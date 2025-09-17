# backend_api/Creditos/urls.py

from django.urls import path
from . import views
from .views import ClienteHistorialCreditosView

urlpatterns = [
    # --- RUTAS DE CLIENTES (sin cambios) ---
    path('mi-credito/', views.ClienteCreditoDetailView.as_view(), name='cliente-credito-detail'),
    path('mi-credito/pdf/', views.ClienteGenerarCreditoPDFView.as_view(), name='cliente-credito-pdf'),
    path('mi-historial/', ClienteHistorialCreditosView.as_view(), name='cliente-credito-historial'),
    
    # --- RUTAS DE GESTIÓN DE CRÉDITOS EXISTENTES (ADMIN) ---
    path('', views.CreditoListCreateView.as_view(), name='credito-list'), # Ya no se usa para crear
    path('<int:pk>/', views.CreditoRetrieveUpdateDestroyView.as_view(), name='credito-detail'),
    path('<int:credito_pk>/abonos/', views.AbonoCreditoCreateView.as_view(), name='abono-create'),
    path('abonos/<int:abono_id>/verificar/', views.VerificarAbonoView.as_view(), name='verificar-abono'),
    path('<int:credito_id>/pdf/', views.GenerarCreditoPDFView.as_view(), name='credito-pdf'),
    path('resumen-dashboard/', views.CreditosResumenDashboardView.as_view(), name='creditos-resumen-dashboard'),

    # --- INICIO DE NUEVAS RUTAS PARA SOLICITUDES (ADMIN) ---
    path('solicitudes/', views.SolicitudCreditoListCreateView.as_view(), name='solicitud-list-create'),
    path('solicitudes/<int:pk>/', views.SolicitudCreditoDetailView.as_view(), name='solicitud-detail'),
    path('solicitudes/historial-cliente/<int:cliente_id>/', views.ClienteHistorialCreditosParaAdminView.as_view(), name='admin-cliente-historial'),
]