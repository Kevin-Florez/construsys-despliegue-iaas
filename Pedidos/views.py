# Pedidos/views.py

from rest_framework import generics, permissions, status, views
from rest_framework.response import Response
from django.db import transaction, models
from django.http import Http404
from rest_framework.views import APIView
from rest_framework.exceptions import PermissionDenied, ValidationError as RestFrameworkValidationError
from django.core.exceptions import ValidationError
import json
import logging
from decimal import Decimal
from django.conf import settings
from Productos.models import Producto
from Clientes.models import Cliente as ModeloCliente
from django.db.models import Q
from .models import Pedido, ComprobantePago
from .serializers import PedidoSerializer, GuestPedidoStatusSerializer, ComprobantePagoSerializer 
from Roles_Permisos.permissions import HasPrivilege
from django.contrib.auth import get_user_model
from .emails import enviar_correo_actualizacion_estado
from rest_framework.filters import SearchFilter, OrderingFilter # Asegúrate de importar OrderingFilter si quieres ordenar
from django_filters.rest_framework import DjangoFilterBackend 

User = get_user_model()
logger = logging.getLogger(__name__)


class PedidoListCreateView(generics.ListCreateAPIView):
    serializer_class = PedidoSerializer

    filter_backends = [SearchFilter]
    search_fields = ['id', 'estado']

    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            raise PermissionDenied("No tienes permiso para ver esta lista.")
        return Pedido.objects.filter(cliente=self.request.user, es_carrito_activo=False).prefetch_related('detalles__producto', 'comprobantes').order_by('-id')

    def perform_create(self, serializer):
        serializer.save()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

class GuestPedidoStatusView(generics.RetrieveAPIView):
    # 👇 Añade .select_related('cliente') a tu queryset
    queryset = Pedido.objects.all().select_related('cliente').prefetch_related('detalles__producto', 'comprobantes')
    serializer_class = GuestPedidoStatusSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = 'token_seguimiento'

