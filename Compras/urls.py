# Compras/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('compras/', views.CompraListCreateView.as_view(), name='compra-list-create'),
    path('compras/<int:pk>/', views.CompraRetrieveUpdateDestroyView.as_view(), name='compra-retrieve-update-destroy'),
    
    
    path('compras/<int:compra_id>/pdf/', views.GenerarCompraPDFView.as_view(), name='compra-pdf'),
]