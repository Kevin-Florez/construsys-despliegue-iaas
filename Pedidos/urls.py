# Pedidos/urls.py

from django.urls import path
from .views import (
    PedidoListCreateView, 
    AdminPedidoListView, 
    AdminPedidoDetailView,
    GuestPedidoStatusView,
    GuestPedidoLookupView,
    AgregarComprobanteView,
    UnirCarritosView,
    ActualizarCarritoView,
    CarritoActivoView,
    # ✨ NUEVA VISTA: Para la consulta de pedidos por cliente (invitado)
    ClientePedidoListView,
    PedidoDetailView
)

urlpatterns = [
    # URLs para clientes y creación de pedidos
    path('pedidos/', PedidoListCreateView.as_view(), name='pedido-list-create'),


    path('pedidos/<int:pk>/', PedidoDetailView.as_view(), name='pedido-detail'),

    path('carrito/unir/', UnirCarritosView.as_view(), name='unir-carritos'),
    path('carrito/actualizar/', ActualizarCarritoView.as_view(), name='actualizar-carrito'),
    path('carrito/activo/', CarritoActivoView.as_view(), name='carrito-activo'),

    # URLs para el flujo de seguimiento de invitados
    path('pedidos/ver/<uuid:token_seguimiento>/', GuestPedidoStatusView.as_view(), name='guest-pedido-status'),
    path('pedidos/consultar/', GuestPedidoLookupView.as_view(), name='guest-pedido-lookup'),
    
    # ✨ NUEVA URL: Consulta de pedidos por documento
    path('pedidos/consulta-documento/', ClientePedidoListView.as_view(), name='cliente-pedido-list'),

    # NUEVA URL para que el cliente pueda subir más comprobantes
    path('pedidos/ver/<uuid:token_seguimiento>/agregar-comprobante/', AgregarComprobanteView.as_view(), name='guest-agregar-comprobante'),

    # URLs para el administrador
    path('admin/pedidos/', AdminPedidoListView.as_view(), name='admin-pedido-list'),
    path('admin/pedidos/<int:pk>/', AdminPedidoDetailView.as_view(), name='admin-pedido-detail'),
]