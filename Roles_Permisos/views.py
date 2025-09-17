# Roles_Permisos/views.py
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied
from .models import Rol, Permiso
from .serializers import RolSerializer, PermisoSerializer
# ✨ 1. Importamos la nueva clase de permiso
from .permissions import HasPrivilege

# Constantes para nombres de roles protegidos
ADMINISTRADOR_ROLE_NAME = 'Administrador'
PROTECTED_ROLE_NAMES = [ADMINISTRADOR_ROLE_NAME.lower()]

class PermisoListCreateView(generics.ListAPIView):
    """
    Vista para listar todos los privilegios, agrupados por módulo.
    """
    queryset = Permiso.objects.all().order_by('modulo', 'nombre')
    serializer_class = PermisoSerializer
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    required_privilege = 'roles_ver'

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        
        grouped_data = {}
        for permiso in serializer.data:
            # Usamos .get() para evitar errores si 'modulo' no existiera
            modulo = permiso.get('modulo', 'General') 
            if modulo not in grouped_data:
                grouped_data[modulo] = []
            
            # Limpiamos el nombre para el frontend (Ej: "Ventas | Ver" -> "Ver")
            permiso['nombre'] = permiso['nombre'].split('|')[-1].strip()
            grouped_data[modulo].append(permiso)
            
        return Response(grouped_data)

class PermisoRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Permiso.objects.all()
    serializer_class = PermisoSerializer
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    # No se puede editar un permiso individualmente, solo ver.
    required_privilege = 'roles_ver'

class RolListCreateView(generics.ListCreateAPIView):
    queryset = Rol.objects.all().order_by('nombre')
    serializer_class = RolSerializer
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]

    def get_required_privilege(self, method):
        if method == 'GET':
            return 'roles_ver'
        if method == 'POST':
            return 'roles_crear'
        return None

class RolRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Rol.objects.all()
    serializer_class = RolSerializer
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]

    def get_required_privilege(self, method):
        if method == 'GET':
            return 'roles_ver'
        if method in ['PUT', 'PATCH']:
            return 'roles_editar'
        if method == 'DELETE':
            return 'roles_eliminar'
        return None

    def perform_update(self, serializer):
        instance = self.get_object()

        if instance.nombre.lower() in PROTECTED_ROLE_NAMES:
            nuevo_nombre_propuesto = serializer.validated_data.get('nombre', instance.nombre)
            if nuevo_nombre_propuesto.lower() != instance.nombre.lower():
                raise ValidationError(f"El nombre del rol protegido '{instance.nombre}' no puede ser cambiado.")
            if 'activo' in serializer.validated_data and serializer.validated_data['activo'] is False:
                raise ValidationError(f"El rol protegido '{instance.nombre}' no puede ser desactivado.")
        
        if 'activo' in serializer.validated_data and not serializer.validated_data['activo']:
            if instance.nombre.lower() not in PROTECTED_ROLE_NAMES and hasattr(instance, 'usuarios') and instance.usuarios.exists():
                raise ValidationError(
                    f"El rol '{instance.nombre}' está asignado a uno o más usuarios y no puede ser desactivado. "
                    "Primero debe reasignar los usuarios a otros roles."
                )
        
        serializer.save()

    def perform_destroy(self, instance):
        if instance.nombre.lower() in PROTECTED_ROLE_NAMES:
            raise PermissionDenied(
                detail=f"El rol '{instance.nombre}' es un rol protegido y no puede ser eliminado."
            )

        if hasattr(instance, 'usuarios') and instance.usuarios.exists():
            raise ValidationError(
                "Este rol está actualmente asignado a uno o más usuarios y no puede ser eliminado. "
                "Primero debe reasignar los usuarios a otros roles"
            )
        
        instance.delete()