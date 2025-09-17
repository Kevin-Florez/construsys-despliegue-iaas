# Usuarios/urls.py
from django.urls import path
from . import views # views ahora solo tiene vistas relacionadas con CustomUser

urlpatterns = [

    path('perfil/', views.PerfilView.as_view(), name='user-profile'),

    path('usuarios/', views.UsuarioListCreateView.as_view(), name='usuario-list-create'),
    path('usuarios/<int:pk>/', views.UsuarioRetrieveUpdateDestroyView.as_view(), name='usuario-retrieve-update-destroy'),
    path('usuarios/cambiar-contrasena/', views.CambiarContrasenaView.as_view(), name='cambiar-contrasena'),
    # Las siguientes líneas se eliminan:
    # path('roles-usuarios/', views.RolListCreateView.as_view(), name='rol-usuario-list-create'),
    # path('roles-usuarios/<int:pk>/', views.RolRetrieveUpdateDestroyView.as_view(), name='rol-usuario-retrieve-destroy'),
]