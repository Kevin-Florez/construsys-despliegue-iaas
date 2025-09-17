# backend_api/Devoluciones/views.py

from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Devolucion
# --- INICIO DE CAMBIOS ---
# Se importa el modelo directamente para poder crearlo
from Stock.models import DevolucionAProveedor, ItemDevolucionAProveedor
# --- FIN DE CAMBIOS ---
from .serializers import DevolucionCreateSerializer, DevolucionReadSerializer
from Stock.serializers import ConfirmarRecepcionSerializer
from Ventas.models import Venta
from Ventas.serializers import VentaReadSerializer
from Roles_Permisos.permissions import HasPrivilege
from Proveedores.models import Proveedor
from django.shortcuts import get_object_or_404
from django.utils import timezone

class DatosVentaParaDevolucionView(generics.RetrieveAPIView):
    queryset = Venta.objects.all()
    serializer_class = VentaReadSerializer
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    required_privilege = "ventas_devolucion"

class DevolucionListCreateView(generics.ListCreateAPIView):
    # --- INICIO DE CORRECCIÓN ---
    # Se añade el ordenamiento por fecha de devolución (más recientes primero)
    # y luego por ID como segundo criterio de desempate.
    queryset = Devolucion.objects.select_related(
        'cliente', 'venta_original', 'gestion_proveedor__proveedor'
    ).prefetch_related(
        'items_devueltos__producto',
        'gestion_proveedor__items__producto_original',
        'gestion_proveedor__items__producto_recibido'
    ).order_by('-fecha_devolucion', '-id')
    # --- FIN DE CORRECCIÓN ---
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return DevolucionCreateSerializer
        return DevolucionReadSerializer

    def get_required_privilege(self, method):
        if method == 'GET':
            return "devoluciones_ver_devolucion_proveedor"
        if method == 'POST':
            return "ventas_devolucion"
        return None

class EnviarDevolucionAProveedorView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    required_privilege = "devoluciones_crear_devolucion_proveedor"

    def post(self, request, devolucion_pk):
        devolucion = get_object_or_404(Devolucion, pk=devolucion_pk)
        
        if hasattr(devolucion, 'gestion_proveedor'):
            return Response({"error": "Esta devolución ya tiene una gestión con proveedor iniciada."}, status=status.HTTP_400_BAD_REQUEST)
            
        items_defectuosos = devolucion.items_devueltos.filter(motivo='PRODUCTO_DEFECTUOSO')
        if not items_defectuosos.exists():
            return Response({"error": "Esta devolución no tiene productos marcados como defectuosos."}, status=status.HTTP_400_BAD_REQUEST)
        
        proveedor_id = request.data.get('proveedor_id')
        if not proveedor_id:
            return Response({"error": "Debe proporcionar un ID de proveedor."}, status=status.HTTP_400_BAD_REQUEST)
        
        proveedor = get_object_or_404(Proveedor, pk=proveedor_id)
        
        gestion = DevolucionAProveedor.objects.create(devolucion_origen=devolucion, proveedor=proveedor)
        for item in items_defectuosos:
            # --- INICIO DE CORRECCIÓN ---
            # Se crea el objeto 'ItemDevolucionAProveedor' directamente, que es la forma correcta.
            ItemDevolucionAProveedor.objects.create(
                gestion_proveedor=gestion,
                item_devuelto_origen=item,
                producto_original=item.producto,
                cantidad_enviada=item.cantidad
            )
            # --- FIN DE CORRECCIÓN ---
            item.devuelto_a_proveedor = True
            item.save(update_fields=['devuelto_a_proveedor'])
            
        gestion.estado = 'ENVIADA'
        gestion.fecha_envio = timezone.localdate()
        gestion.save()
        
        serializer = DevolucionReadSerializer(devolucion)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

class ConfirmarRecepcionProveedorView(generics.UpdateAPIView):
    queryset = DevolucionAProveedor.objects.all()
    serializer_class = ConfirmarRecepcionSerializer
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    required_privilege = "devoluciones_editar_devolucion_proveedor"

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.update(instance, serializer.validated_data)
        
        full_devolucion_serializer = DevolucionReadSerializer(instance.devolucion_origen)
        return Response(full_devolucion_serializer.data)