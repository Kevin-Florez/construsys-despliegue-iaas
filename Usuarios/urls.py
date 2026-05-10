# Usuarios/urls.py
from django.urls import path
from . import views 

urlpatterns = [

    path('perfil/', views.PerfilView.as_view(), name='user-profile'),

    path('usuarios/', views.UsuarioListCreateView.as_view(), name='usuario-list-create'),
    path('usuarios/<int:pk>/', views.UsuarioRetrieveUpdateDestroyView.as_view(), name='usuario-retrieve-update-destroy'),
    path('usuarios/cambiar-contrasena/', views.CambiarContrasenaView.as_view(), name='cambiar-contrasena'),
]
