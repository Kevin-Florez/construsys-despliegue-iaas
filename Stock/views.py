# backend/Stock/views.py

from rest_framework import generics, permissions
from .models import BajaDeStock
from .serializers import (
    BajaDeStockReadSerializer,
    BajaDeStockCreateSerializer,
)
from Roles_Permisos.permissions import HasPrivilege

class BajaDeStockListView(generics.ListCreateAPIView):
    queryset = BajaDeStock.objects.select_related('producto').all()
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return BajaDeStockCreateSerializer
        return BajaDeStockReadSerializer

    def get_required_privilege(self, method):
        if method == 'GET': return 'stock_ver_bajas'
        if method == 'POST': return 'stock_registrar_baja'
        return None