# backend/Stock/urls.py

from django.urls import path
from .views import BajaDeStockListView

urlpatterns = [
    path('bajas/', BajaDeStockListView.as_view(), name='bajas-stock-list-create'),
]