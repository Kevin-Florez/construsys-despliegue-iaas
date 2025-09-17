from rest_framework import permissions

class PuedeGestionarUsuarios(permissions.BasePermission):
    """
    Permiso personalizado para permitir solo a usuarios con permiso de 'gestionar_usuarios'.
    """
    def has_permission(self, request, view):
        return request.user and request.user.has_perm('usuarios.puede_gestionar_usuarios')

class PuedeGestionarRolesUsuarios(permissions.BasePermission):
    """
    Permiso personalizado para permitir solo a usuarios con permiso de 'gestionar_roles_usuarios'.
    """
    def has_permission(self, request, view):
        return request.user and request.user.has_perm('usuarios.puede_gestionar_roles_usuarios')