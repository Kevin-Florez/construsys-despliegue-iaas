# authentication/jwt_auth.py
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.conf import settings
from django.contrib.auth import get_user_model
from Clientes.models import Cliente
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed

User = get_user_model()

class CustomJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        """
        Sobrescribe el método para leer el 'user_type' del token
        y buscar en la tabla correcta, evitando la colisión de IDs.
        """
        try:
            user_id = validated_token[settings.SIMPLE_JWT['USER_ID_CLAIM']]
            # ✨ INICIO DE LA CORRECCIÓN: Leemos nuestro campo personalizado
            user_type = validated_token.get('user_type') 
        except KeyError:
            raise InvalidToken('El token no contiene una identificación de usuario reconocible.')

        # ✨ Buscamos en la tabla correcta basándonos en 'user_type'
        if user_type == 'system_user':
            try:
                user = User.objects.get(pk=user_id)
                if self.user_can_authenticate(user):
                    return user
            except User.DoesNotExist:
                pass # El error se lanzará al final
        
        elif user_type == 'cliente':
            try:
                cliente = Cliente.objects.get(pk=user_id)
                if cliente.activo: # Verificamos si el cliente está activo
                    return cliente
            except Cliente.DoesNotExist:
                pass # El error se lanzará al final
        
        # Si el user_type es desconocido o el usuario no se encontró, lanzamos un error.
        raise AuthenticationFailed('Usuario no encontrado o no activo.', code='user_not_found')
    
    def user_can_authenticate(self, user):
        is_active = getattr(user, "is_active", None)
        return is_active or is_active is None