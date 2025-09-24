# authentication/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics, permissions
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password as django_validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import validate_email
from django.contrib.contenttypes.models import ContentType
import uuid
from datetime import timedelta 
from .models import PasswordResetToken
from .utils import get_tokens_for_user
from .serializers import (
    UnifiedLoginSerializer,
    AdminUserRegistrationSerializer,
    SolicitudReseteoPasswordSerializer,
    ClienteRegistrationSerializer as AuthClienteRegistrationSerializer
)
from Clientes.models import Cliente
from Usuarios.models import CustomUser # Importar CustomUser

from Usuarios.serializers import UserProfileSerializer, UserProfileUpdateSerializer
from Clientes.serializers import ClienteProfileSerializer, ClienteProfileUpdateSerializer
from rest_framework_simplejwt.tokens import AccessToken


User = get_user_model()

# -------------------- LOGIN UNIFICADO --------------------
class UnifiedLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = UnifiedLoginSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            user_or_cliente_instance = serializer.validated_data["user"]
            
            # La función get_tokens_for_user ahora hace todo el trabajo.
            tokens = get_tokens_for_user(user_or_cliente_instance)

            # La respuesta ahora solo devuelve los tokens, porque toda la información
            # necesaria ya está dentro del token de acceso.
            return Response(tokens, status=status.HTTP_200_OK)
            
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# -------------------- REGISTRO USUARIO (ADMIN/SISTEMA) --------------------
class RegistrationView(APIView):
    permission_classes = [permissions.IsAdminUser]
    def post(self, request):
        serializer = AdminUserRegistrationSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {"message": "Usuario del sistema registrado exitosamente."},
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# -------------------- REGISTRO CLIENTE (DESDE FRONTEND PÚBLICO) --------------------
class ClienteRegistrationView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = AuthClienteRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            cliente = serializer.save()
            try:
                subject = '¡Gracias por registrarte en ConstruSys!'
                message_body = (
                    f"Hola {cliente.nombre},\n\n"
                    f"Tu cuenta en ConstruSys ha sido creada exitosamente.\n\n"
                    f"Ya puedes iniciar sesión con tu correo y la contraseña que elegiste.\n"
                    f"Inicia sesión aquí: {settings.FRONTEND_URL}/login\n\n"
                    f"Saludos,\nEl equipo de ConstruSys"
                )
                send_mail(subject, message_body, settings.DEFAULT_FROM_EMAIL, [cliente.correo], fail_silently=True)
            except Exception as e:
                print(f"ERROR: No se pudo enviar correo de bienvenida (auto-registro) a {cliente.correo}. Causa: {str(e)}")

            return Response(
                {
                    "message": "Cliente registrado exitosamente. Ahora puede iniciar sesión.",
                    "cliente_id": cliente.id,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# -------------------- VERIFICACIÓN DE CORREO ELECTRÓNICO --------------------
class CheckEmailView(APIView):
    permission_classes = [permissions.AllowAny]
    def post(self, request):
        email = request.data.get('correo', None)
        if not email:
            return Response({'error': 'Se requiere el correo electrónico.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            validate_email(email)
        except DjangoValidationError:
            return Response({'error': 'Formato de correo electrónico inválido.'}, status=status.HTTP_400_BAD_REQUEST)

        user_exists = User.objects.filter(email__iexact=email).exists()
        cliente_exists = Cliente.objects.filter(correo__iexact=email).exists()

        if user_exists or cliente_exists:
            return Response({'error': 'Este correo electrónico ya está registrado.'}, status=status.HTTP_409_CONFLICT)
        else:
            return Response({'message': 'Correo electrónico disponible.'}, status=status.HTTP_200_OK)


# -------------------- RECUPERAR CONTRASEÑA (CLIENTE) - Solicitud --------------------
class UnifiedPasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = SolicitudReseteoPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"].lower()
        user_or_cliente = None
        user_type_name = "usuario" # Nombre genérico

        # 1. Buscar primero en el modelo de Usuarios del sistema (CustomUser)
        user_found = User.objects.filter(email__iexact=email, is_active=True).first()
        if user_found:
            user_or_cliente = user_found
            user_type_name = f"{user_found.first_name} {user_found.last_name}"

        # 2. Si no se encontró, buscar en el modelo de Clientes
        else:
            cliente_found = Cliente.objects.filter(correo__iexact=email, activo=True).first()
            if cliente_found:
                user_or_cliente = cliente_found
                user_type_name = f"{cliente_found.nombre} {cliente_found.apellido}"

        # 3. Si encontramos un usuario o cliente activo, generamos el token y enviamos el correo
        if user_or_cliente:
            try:
                # Borramos tokens antiguos para este usuario para evitar confusiones
                PasswordResetToken.objects.filter(
                    content_type=ContentType.objects.get_for_model(user_or_cliente),
                    object_id=user_or_cliente.id
                ).delete()

                # Creamos el nuevo token
                token_instance = PasswordResetToken.objects.create(content_object=user_or_cliente)
                
                # La URL del frontend debe ser genérica ahora
                reset_url = f"{settings.FRONTEND_URL}/reset-password/{token_instance.token}"
                
                subject = "Restablecer su Contraseña - ConstruSys"
                message = (
                    f"Hola {user_type_name},\n\n"
                    f"Ha solicitado restablecer su contraseña para ConstruSys. "
                    f"Haga clic en el siguiente enlace o cópielo en su navegador para continuar:\n\n"
                    f"{reset_url}\n\n"
                    f"Este enlace es válido por 1 hora.\n\n"
                    f"Si usted no solicitó este cambio, por favor ignore este correo electrónico.\n\n"
                    f"Atentamente,\nEl equipo de ConstruSys"
                )
                
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    
                    [user_or_cliente.email if isinstance(user_or_cliente, User) else user_or_cliente.correo],
                    fail_silently=False
                )
            except Exception as e:
                print(f"Error en UnifiedPasswordResetRequestView al enviar correo: {str(e)}")
                # No devolvemos el error al cliente por seguridad, pero lo registramos
        
        # Por seguridad, SIEMPRE devolvemos el mismo mensaje, exista o no el correo.
        # Esto previene que alguien pueda adivinar qué correos están registrados.
        return Response({
            "message": "Si su correo electrónico está registrado y activo, recibirá un mensaje con instrucciones."
        }, status=status.HTTP_200_OK)

# -------------------- RECUPERAR CONTRASEÑA (CLIENTE) - Confirmación --------------------
class UnifiedPasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, token):
        # 1. Validar la contraseña nueva
        password_nuevo = request.data.get("password_nuevo")
        password_nuevo_confirmacion = request.data.get("password_nuevo_confirmacion")

        if not password_nuevo or not password_nuevo_confirmacion:
            return Response({"error": "La nueva contraseña y su confirmación son requeridas."}, status=status.HTTP_400_BAD_REQUEST)
        
        if password_nuevo != password_nuevo_confirmacion:
            return Response({"error_password_confirmacion": ["Las nuevas contraseñas no coinciden."]}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Buscar el token y el usuario asociado
        try:
            token_instance = PasswordResetToken.objects.select_related('content_type').get(token=token)
        except (PasswordResetToken.DoesNotExist, DjangoValidationError): # DjangoValidationError para UUID mal formados
            return Response({"error": "El enlace de restablecimiento es inválido o ha expirado."}, status=status.HTTP_400_BAD_REQUEST)

        # 3. Verificar si el token ha expirado (1 hora)
        if token_instance.created_at < timezone.now() - timedelta(hours=1):
            token_instance.delete() # Limpiamos el token expirado
            return Response({"error": "El enlace de restablecimiento es inválido o ha expirado."}, status=status.HTTP_400_BAD_REQUEST)

        # 4. Obtener el usuario/cliente real desde el token
        user_or_cliente = token_instance.content_object
        if not user_or_cliente:
             token_instance.delete()
             return Response({"error": "Usuario asociado al token no encontrado."}, status=status.HTTP_404_NOT_FOUND)

        # 5. Validar la fortaleza de la contraseña y guardarla
        try:
            django_validate_password(password_nuevo, user=user_or_cliente)
            user_or_cliente.set_password(password_nuevo)
            
            # Si el usuario tenía la bandera de "debe cambiar contraseña", la quitamos
            if hasattr(user_or_cliente, 'must_change_password'):
                user_or_cliente.must_change_password = False
            
            user_or_cliente.save()
            
            # 6. Eliminar el token una vez usado
            token_instance.delete()

            return Response({"message": "Contraseña restablecida exitosamente."}, status=status.HTTP_200_OK)

        except DjangoValidationError as e:
            return Response({"error_password": list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print(f"Error en UnifiedPasswordResetConfirmView: {str(e)}")
            return Response({"error": "Ocurrió un error al restablecer la contraseña."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ProfileView(APIView):
    """
    Vista para que el usuario/cliente autenticado
    pueda ver y actualizar su propio perfil.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self, user_instance, update=False):
        """ Devuelve la clase de serializer apropiada. """
        if isinstance(user_instance, User):
            return UserProfileUpdateSerializer if update else UserProfileSerializer
        elif isinstance(user_instance, Cliente):
            return ClienteProfileUpdateSerializer if update else ClienteProfileSerializer
        return None

    def get(self, request):
        """ Devuelve la información del perfil del usuario/cliente logueado. """
        user = request.user
        SerializerClass = self.get_serializer_class(user, update=False)

        if SerializerClass:
            serializer = SerializerClass(user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response(
                {"error": "Tipo de usuario no reconocido."},
                status=status.HTTP_400_BAD_REQUEST
            )

    def put(self, request):
        """ Actualiza la información del perfil del usuario/cliente logueado. """
        user = request.user
        SerializerClass = self.get_serializer_class(user, update=True)
        ReadSerializerClass = self.get_serializer_class(user, update=False)

        if not SerializerClass or not ReadSerializerClass:
            return Response(
                {"error": "Tipo de usuario no reconocido."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = SerializerClass(user, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            # Devolver el perfil actualizado usando el serializer de lectura
            read_serializer = ReadSerializerClass(user)
            return Response(read_serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request):
        """ Permite actualizaciones parciales (funciona igual que PUT con partial=True). """
        return self.put(request)




class CheckDocumentoView(APIView):
    """
    Una vista para verificar si un número de documento ya existe.
    """
    permission_classes = [permissions.AllowAny] # Cualquiera puede verificar al registrarse

    def post(self, request, *args, **kwargs):
        tipo_documento = request.data.get('tipo_documento')
        documento = request.data.get('documento')

        if not tipo_documento or not documento:
            return Response(
                {'error': 'Se requieren el tipo y el número de documento.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Buscamos si ya existe un cliente con esa combinación
        if Cliente.objects.filter(tipo_documento=tipo_documento, documento=documento).exists():
            return Response(
                {'error': 'Este número de documento ya está registrado.'},
                status=status.HTTP_409_CONFLICT # 409 Conflict es un buen código para "ya existe"
            )
        
        return Response(
            {'message': 'Documento disponible.'},
            status=status.HTTP_200_OK
        )