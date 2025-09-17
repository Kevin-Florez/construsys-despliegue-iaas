from django.urls import path
from . import views

urlpatterns = [
    path('proveedores/', views.ProveedorListCreateView.as_view(), name='proveedor-list-create'),
    path('proveedores/<int:pk>/', views.ProveedorRetrieveUpdateDestroyView.as_view(), name='proveedor-retrieve-update-destroy'),
]