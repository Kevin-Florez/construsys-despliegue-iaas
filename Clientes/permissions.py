from rest_framework import permissions

class PuedeGestionarClientes(permissions.BasePermission):
    """
    Permiso personalizado para permitir solo a usuarios con permiso de 'gestionar_clientes'.
    """
    def has_permission(self, request, view):
        return request.user and request.user.has_perm('clientes.puede_gestionar_clientes')