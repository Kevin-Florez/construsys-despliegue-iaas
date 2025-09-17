from rest_framework import permissions

# --- EXPLICACIÓN ---
# La clase 'PuedeGestionarProveedores' que tenías aquí se basaba en el sistema de permisos
# estándar de Django (request.user.has_perm('proveedores.puede_gestionar_proveedores')).
# Si has adoptado el sistema de Roles y Permisos personalizados (con el modelo Permiso y la clase HasModulePermission)
# para otros módulos, es recomendable usar HasModulePermission también aquí para consistencia.
# Las vistas en Proveedores/views.py han sido actualizadas para usar HasModulePermission.
# Por lo tanto, esta clase PuedeGestionarProveedores podría no ser necesaria para esas vistas específicas.
# La dejo comentada por si la necesitas para otros propósitos o prefieres ese sistema.

# class PuedeGestionarProveedores(permissions.BasePermission):
# """
# Permiso personalizado para permitir solo a usuarios con permiso de 'gestionar_proveedores'.
# """
# def has_permission(self, request, view):
#       # Esto asume que 'proveedores.puede_gestionar_proveedores' es un permiso de Django
#       # (ej. app_label.codename_model) o uno que has creado y asignado de esa forma.
# return request.user and request.user.is_authenticated and request.user.has_perm('proveedores.puede_gestionar_proveedores')

# No se necesitan otras clases de permiso aquí si las vistas usan HasModulePermission.