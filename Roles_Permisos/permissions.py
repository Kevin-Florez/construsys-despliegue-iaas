# Roles_Permisos/permissions.py

from rest_framework.permissions import BasePermission
from rest_framework import permissions

class HasPrivilege(BasePermission):
    """
    Permiso personalizado para verificar si el rol del usuario autenticado
    tiene un privilegio específico (codename) requerido por la vista.
    
    LÓGICA MEJORADA:
    - Si el permiso requerido termina en '_ver' (ej: 'ventas_ver'), la comprobación
      será exitosa si el usuario tiene CUALQUIER permiso para ese módulo (ej: 'ventas_crear').
    - Para otros permisos (ej: 'ventas_crear'), se busca la coincidencia exacta.
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
            required_privilege = view.get_required_privilege(request.method)
        elif hasattr(view, 'required_privilege'):
            required_privilege = view.required_privilege

        if not required_privilege:
            # Por seguridad, si una vista usa este permiso, DEBE definir el privilegio.
            return False

        # Si el usuario no tiene un rol activo, denegar acceso.
        if not hasattr(request.user, 'rol') or not request.user.rol or not request.user.rol.activo:
            return False

        # ✨ --- INICIO DE LA LÓGICA MEJORADA --- ✨
        # Si el permiso requerido es para 'ver', comprobamos si tiene CUALQUIER privilegio del módulo.
        if required_privilege.endswith('_ver'):
            # Extraemos el nombre del módulo. Ej: 'ventas_ver' -> 'ventas'
            module_name_prefix = required_privilege.rsplit('_', 1)[0] + "_"
            
            # Verificamos si existe algún permiso que comience con el prefijo del módulo.
            # Ej: 'ventas_crear', 'ventas_editar', etc.
            return request.user.rol.permisos.filter(codename__startswith=module_name_prefix).exists()
        
        # Si el permiso no es de 'ver' (ej: 'ventas_crear'), se mantiene la lógica original
        # de buscar el privilegio exacto.
        return request.user.rol.permisos.filter(codename=required_privilege).exists()
        # ✨ --- FIN DE LA LÓGICA MEJORADA --- ✨

class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Permiso personalizado para permitir el acceso de solo lectura (GET) a cualquiera,
    pero solo permitir escritura (POST, PUT, PATCH, DELETE) a los administradores autenticados.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)