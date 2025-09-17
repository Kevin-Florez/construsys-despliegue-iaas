from rest_framework import permissions

class PuedeGestionarVentas(permissions.BasePermission):
    """
    Permiso personalizado para permitir solo a usuarios con permiso de 'gestionar_ventas'.
    """
    def has_permission(self, request, view):
        return request.user and request.user.has_perm('ventas.puede_gestionar_ventas')