# authentication/urls.py
from django.urls import path
from .views import (
    UnifiedLoginView,
    RegistrationView,
    ClienteRegistrationView,
    
    UnifiedPasswordResetRequestView,    
    UnifiedPasswordResetConfirmView,   
    
    CheckEmailView,
)
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('login/', UnifiedLoginView.as_view(), name='unified_login'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    
    path('register/admin/', RegistrationView.as_view(), name='admin_user_registration'),
    path('register/', ClienteRegistrationView.as_view(), name='cliente_public_register'),

    # Verificación de Email (sin cambios)
    path('check-email/', CheckEmailView.as_view(), name='check_email'),

 

    # Añadimos las nuevas rutas genéricas
    path('password/reset/', UnifiedPasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password/reset/confirm/<uuid:token>/', UnifiedPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
   
]