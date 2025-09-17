# Roles_Permisos/permissions.py

from rest_framework.permissions import BasePermission
from rest_framework import permissions

class HasPrivilege(BasePermission):
    """
    Permiso personalizado para verificar si el rol del usuario autenticado
    tiene un privilegio específico (codename) requerido por la vista.
    
    Uso en una vista:
    permission_classes = [IsAuthenticated, HasPrivilege]
    
    Para vistas de solo lectura (GET, LIST):
    required_privilege = 'modulo_ver'
    
    Para vistas con múltiples acciones (Crear, Editar, etc.):
    def get_required_privilege(self, method):
        if self.request.method == 'POST':
            return 'modulo_crear'
        if self.request.method in ['PUT', 'PATCH']:
            return 'modulo_editar'
        if self.request.method == 'DELETE':
            return 'modulo_eliminar'
        return None # Denegar por defecto si no se especifica
    """
    
    def has_permission(self, request, view):
        # El usuario debe estar logueado para tener privilegios
        if not request.user or not request.user.is_authenticated:
            return False
        
        # El superusuario siempre tiene acceso total
        if request.user.is_superuser:
            return True

        # Determinar el privilegio requerido por la vista
        required_privilege = None
        if hasattr(view, 'get_required_privilege'):
            # Para vistas con múltiples acciones (POST, PUT, etc.)
            required_privilege = view.get_required_privilege(request.method)
        elif hasattr(view, 'required_privilege'):
            # Para vistas con una sola acción (GET)
            required_privilege = view.required_privilege

        if not required_privilege:
            # Por seguridad, si una vista usa este permiso, DEBE definir el privilegio.
            return False

        # Verificar si el rol del usuario (si existe y está activo) tiene el privilegio.
        if hasattr(request.user, 'rol') and request.user.rol and request.user.rol.activo:
            # Esta consulta es muy eficiente si los permisos del usuario se cargan
            # al inicio (prefetch_related en la vista de login/perfil)
            return request.user.rol.permisos.filter(codename=required_privilege).exists()

        return False
    


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permiso personalizado para permitir el acceso de solo lectura (GET) a cualquiera,
    pero solo permitir escritura (POST, PUT, PATCH, DELETE) a los administradores autenticados.
    """
    def has_permission(self, request, view):
        # El acceso de lectura (GET, HEAD, OPTIONS) está permitido para cualquiera,
        # esté logueado o no.
        if request.method in permissions.SAFE_METHODS:
            return True

        # Para cualquier otro método (escritura), el usuario debe estar
        # autenticado Y ser un administrador (is_staff).
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)