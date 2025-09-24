# Usuarios/views.py
from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from rest_framework.exceptions import PermissionDenied, ValidationError 

from .serializers import (
    UsuarioSerializer,
    UsuarioCreateSerializer,
    UsuarioUpdateSerializer,
    CambiarContrasenaSerializer,
    UserProfileSerializer
)

from Clientes.models import Cliente
from Ventas.models import Venta # Asumiendo que tienes un app 'Ventas' con un modelo 'Venta'
from Compras.models import Compra
from Clientes.serializers import ClienteProfileSerializer
# ✨ 1. Importamos la nueva clase de permiso
from Roles_Permisos.permissions import HasPrivilege

User = get_user_model()

class UsuarioListCreateView(generics.ListCreateAPIView):
    """
    Vista para listar todos los CustomUser y crear uno nuevo.
    Requiere privilegios específicos para ver o crear.
    """
    queryset = User.objects.all().order_by('first_name', 'last_name')
    # ✨ 2. Reemplazamos el sistema de permisos
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return UsuarioCreateSerializer
        return UsuarioSerializer
        
    # ✨ 3. Definimos los privilegios para cada acción (GET vs POST)
    def get_required_privilege(self, method):
        if method == 'GET':
            return 'usuarios_ver'
        if method == 'POST':
            return 'usuarios_crear'
        return None # Denegar por defecto

class UsuarioRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """
    Vista para obtener, actualizar y eliminar un CustomUser específico por su ID.
    Requiere privilegios específicos para cada acción.
    """
    queryset = User.objects.all()
    # ✨ 2. Reemplazamos el sistema de permisos
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return UsuarioUpdateSerializer
        return UsuarioSerializer

    # ✨ 3. Definimos los privilegios para cada acción
    def get_required_privilege(self, method):
        if method == 'GET':
            return 'usuarios_ver'
        if method in ['PUT', 'PATCH']:
            return 'usuarios_editar'
        if method == 'DELETE':
            # Nota: Django REST Framework no siempre expone DELETE en esta vista,
            # pero si lo haces, este sería el permiso.
            return 'usuarios_eliminar' # Asumiendo que existe un privilegio 'eliminar'
        return None
        
    def perform_update(self, serializer):
        instance = self.get_object()
        
        # Lógica para prevenir la autodesactivación (sin cambios)
        if 'activo' in self.request.data and self.request.data.get('activo') is False:
            if instance.pk == self.request.user.pk:
                raise PermissionDenied(
                    detail="No puedes desactivar tu propia cuenta a través de esta interfaz."
                )
        
        serializer.save()

    def perform_destroy(self, instance):
        # 1. Validaciones de autoprotección (ya las tenías y están bien)
        if instance.pk == self.request.user.pk:
            raise PermissionDenied(detail="No puedes eliminar tu propia cuenta.")
        
        if instance.is_superuser:
            raise PermissionDenied(detail="Las cuentas de superusuario no pueden ser eliminadas.")
            
        # 2. ✨ NUEVA VALIDACIÓN DE INTEGRIDAD DE DATOS ✨
        # Comprueba si el usuario tiene registros asociados en otros modelos.
        # Añade aquí todos los modelos importantes donde un usuario puede estar referenciado.
        
        # Ejemplo con Ventas (ajusta 'usuario_creador' al nombre real de tu campo ForeignKey)
        #if Venta.objects.filter(usuario_creador=instance).exists():
            #raise ValidationError("Este usuario no puede ser eliminado porque tiene ventas asociadas. Por favor, desactívelo en su lugar.")

        # Ejemplo con Compras
        #if Compra.objects.filter(usuario_registra=instance).exists():
            #raise ValidationError("Este usuario no puede ser eliminado porque tiene compras asociadas. Por favor, desactívelo en su lugar.")

        # Puedes añadir más comprobaciones aquí...
        # if Producto.objects.filter(usuario=instance).exists():
        #     raise ValidationError(...)

        # 3. Si pasa todas las validaciones, procede a eliminar.
        instance.delete()

class CambiarContrasenaView(APIView):
    """
    Vista para que un usuario autenticado cambie su propia contraseña.
    (Sin cambios, solo requiere autenticación, no privilegios especiales).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CambiarContrasenaSerializer(data=request.data, context={'request': request, 'user': request.user})
        if serializer.is_valid():
            password_actual = serializer.validated_data['password_actual']
            password_nuevo = serializer.validated_data['password_nuevo']
            user = request.user
            
            if not hasattr(user, 'check_password'):
                return Response({'error': 'Objeto de usuario inválido para check_password.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            if user.check_password(password_actual):
                user.set_password(password_nuevo)
                if hasattr(user, 'must_change_password'):
                    user.must_change_password = False
                user.save(update_fields=['password', 'must_change_password'] if hasattr(user, 'must_change_password') else ['password'])
                return Response({'mensaje': 'Contraseña cambiada exitosamente.'}, status=status.HTTP_200_OK)
            else:
                return Response({'error': 'La contraseña actual es incorrecta.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class PerfilView(APIView):
    """
    Vista para obtener y ACTUALIZAR el perfil del usuario actualmente autenticado.
    (Sin cambios, solo requiere autenticación, no privilegios especiales).
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        
        if isinstance(user, User):
            serializer = UserProfileSerializer(user)
        elif isinstance(user, Cliente):
            serializer = ClienteProfileSerializer(user)
        else:
            return Response(
                {"detail": "Tipo de usuario no reconocido."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        return Response(serializer.data)

    def put(self, request):
        user = request.user
        
        if isinstance(user, User):
            serializer_class = UsuarioUpdateSerializer 
        elif isinstance(user, Cliente):
            serializer_class = ClienteProfileSerializer
        else:
            return Response(
                {"detail": "Tipo de usuario no reconocido para actualización."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = serializer_class(instance=user, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)