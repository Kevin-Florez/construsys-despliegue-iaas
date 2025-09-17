# Cotizaciones/permissions.py
from rest_framework import permissions


class PuedeGestionarCotizaciones(permissions.BasePermission):
    def has_permission(self, request, view):
        
        return request.user and request.user.is_authenticated 

