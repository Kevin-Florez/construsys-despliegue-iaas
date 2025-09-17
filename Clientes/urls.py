# Clientes/urls.py
from django.urls import path
from . import views
from .views import CheckClientByDocumentView, ClienteProfileView

urlpatterns = [
    path('', views.ClienteListCreateView.as_view(), name='cliente-list-create'),
    path('<int:pk>/', views.ClienteRetrieveUpdateDestroyView.as_view(), name='cliente-retrieve-update-destroy'),
    path('registro/', views.ClienteRegistroView.as_view(), name='cliente-registro'),
    path('login/', views.ClienteLoginView.as_view(), name='cliente-login'),

    path('<int:cliente_pk>/credito-info/', views.ClienteCreditoInfoView.as_view(), name='cliente-credito-info'),

    path('check-by-document/', CheckClientByDocumentView.as_view(), name='check-client-by-document'),

    path('mi-perfil/', ClienteProfileView.as_view(), name='cliente-profile'),
]
