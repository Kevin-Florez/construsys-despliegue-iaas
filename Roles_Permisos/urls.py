from django.urls import path
from . import views

urlpatterns = [
    path('roles/', views.RolListCreateView.as_view(), name='rol-list-create'),
    path('roles/<int:pk>/', views.RolRetrieveUpdateDestroyView.as_view(), name='rol-retrieve-update-destroy'),
    path('permisos/', views.PermisoListCreateView.as_view(), name='permiso-list-create'),
    path('permisos/<int:pk>/', views.PermisoRetrieveUpdateDestroyView.as_view(), name='permiso-retrieve-update-destroy'),
]