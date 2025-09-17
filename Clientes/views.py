# Clientes/views.py
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from django.db.models import ProtectedError
from django.db import IntegrityError
from rest_framework.exceptions import ValidationError
from Ventas.models import Venta
from .models import Cliente
from authentication.serializers import ClienteRegistrationSerializer as AuthClienteRegistrationSerializer
from .serializers import ClienteSerializer, ClienteLookupSerializer


from Roles_Permisos.permissions import HasPrivilege

from django.shortcuts import get_object_or_404 
from Creditos.models import Credito
from django.utils import timezone

class ClienteRegistroView(generics.CreateAPIView):
    """
    Permite a cualquiera registrar un nuevo Cliente (auto-registro).
    No necesita permisos especiales.
    """
    queryset = Cliente.objects.all()
    serializer_class = AuthClienteRegistrationSerializer
    permission_classes = [permissions.AllowAny]

class ClienteLoginView(APIView):
    """
    (Sin cambios en los permisos, es una vista pública)
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        correo = request.data.get('correo')
        password = request.data.get('password')

        if correo is None or password is None:
            return Response(
                {'detail': 'Por favor, proporcione correo y contraseña.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            cliente = Cliente.objects.get(correo__iexact=correo)
        except Cliente.DoesNotExist:
            return Response(
                {'detail': 'Correo o contraseña incorrectos.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if not cliente.activo:
            return Response(
                {'detail': 'Esta cuenta de cliente está inactiva.'},
                status=status.HTTP_403_FORBIDDEN
            )

        if not cliente.check_password(password):
            return Response(
                {'detail': 'Correo o contraseña incorrectos.'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        must_change = cliente.must_change_password
        cliente_data = ClienteSerializer(cliente).data
        
        return Response({
            'message': 'Inicio de sesión de cliente exitoso.',
            'cliente': cliente_data,
            'rol': 'cliente',
            'must_change_password': must_change,
            'user_id': cliente.id 
        }, status=status.HTTP_200_OK)


class ClienteListCreateView(generics.ListCreateAPIView):
    """
    Vista para listar todos los Clientes o crear un nuevo Cliente (por un admin).
    """
    queryset = Cliente.objects.all().order_by('apellido', 'nombre')
    serializer_class = ClienteSerializer 
    
    
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    
    
    def get_required_privilege(self, method):
        if method == 'GET':
            return 'clientes_ver'
        if method == 'POST':
            return 'clientes_crear'
        return None

    def get_queryset(self):
        queryset = Cliente.objects.all()
        activo_param = self.request.query_params.get('activo')
        if activo_param and activo_param.lower() == 'true':
            queryset = queryset.filter(activo=True)
        return queryset.order_by('nombre', 'apellido')

class ClienteRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer
    
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]

    def get_required_privilege(self, method):
        if method == 'GET':
            return 'clientes_ver'
        if method in ['PUT', 'PATCH']:
            return 'clientes_editar'
        if method == 'DELETE':
            return 'clientes_eliminar'
        return None

    def perform_destroy(self, instance):
        """
        Verifica las dependencias antes de eliminar a un cliente.
        Si tiene registros asociados, bloquea la eliminación.
        """
        
        
        # 1. Verificar si el cliente tiene ventas asociadas
        
        if Venta.objects.filter(cliente=instance).exists():
            raise ValidationError(
                "Este cliente no puede ser eliminado porque tiene ventas registradas. Por favor, considere desactivarlo en su lugar."
            )

        # 2. Verificar si el cliente tiene créditos asociados
        if Credito.objects.filter(cliente=instance).exists():
            raise ValidationError(
                "Este cliente no puede ser eliminado porque tiene créditos asociados. Por favor, considere desactivarlo en su lugar."
            )
        
        

        # Si pasa todas las validaciones, se procede con la eliminación.
        try:
            instance.delete()
        except Exception as e:
            
            raise ValidationError(f"Ocurrió un error inesperado al intentar eliminar el cliente: {str(e)}")

class ClienteCreditoInfoView(APIView):
    """
    Devuelve información de crédito de un cliente. 
    Usado probablemente al crear una Venta o un Crédito.
    """
    
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
   
    required_privilege = "ventas_crear"

    def get(self, request, cliente_pk=None):
        cliente = get_object_or_404(Cliente, pk=cliente_pk)

        credito_utilizable = Credito.objects.filter(
            cliente=cliente,
            estado__in=['Activo', 'Agotado']
        ).order_by('-fecha_otorgamiento').first()

        if credito_utilizable:
            if credito_utilizable.fecha_vencimiento and credito_utilizable.fecha_vencimiento < timezone.now().date():
                if credito_utilizable.estado != 'Vencido':
                    credito_utilizable.estado = 'Vencido'
                    credito_utilizable.save(update_fields=['estado', 'fecha_actualizacion_registro'])
                
                return Response({
                    "id_credito": credito_utilizable.id,
                    "estado": credito_utilizable.estado,
                    "estado_display": credito_utilizable.get_estado_display(),
                    "saldo_disponible_para_ventas": "0.00",
                    "monto_otorgado": credito_utilizable.monto_otorgado,
                    "mensaje": "El cliente tiene una línea de crédito vencida. No se puede utilizar para nuevas compras a crédito."
                }, status=status.HTTP_200_OK)
            
            return Response({
                "id_credito": credito_utilizable.id,
                "estado": credito_utilizable.estado,
                "estado_display": credito_utilizable.get_estado_display(),
                "saldo_disponible_para_ventas": credito_utilizable.saldo_disponible_para_ventas,
                "monto_otorgado": credito_utilizable.monto_otorgado,
                "mensaje": f"Crédito {credito_utilizable.get_estado_display()} con saldo de ${credito_utilizable.saldo_disponible_para_ventas:,.0f}."
            }, status=status.HTTP_200_OK)
        else:
            credito_vencido_existente = Credito.objects.filter(
                cliente=cliente, estado='Vencido'
            ).order_by('-fecha_otorgamiento').first()

            if credito_vencido_existente:
                 return Response({
                    "id_credito": credito_vencido_existente.id,
                    "estado": "Vencido",
                    "estado_display": "Vencido",
                    "saldo_disponible_para_ventas": "0.00",
                    "monto_otorgado": credito_vencido_existente.monto_otorgado,
                    "mensaje": "El cliente tiene una línea de crédito vencida. No se puede utilizar."
                }, status=status.HTTP_200_OK)

            return Response({
                "no_credito_utilizable": True,
                "mensaje": "El cliente no tiene una línea de crédito activa o utilizable en este momento."
            }, status=status.HTTP_200_OK)

class CheckClientByDocumentView(APIView):
    """
    (Sin cambios en los permisos, es una vista pública)
    """
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        tipo_documento = request.data.get('tipo_documento')
        documento = request.data.get('documento')

        if not tipo_documento or not documento:
            return Response(
                {"detail": "Tipo y número de documento son requeridos."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            cliente = Cliente.objects.get(tipo_documento=tipo_documento, documento=documento)
            serializer = ClienteLookupSerializer(cliente)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Cliente.DoesNotExist:
            return Response(
                {"detail": "Cliente no encontrado."}, 
                status=status.HTTP_404_NOT_FOUND
            )
        


class ClienteProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        """
        Devuelve los datos completos del cliente autenticado.
        """
        # request.user aquí es la instancia completa del modelo Cliente
        # gracias a la configuración de autenticación.
        serializer = ClienteSerializer(request.user)
        return Response(serializer.data)