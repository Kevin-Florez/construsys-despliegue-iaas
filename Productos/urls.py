# backend_api/Productos/urls.py

from django.urls import path
from .views import (
    CatalogoPublicoView, 
    CatalogoClienteView,
    ProductosStockSummaryView,
    ProductoListCreateView,
    ProductoRetrieveUpdateDestroyView,
    CategoriaProductoListCreateView,
    CategoriaProductoRetrieveUpdateDestroyView, 
    MarcaListCreateView, 
    MarcaRetrieveUpdateDestroyView,
)

urlpatterns = [
    path('public/catalogo/', CatalogoPublicoView.as_view(), name='catalogo-publico'),
    path('cliente/catalogo/', CatalogoClienteView.as_view(), name='catalogo-cliente'),
    path('resumen-stock/', ProductosStockSummaryView.as_view(), name='producto-stock-summary'),
    
    path('productos/', ProductoListCreateView.as_view(), name='producto-list-create'),
    
    # --- INICIO DE CORRECCIÓN FINAL ---
    # Para la URL de detalle, especificamos explícitamente qué método HTTP
    # corresponde a cada acción estándar del ViewSet.
    path('productos/<int:pk>/', ProductoRetrieveUpdateDestroyView.as_view({
        'get': 'retrieve',
        'put': 'update',
        'patch': 'partial_update',
        'delete': 'destroy'
    }), name='producto-detail'),
    # --- FIN DE CORRECCIÓN FINAL ---
    
    # Esta línea ya era correcta y no necesita cambios.
    path('productos/<int:pk>/dar-de-baja/', ProductoRetrieveUpdateDestroyView.as_view({'post': 'dar_de_baja'}), name='producto-dar-de-baja'),
    
    path('categorias/', CategoriaProductoListCreateView.as_view(), name='categoria-producto-list-create'),
    path('categorias/<int:pk>/', CategoriaProductoRetrieveUpdateDestroyView.as_view(), name='categoria-producto-retrieve-update-destroy'),
    
    path('marcas/', MarcaListCreateView.as_view(), name='marca-list-create'),
    path('marcas/<int:pk>/', MarcaRetrieveUpdateDestroyView.as_view(), name='marca-detail'),
]