# backend_api/settings.py
"""
Django settings for backend_api project.
# ... (resto de tus comentarios y configuraciones iniciales) ...
"""
from dotenv import load_dotenv
import os # <<< --- AÑADE ESTA IMPORTACIÓN SI USAS os.path.join más abajo

load_dotenv()


from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent




# --- CONFIGURACIÓN A PRUEBA DE ERRORES PARA SUPABASE STORAGE ---

# 1. Leemos las variables de entorno de Vercel
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
SUPABASE_BUCKET = os.environ.get('SUPABASE_BUCKET')
SUPABASE_PROJECT_ID = os.environ.get('SUPABASE_PROJECT_ID')

# 2. Verificación "a prueba de fallos"
# Si alguna de las variables no existe, detenemos el programa con un error claro.
if not all([SUPABASE_KEY, SUPABASE_BUCKET, SUPABASE_PROJECT_ID]):
    raise ValueError(
        "ERROR CRÍTICO: Faltan una o más variables de entorno de Supabase. "
        "Verifica que SUPABASE_KEY, SUPABASE_BUCKET, y SUPABASE_PROJECT_ID existan en Vercel."
    )

# 3. Si todas las variables existen, procedemos a configurar el almacenamiento
print("✅ Todas las variables de Supabase detectadas. Configurando DEFAULT_FILE_STORAGE...")

# settings.py - CORRECTO
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'

AWS_ACCESS_KEY_ID = SUPABASE_PROJECT_ID
AWS_SECRET_ACCESS_KEY = SUPABASE_KEY
AWS_STORAGE_BUCKET_NAME = SUPABASE_BUCKET
AWS_S3_ENDPOINT_URL = f'https://{SUPABASE_PROJECT_ID}.supabase.co/storage/v1'
AWS_S3_OBJECT_PARAMETERS = {
    'CacheControl': 'max-age=86400',
}
AWS_DEFAULT_ACL = 'public-read'
AWS_QUERYSTRING_AUTH = False

print("✅ DEFAULT_FILE_STORAGE configurado para usar S3Boto3Storage.")


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'

# backend_api/settings.py
ALLOWED_HOSTS = ['192.168.167.94', 'localhost', '127.0.0.1', '.vercel.app']


# Application definition

INSTALLED_APPS = [
    "corsheaders",
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.humanize',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_filters',
    'rest_framework',
    'rest_framework_simplejwt', 
    'drf_spectacular',

    'storages',

    'authentication.apps.AuthenticationConfig',
    'Productos.apps.ProductosConfig',
    'Clientes.apps.ClientesConfig',
    'Compras.apps.ComprasConfig',
    'Cotizaciones.apps.CotizacionesConfig',
    'Creditos.apps.CreditosConfig',
    'Devoluciones.apps.DevolucionesConfig',
    'Proveedores.apps.ProveedoresConfig',
    'Roles_Permisos.apps.Roles_PermisosConfig',
    'Usuarios.apps.UsuariosConfig',
    'Ventas.apps.VentasConfig',
    'Configuracion.apps.ConfiguracionConfig',
    'Pedidos.apps.PedidosConfig',
    'Stock.apps.StockConfig',
]


# backend_api/settings.py
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'authentication.jwt_auth.CustomJWTAuthentication',
    ],
    # AÑADE ESTO:
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

AUTHENTICATION_BACKENDS = [
    # 1. Django intentará autenticar primero como Usuario del sistema.
    'authentication.backends.UsuarioBackend',
    
    # 2. Si falla, intentará autenticar como Cliente.
    'authentication.backends.ClienteBackend',
]


from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=1440),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Para desarrollo está bien, en producción sé más restrictivo

CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173", # <<< ---  puerto de tu React App
    # "http://localhost:3000", # Si usaras el puerto 3000
]

ROOT_URLCONF = 'backend_api.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend_api.wsgi.application'


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': os.environ.get('DB_PORT'),
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'construsys2025@gmail.com'
EMAIL_HOST_PASSWORD = 'puju drtr tsgx ifmw' 
DEFAULT_FROM_EMAIL = 'construsys2025@gmail.com'


AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

AUTH_USER_MODEL = 'Usuarios.CustomUser'

LANGUAGE_CODE = 'es-co' # Ajustado a español Colombia

TIME_ZONE = 'America/Bogota' # Ajustado a la zona horaria de Colombia

USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'

STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'

# Define la ruta en el disco duro donde se guardarán los archivos subidos.
#MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
PASSWORD_RESET_TIMEOUT_SECONDS = 3600


# settings.py
FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5173')


TASA_IVA = 19.0

CORS_ALLOW_ALL_ORIGINS = True 

# backend_api/settings.py (reemplaza tu bloque de Supabase al final del archivo)




# settings.py (al final de todo el archivo)

print("--- VERIFICACIÓN DE CONFIGURACIÓN ---")
print(f"MODO DEBUG: {DEBUG}")
print(f"ALMACENAMIENTO POR DEFECTO: {DEFAULT_FILE_STORAGE}")
print("---------------------------------")