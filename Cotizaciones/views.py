# Cotizaciones/views.py

from rest_framework import generics, permissions, status, views
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from django.conf import settings
from django.db.models import Q
from .models import Cotizacion, DetalleCotizacion
from .serializers import CotizacionCreateSerializer, CotizacionReadSerializer
from Productos.models import Producto
from Pedidos.models import Pedido, DetallePedido
from Pedidos.emails import enviar_correo_confirmacion_pedido
from Roles_Permisos.permissions import HasPrivilege

from .serializers import AdminCotizacionCreateSerializer
from Clientes.models import Cliente
from .pdf_generator import generate_cotizacion_pdf
from django.http import HttpResponse


from .emails import enviar_correo_cotizacion_invitado


# --- VISTAS PARA EL CLIENTE Y EL PÚBLICO ---


class AdminCotizacionCreateView(generics.CreateAPIView):
    """
    Endpoint para que un administrador cree una nueva cotización para un cliente
    o un invitado.
    """
    serializer_class = AdminCotizacionCreateSerializer
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    required_privilege = 'cotizaciones_crear' # Asegúrate de que este privilegio exista

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cotizacion = serializer.save()

        # Opcional: Enviar correo si se creó para un invitado
        if not cotizacion.cliente and cotizacion.email_invitado:
            try:
                enviar_correo_cotizacion_invitado(cotizacion)
            except Exception as e:
                # No detener el proceso si el correo falla, pero sí registrarlo
                print(f"ADVERTENCIA: Cotización #{cotizacion.id} creada por admin, pero no se pudo enviar correo a invitado. Causa: {e}")

        read_serializer = CotizacionReadSerializer(cotizacion)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)
    


class CotizacionCreateView(generics.CreateAPIView):
    """
    Endpoint para crear una nueva cotización.
    Accesible por cualquier usuario (autenticado o invitado).
    Recibe los items del carrito y los datos del invitado si aplica.
    """
    serializer_class = CotizacionCreateSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        serializer.save()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        
        cotizacion_instance = serializer.instance

        
        # Verificamos si la cotización no tiene un cliente asociado (es de un invitado)
        if not cotizacion_instance.cliente and cotizacion_instance.email_invitado:
            enviar_correo_cotizacion_invitado(cotizacion_instance)
        
        
        read_serializer = CotizacionReadSerializer(cotizacion_instance)
        headers = self.get_success_headers(read_serializer.data)
        
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class MisCotizacionesListView(generics.ListAPIView):
    """
    Endpoint para que un cliente autenticado vea su historial de cotizaciones.
    Ahora incluye lógica de búsqueda.
    """
    serializer_class = CotizacionReadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        
        # Comienza con el queryset base de cotizaciones del usuario
        if hasattr(user, 'cotizaciones'):
            queryset = user.cotizaciones.prefetch_related('detalles__producto').order_by('-id')
        else:
            return Cotizacion.objects.none()

        
        # Leemos el parámetro 'search' que enviará Flutter
        query = self.request.query_params.get('search', None)
        
        if query:
            # Si hay un término de búsqueda, filtramos el queryset
            # Busca si el ID contiene el texto O si el estado contiene el texto
            queryset = queryset.filter(
                Q(id__icontains=query) | 
                Q(estado__icontains=query)
            )
       
            
        return queryset

class CotizacionRetrieveView(generics.RetrieveAPIView):
    """
    Endpoint para ver una cotización específica usando su token de acceso.
    Sirve tanto para el cliente como para el invitado que tiene el enlace.
    """
    queryset = Cotizacion.objects.prefetch_related('detalles__producto').all()
    serializer_class = CotizacionReadSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'token_acceso'

class ConvertirCotizacionAPedidoView(views.APIView):
    """
    Endpoint para convertir una cotización vigente en un pedido.
    """
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request, token_acceso, *args, **kwargs):
        cotizacion = get_object_or_404(Cotizacion, token_acceso=token_acceso)

        if cotizacion.estado != 'vigente' or cotizacion.is_expired:
            raise ValidationError("Esta cotización no es válida o ha expirado y no puede ser convertida en un pedido.")
        
        for detalle in cotizacion.detalles.all():
            if not detalle.producto or detalle.producto.stock_actual < detalle.cantidad:
                raise ValidationError(f"No hay stock suficiente para '{detalle.producto_nombre_historico}'.")

        pedido = Pedido.objects.create(
            cliente=cotizacion.cliente,
            email_invitado=cotizacion.email_invitado,
            nombre_receptor=cotizacion.cliente.nombre if cotizacion.cliente else cotizacion.nombre_invitado,
            telefono_receptor=cotizacion.cliente.telefono if cotizacion.cliente else "N/A",
            subtotal=cotizacion.subtotal,
            iva=cotizacion.iva,
            total=cotizacion.total,
            estado='pendiente_pago_temporal',
            fecha_limite_pago=timezone.now() + timezone.timedelta(hours=1),
        )

        detalles_pedido_a_crear = [
            DetallePedido(
                pedido=pedido,
                producto=detalle.producto,
                cantidad=detalle.cantidad,
                precio_unitario=detalle.precio_unitario_cotizado
            )
            for detalle in cotizacion.detalles.all()
        ]
        DetallePedido.objects.bulk_create(detalles_pedido_a_crear)

        cotizacion.estado = 'convertida'
        cotizacion.save(update_fields=['estado'])
        
        try:
            enviar_correo_confirmacion_pedido(pedido)
        except Exception as e:
            print(f"ERROR: No se pudo enviar el correo de confirmación del pedido #{pedido.id}. Causa: {e}")

        return Response({
            "message": "La cotización ha sido convertida a un pedido exitosamente.",
            "pedido_token_seguimiento": pedido.token_seguimiento
        }, status=status.HTTP_201_CREATED)


# --- VISTAS PARA EL ADMINISTRADOR ---

class AdminCotizacionListView(generics.ListAPIView):
    """
    Vista para que los administradores listen todas las cotizaciones del sistema.
    """
    queryset = Cotizacion.objects.select_related('cliente').order_by('-id')
    serializer_class = CotizacionReadSerializer
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    required_privilege = 'cotizaciones_ver'

class AdminCotizacionDetailView(generics.RetrieveAPIView):
    """
    Vista para que los administradores vean el detalle de una cotización específica por ID.
    """
    queryset = Cotizacion.objects.prefetch_related('detalles__producto').all()
    serializer_class = CotizacionReadSerializer
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    required_privilege = 'cotizaciones_ver'



class AdminCotizacionPDFView(views.APIView):
    """
    Endpoint para generar y descargar un PDF de una cotización específica.
    """
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    required_privilege = 'cotizaciones_ver' 

    def get(self, request, pk, *args, **kwargs):
        cotizacion = get_object_or_404(Cotizacion, pk=pk)
        pdf_buffer = generate_cotizacion_pdf(cotizacion)
        
        response = HttpResponse(pdf_buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="cotizacion_{cotizacion.id}.pdf"'
        
        return response
