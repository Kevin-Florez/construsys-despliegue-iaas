# backend_api/urls.py

from django.contrib import admin
from django.urls import path, include

from .views import ContactoView

# --- ✨ IMPORTACIONES PARA MEDIA FILES ✨ ---
from django.conf import settings
from django.conf.urls.static import static
# --- ✨ FIN IMPORTACIONES ✨ ---

from authentication.views import ProfileView, CheckDocumentoView
from Usuarios.views import CambiarContrasenaView

from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # --- Inclusiones de URLs de las Apps ---
    path('api/auth/', include('authentication.urls')),
    path('api/auth/check-documento/', CheckDocumentoView.as_view(), name='check-documento'),
    # Rutas que ya funcionaban bien
    path('api/clientes/', include('Clientes.urls')),
    path('api/cotizaciones/', include('Cotizaciones.urls')),
    path('api/roles-permisos/', include('Roles_Permisos.urls')),
    path('api/ventas/', include('Ventas.urls')),
    
    path('api/stock/', include('Stock.urls')),
    
    path('api/', include('Proveedores.urls')),
    path('api/', include('Productos.urls')),
    path('api/', include('Compras.urls')),
    path('api/', include('Devoluciones.urls')),
    path('api/', include('Usuarios.urls')),
    path('api/', include('Pedidos.urls')),
    path('api/devoluciones/', include('Devoluciones.urls')),
    
    path('api/creditos/', include('Creditos.urls')),
    

    # --- Rutas de Perfil ---
    path('api/perfil/', ProfileView.as_view(), name='vista_perfil'),
    path('api/perfil/cambiar-password/', CambiarContrasenaView.as_view(), name='perfil_cambiar_password'),



    path('api/contacto/', ContactoView.as_view(), name='contacto'),



    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    # Interfaz de Swagger:
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    # Interfaz de ReDoc:
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

# --- Servir archivos media en modo DEBUG ---
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) 