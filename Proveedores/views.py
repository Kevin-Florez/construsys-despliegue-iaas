# backend_api/Proveedores/views.py

from rest_framework import generics, permissions
from .models import Proveedor
from .serializers import ProveedorSerializer
# ✨ 1. Importamos la nueva clase de permiso y eliminamos la antigua
from Roles_Permisos.permissions import HasPrivilege
from rest_framework.exceptions import ValidationError

class ProveedorListCreateView(generics.ListCreateAPIView):
    queryset = Proveedor.objects.all().order_by('nombre')
    serializer_class = ProveedorSerializer
    # ✨ 2. Reemplazamos el sistema de permisos
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]

    # ✨ 3. Definimos los privilegios para cada acción
    def get_required_privilege(self, method):
        if method == 'GET':
            return 'proveedores_ver'
        if method == 'POST':
            return 'proveedores_crear'
        return None

    def get_queryset(self):
        """
        Sobrescribe el queryset base para permitir filtrar por estado 'Activo'.
        Si el frontend envía '?estado=Activo', solo se devolverán proveedores activos.
        De lo contrario, se devuelven todos.
        """
        queryset = Proveedor.objects.all()
        
        estado_param = self.request.query_params.get('estado')

        if estado_param and estado_param == 'Activo':
            queryset = queryset.filter(estado='Activo')
            
        return queryset.order_by('nombre')

class ProveedorRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Proveedor.objects.all()
    serializer_class = ProveedorSerializer
    # ✨ 2. Reemplazamos el sistema de permisos
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]

    # ✨ 3. Definimos los privilegios para cada acción
    def get_required_privilege(self, method):
        if method == 'GET':
            return 'proveedores_ver'
        if method in ['PUT', 'PATCH']:
            return 'proveedores_editar'
        if method == 'DELETE':
            return 'proveedores_eliminar'
        return None
    

    def perform_destroy(self, instance):
        # related_name="compras" en el modelo Compra
        if instance.compras.exists():
            raise ValidationError("Este proveedor no puede ser eliminado porque tiene compras asociadas. Desactívelo en su lugar.")
        instance.delete()