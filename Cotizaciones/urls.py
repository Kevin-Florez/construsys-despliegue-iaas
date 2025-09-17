# Cotizaciones/urls.py

from django.urls import path
from .views import (
    CotizacionCreateView,
    MisCotizacionesListView,
    CotizacionRetrieveView,
    ConvertirCotizacionAPedidoView,
    AdminCotizacionListView,
    AdminCotizacionDetailView,
    AdminCotizacionCreateView, 
    AdminCotizacionPDFView, 
)

urlpatterns = [
    # --- URLs para Clientes e Invitados ---
    
    # POST /api/cotizaciones/crear/ -> Crea una nueva cotización desde el carrito
    path('crear/', CotizacionCreateView.as_view(), name='cotizacion-crear'),
    
    # GET /api/cotizaciones/mis-cotizaciones/ -> Lista las cotizaciones del cliente logueado
    path('mis-cotizaciones/', MisCotizacionesListView.as_view(), name='cotizaciones-cliente-list'),
    
    # GET /api/cotizaciones/ver/<uuid:token_acceso>/ -> Muestra una cotización por token
    path('ver/<uuid:token_acceso>/', CotizacionRetrieveView.as_view(), name='cotizacion-retrieve-by-token'),
    
    # POST /api/cotizaciones/convertir/<uuid:token_acceso>/ -> Convierte cotización a pedido
    path('convertir/<uuid:token_acceso>/', ConvertirCotizacionAPedidoView.as_view(), name='cotizacion-convertir-a-pedido'),

    # --- URLs para el Panel de Administración ---

    # GET /api/cotizaciones/admin/ -> Lista todas las cotizaciones para el admin
    path('admin/', AdminCotizacionListView.as_view(), name='admin-cotizacion-list'),

    path('admin/crear/', AdminCotizacionCreateView.as_view(), name='admin-cotizacion-crear'),

    # GET /api/cotizaciones/admin/<int:pk>/ -> Muestra una cotización específica al admin
    path('admin/<int:pk>/', AdminCotizacionDetailView.as_view(), name='admin-cotizacion-detail'),

    path('admin/<int:pk>/pdf/', AdminCotizacionPDFView.as_view(), name='admin-cotizacion-pdf'),
]