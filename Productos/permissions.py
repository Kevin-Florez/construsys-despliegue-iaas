from rest_framework import permissions

class PuedeGestionarProductos(permissions.BasePermission):
    """
    Permiso personalizado para permitir solo a usuarios con permiso de 'gestionar_productos'.
    """
    def has_permission(self, request, view):
        return request.user and request.user.has_perm('productos.puede_gestionar_productos')

class PuedeGestionarCategoriasProductos(permissions.BasePermission):
    """
    Permiso personalizado para permitir solo a usuarios con permiso de 'gestionar_categorias_productos'.
    """
    def has_permission(self, request, view):
        return request.user and request.user.has_perm('productos.puede_gestionar_categorias_productos')