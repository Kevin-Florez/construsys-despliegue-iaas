# authentication/utils.py
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from Clientes.models import Cliente
from Roles_Permisos.models import Permiso

User = get_user_model()

def get_tokens_for_user(user_instance):
    refresh = RefreshToken.for_user(user_instance)
    access_token = refresh.access_token

    rol_nombre = "Desconocido"
    privileges_codenames = []
    user_type = None
    full_name = "" 

    if isinstance(user_instance, User):
        user_type = "system_user"
        full_name = f"{user_instance.first_name} {user_instance.last_name}".strip()
        
        if user_instance.is_superuser:
            rol_nombre = "Superadmin"
            privileges_codenames = list(Permiso.objects.values_list('codename', flat=True))
        elif hasattr(user_instance, 'rol') and user_instance.rol and user_instance.rol.activo:
            rol_nombre = user_instance.rol.nombre
            privileges_codenames = list(user_instance.rol.permisos.values_list('codename', flat=True))
        else:
            rol_nombre = "Usuario sin rol"

    elif isinstance(user_instance, Cliente):
        user_type = "cliente"
        rol_nombre = "Cliente"
        full_name = f"{user_instance.nombre} {user_instance.apellido or ''}".strip()
        privileges_codenames = []

    # Añadimos nuestros datos personalizados al payload del token
    access_token['user_type'] = user_type
    access_token['rol'] = rol_nombre
    access_token['privileges'] = privileges_codenames
    access_token['full_name'] = full_name 
    access_token['nombre'] = user_instance.first_name if hasattr(user_instance, 'first_name') else user_instance.nombre
    
    
    access_token['must_change_password'] = getattr(user_instance, 'must_change_password', False)

    return {
        'refresh': str(refresh),
        'access': str(access_token),
    }