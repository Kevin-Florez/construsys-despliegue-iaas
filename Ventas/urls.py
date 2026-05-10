# Ventas/urls.py
from django.urls import path
from .views import (
    ResumenGeneralDashboardView,
    VentaListCreateView,
    VentaRetrieveUpdateDestroyView,
    VentasCompletadasPorClienteView,
    GenerarVentaPDFView,
    MobileDashboardView
)

urlpatterns = [
    # --- RUTA PARA EL DASHBOARD ---
    path('resumen-general-dashboard/', ResumenGeneralDashboardView.as_view(), name='resumen-general-dashboard'),
    
    path('admin/dashboard/mobile/', MobileDashboardView.as_view(), name='mobile-dashboard'),
    # --- RUTAS PARA EL CRUD DE VENTAS ---
    path('', VentaListCreateView.as_view(), name='venta-list-create'),
    path('<int:pk>/', VentaRetrieveUpdateDestroyView.as_view(), name='venta-detail'),
    
    # --- OTRAS RUTAS ---
    path('cliente/<int:cliente_pk>/completadas_con_items/', VentasCompletadasPorClienteView.as_view(), name='ventas-completadas-por-cliente'),
    path('<int:venta_id>/pdf/', GenerarVentaPDFView.as_view(), name='venta-pdf'),
]
