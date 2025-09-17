# Creditos/permissions.py
from rest_framework import permissions
from Roles_Permisos.permissions import HasModulePermission # Importa tu clase base

# YA NO SE NECESITA si usas HasModulePermission directamente en la vista.
# class PuedeGestionarCreditos(permissions.BasePermission):
#     message = "No tiene permiso para gestionar créditos."
#     def has_permission(self, request, view):
#         if not request.user or not request.user.is_authenticated: return False
#         if request.user.is_superuser: return True
#         if hasattr(request.user, 'rol') and request.user.rol and request.user.rol.activo:
#             return request.user.rol.permisos.filter(nombre="Creditos").exists()
#         return False