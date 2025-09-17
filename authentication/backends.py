# authentication/backends.py

from django.contrib.auth import get_user_model
from Clientes.models import Cliente

User = get_user_model()  # Tu CustomUser

class UsuarioBackend:
    """
    Autentica a un Usuario del sistema (admin, empleado) usando su email.
    Este backend solo conoce el modelo CustomUser.
    """
    def authenticate(self, request, username=None, correo=None, password=None, **kwargs):
        # Acepta 'username' (del admin de Django) o 'correo' (de tu API)
        email = username or correo
        if not email:
            return None
            
        try:
            user = User.objects.get(email=email)
            if user.check_password(password) and user.is_active:
                return user  # Autenticación exitosa para un Usuario del sistema
        except User.DoesNotExist:
            return None  # El usuario no existe en esta tabla, no hace nada más
        return None

    def get_user(self, user_id):
        """
        Obtiene una instancia de CustomUser a partir de su ID.
        Este método solo será llamado si este backend autenticó al usuario.
        """
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

class ClienteBackend:
    """
    Autentica a un Cliente de la tienda usando su correo.
    Este backend solo conoce el modelo Cliente.
    """
    def authenticate(self, request, username=None, correo=None, password=None, **kwargs):
        email = username or correo
        if not email:
            return None

        try:
            cliente = Cliente.objects.get(correo=email)
            # Usamos la propiedad 'is_active' que definiste en el modelo Cliente
            if cliente.check_password(password) and cliente.is_active:
                return cliente  # Autenticación exitosa para un Cliente
        except Cliente.DoesNotExist:
            return None # El cliente no existe, no hace nada más
        return None

    def get_user(self, user_id):
        """
        Obtiene una instancia de Cliente a partir de su ID.
        Este método solo será llamado si este backend autenticó al usuario.
        """
        try:
            return Cliente.objects.get(pk=user_id)
        except Cliente.DoesNotExist:
            return None