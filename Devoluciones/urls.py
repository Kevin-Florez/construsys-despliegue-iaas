# backend_api/Devoluciones/urls.py

from django.urls import path
from .views import (
    DatosVentaParaDevolucionView,
    DevolucionListCreateView, # Vista unificada
    EnviarDevolucionAProveedorView,
    ConfirmarRecepcionProveedorView
)

urlpatterns = [
    path('venta-original/<int:pk>/', DatosVentaParaDevolucionView.as_view(), name='devolucion-datos-venta'),
    
    # --- RUTA PRINCIPAL ---
    # Ahora esta URL acepta GET (para listar) y POST (para crear)
    path('', DevolucionListCreateView.as_view(), name='devolucion-list-create'),
    
    # --- ACCIONES ---
    path('<int:devolucion_pk>/enviar-a-proveedor/', EnviarDevolucionAProveedorView.as_view(), name='devolucion-enviar-proveedor'),
    path('gestion-proveedor/<int:pk>/confirmar-recepcion/', ConfirmarRecepcionProveedorView.as_view(), name='devolucion-confirmar-recepcion'),
]