class GuestPedidoLookupView(views.APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request, *args, **kwargs):
        pedido_id = request.data.get('pedidoId')
        email = request.data.get('email')

        if not pedido_id or not email:
            return Response({'detail': 'Se requiere el número de pedido y el correo electrónico.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            pedido = Pedido.objects.get(
                Q(id=pedido_id),
                Q(email_invitado__iexact=email) | Q(cliente__correo__iexact=email)
            )
            return Response({'token': pedido.token_seguimiento}, status=status.HTTP_200_OK)
        except Pedido.DoesNotExist:
            return Response({'detail': 'No se encontró ningún pedido con los datos proporcionados.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error en la búsqueda de pedido: {e}")
            return Response({'detail': 'Ocurrió un error al procesar tu solicitud.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ClientePedidoListView(generics.ListAPIView):
    serializer_class = PedidoSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        tipo_documento = self.request.query_params.get('tipo_documento')
        documento = self.request.query_params.get('documento')

        if not tipo_documento or not documento:
            raise RestFrameworkValidationError("Se requieren el tipo y número de documento.")

        query = Q(cliente__tipo_documento=tipo_documento, cliente__documento=documento) | \
                Q(tipo_documento_invitado=tipo_documento, documento_invitado=documento)

        return Pedido.objects.filter(
            query,
            estado__in=['pendiente_pago', 'pendiente_pago_temporal', 'en_verificacion', 'pago_incompleto', 'confirmado', 'en_camino'],
            es_carrito_activo=False
        ).prefetch_related('detalles__producto', 'comprobantes').order_by('-id')

class AdminPedidoListView(generics.ListAPIView):
 queryset = Pedido.objects.filter(es_carrito_activo=False).select_related('cliente').prefetch_related('comprobantes').order_by('-id')
 serializer_class = PedidoSerializer
 permission_classes = [permissions.IsAuthenticated, HasPrivilege]
 required_privilege = "pedidos_ver"


 filter_backends = [DjangoFilterBackend, SearchFilter]

 filterset_fields = ['estado']

 search_fields = ['id', 'cliente__nombre', 'cliente__correo', 'email_invitado', 'nombre_receptor']

class AdminPedidoDetailView(generics.RetrieveUpdateAPIView):
    queryset = Pedido.objects.all().prefetch_related('detalles__producto', 'comprobantes')
    serializer_class = PedidoSerializer
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    http_method_names = ['get', 'patch']

    def get_required_privilege(self, method):
        if method == 'GET':
            return 'pedidos_ver'
        if method == 'PATCH':
            return 'pedidos_gestionar_estado'
        return None

    def partial_update(self, request, *args, **kwargs):

        print("Datos de la petición PATCH:", request.data)
        pedido = self.get_object()
        nuevo_estado = request.data.get('estado')
        monto_pagado_verificado = request.data.get('monto_pagado_verificado')
        motivo = request.data.get('motivo_cancelacion', '').strip()

        if not nuevo_estado:
            return Response({'detail': 'El campo "estado" es requerido.'}, status=status.HTTP_400_BAD_REQUEST)

        estado_anterior = pedido.estado

        transiciones_validas = {
            'pendiente_pago': ['en_verificacion', 'cancelado'],
            'pendiente_pago_temporal': ['en_verificacion', 'cancelado'],
            'en_verificacion': ['pago_incompleto', 'confirmado', 'cancelado'],
            'pago_incompleto': ['en_verificacion', 'confirmado', 'cancelado'],
            'confirmado': ['en_camino', 'cancelado'],
            'en_camino': ['entregado', 'cancelado'],
            'entregado': [],
            'cancelado': [],
            'cancelado_por_inactividad': [],
        }

        if pedido.metodo_entrega == 'tienda' and estado_anterior == 'confirmado':
            transiciones_validas['confirmado'] = ['entregado', 'cancelado']

        if nuevo_estado not in transiciones_validas.get(estado_anterior, []):
            estado_anterior_display = pedido.get_estado_display()
            nuevo_estado_display = dict(Pedido.ESTADO_CHOICES).get(nuevo_estado, nuevo_estado)
            raise RestFrameworkValidationError(f"No se puede cambiar el estado de '{estado_anterior_display}' a '{nuevo_estado_display}'.")

        if nuevo_estado == 'pago_incompleto':
            if not monto_pagado_verificado:
                raise RestFrameworkValidationError("Para marcar un pago como incompleto, se debe especificar el 'monto_pagado_verificado'.")
            if Decimal(monto_pagado_verificado) >= pedido.total:
                 raise RestFrameworkValidationError("El monto verificado no puede ser igual o mayor al total del pedido. Usa el estado 'confirmado' en su lugar.")
            pedido.monto_pagado_verificado = Decimal(monto_pagado_verificado)
            pedido.motivo_cancelacion = None

        if nuevo_estado in ['cancelado', 'cancelado_por_inactividad']:
            if not motivo:
                raise RestFrameworkValidationError("Para cancelar un pedido, se debe proporcionar un motivo.")
            pedido.motivo_cancelacion = motivo
            pedido.monto_pagado_verificado = Decimal('0.00')

        try:
            pedido.estado = nuevo_estado
            pedido.save()

            if nuevo_estado == 'confirmado':
                 pedido._process_confirmation()

            if nuevo_estado in ['confirmado', 'en_camino', 'entregado', 'pago_incompleto', 'cancelado', 'cancelado_por_inactividad']:
                enviar_correo_actualizacion_estado(pedido)
        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error inesperado en AdminPedidoDetailView: {e}")
            return Response({"detail": "Ocurrió un error interno. Revisa los logs del servidor."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        serializer = self.get_serializer(pedido)
        return Response(serializer.data)

class AgregarComprobanteView(generics.CreateAPIView):
    serializer_class = ComprobantePagoSerializer  # Asumiendo que quieres el detalle completo del pedido
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        token_seguimiento = self.kwargs.get('token_seguimiento')
        try:
            pedido = Pedido.objects.get(token_seguimiento=token_seguimiento)
        except Pedido.DoesNotExist:
            raise Http404

        if pedido.estado not in ['pendiente_pago', 'pendiente_pago_temporal', 'pago_incompleto']:
            raise RestFrameworkValidationError("No se pueden añadir comprobantes a este pedido en su estado actual.")

        # Aquí asumimos que el serializer puede manejar la creación de un comprobante
        # y asociarlo al pedido. Si no, necesitarías un serializer específico.
        serializer.save(pedido=pedido)

        pedido.estado = 'en_verificacion'
        pedido.save(update_fields=['estado'])

        logger.info(f"Nuevo comprobante subido para el Pedido #{pedido.id}. Pasó a estado 'En Verificación'.")

class CarritoActivoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        cliente = ModeloCliente.objects.filter(id=request.user.id).first()
        if not cliente:
            return Response({"detail": "El usuario no es un cliente."}, status=status.HTTP_403_FORBIDDEN)

        try:
            carrito_activo = Pedido.objects.get(cliente=cliente, es_carrito_activo=True)
            serializer = PedidoSerializer(carrito_activo)
            return Response(serializer.data)
        except Pedido.DoesNotExist:
            return Response({"detalles": []})

class UnirCarritosView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        local_cart_items = request.data.get('local_cart', [])
        cliente = ModeloCliente.objects.filter(id=request.user.id).first()
        if not cliente:
            return Response({"detail": "El usuario no es un cliente."}, status=status.HTTP_403_FORBIDDEN)

        carrito_db, created = Pedido.objects.get_or_create(
            cliente=cliente,
            es_carrito_activo=True,
            defaults={
                'estado': 'pendiente_pago',
                'total': 0,
                'nombre_receptor': cliente.nombre,
                'telefono_receptor': cliente.telefono
            }
        )

        items_en_db = {item.producto.id: item for item in carrito_db.detalles.all()}

        for local_item in local_cart_items:
            producto_id = local_item.get('id')
            cantidad_local = local_item.get('quantity', 1)

            if not producto_id:
                continue

            if producto_id in items_en_db:
                item_db = items_en_db[producto_id]
                item_db.cantidad += cantidad_local
                item_db.save(update_fields=['cantidad'])
            else:
                try:
                    producto = Producto.objects.get(id=producto_id)
                    from .models import DetallePedido
                    DetallePedido.objects.create(
                        pedido=carrito_db,
                        producto=producto,
                        cantidad=cantidad_local,
                        precio_unitario=producto.precio_venta
                    )
                except Producto.DoesNotExist:
                    continue

        carrito_db.refresh_from_db()
        subtotal = sum(detalle.subtotal for detalle in carrito_db.detalles.all())
        tasa_iva = Decimal(settings.TASA_IVA) / Decimal('100.0')
        iva = subtotal * tasa_iva
        total = subtotal + iva

        carrito_db.subtotal = subtotal
        carrito_db.iva = iva
        carrito_db.total = total
        carrito_db.save()

        serializer = PedidoSerializer(carrito_db)
        return Response(serializer.data)

class ActualizarCarritoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        nuevos_items_carrito = request.data.get('cart', [])
        cliente = ModeloCliente.objects.filter(id=request.user.id).first()
        if not cliente:
            return Response({"detail": "El usuario no es un cliente."}, status=status.HTTP_403_FORBIDDEN)

        carrito_db, created = Pedido.objects.get_or_create(
            cliente=cliente,
            es_carrito_activo=True,
            defaults={
                'estado': 'pendiente_pago',
                'total': 0,
                'nombre_receptor': cliente.nombre,
                'telefono_receptor': cliente.telefono
            }
        )

        carrito_db.detalles.all().delete()

        from .models import DetallePedido
        detalles_a_crear = []
        for item_data in nuevos_items_carrito:
            producto_id = item_data.get('id')
            try:
                producto = Producto.objects.get(id=producto_id)
                detalles_a_crear.append(
                    DetallePedido(
                        pedido=carrito_db,
                        producto=producto,
                        cantidad=item_data.get('quantity', 1),
                        precio_unitario=producto.precio_venta
                    )
                )
            except Producto.DoesNotExist:
                continue

        DetallePedido.objects.bulk_create(detalles_a_crear)

        carrito_db.refresh_from_db()
        subtotal = sum(d.subtotal for d in carrito_db.detalles.all())
        tasa_iva = Decimal(settings.TASA_IVA) / Decimal('100.0')
        iva = subtotal * tasa_iva
        carrito_db.subtotal = subtotal
        carrito_db.iva = iva
        carrito_db.total = subtotal + iva
        carrito_db.save()

        return Response({"detail": "Carrito actualizado con éxito."}, status=status.HTTP_200_OK)
    



class CarritoActivoView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        # ✨ CORRECCIÓN: Usamos el ID de la instancia de CustomUser para buscar el Cliente
        cliente = ModeloCliente.objects.filter(id=request.user.id).first()
        
        if not cliente:
            # Manejar el caso de que el usuario autenticado no sea un Cliente
            # Este caso ocurre para usuarios admin o superuser
            return Response({"detail": "El usuario no es un cliente. No tiene carrito activo."}, status=status.HTTP_403_FORBIDDEN)
        
        try:
            carrito_activo = Pedido.objects.get(cliente=cliente, es_carrito_activo=True)
            serializer = PedidoSerializer(carrito_activo)
            return Response(serializer.data)
        except Pedido.DoesNotExist:
            return Response({"detalles": []})
        

class PedidoDetailView(generics.RetrieveAPIView):
    """
    Vista para que un cliente autenticado vea el detalle de UNO de sus pedidos.
    """
    serializer_class = PedidoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Esta función es la clave de la seguridad: asegura que un usuario
        solo pueda ver los pedidos que le pertenecen.
        """
        # Asumiendo que tu modelo Pedido tiene una relación ForeignKey llamada 'cliente' con el modelo User
        return self.request.user.pedidos.all()