# Usuarios/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password as django_validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from Roles_Permisos.models import Rol
from django.core.mail import send_mail
from django.conf import settings
import secrets

User = get_user_model()

class RolAsignadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rol
        fields = ['id', 'nombre', 'activo']

class UsuarioSerializer(serializers.ModelSerializer):
    rol = RolAsignadoSerializer(read_only=True)
    rol_id = serializers.PrimaryKeyRelatedField(
        queryset=Rol.objects.all(),
        write_only=True,
        source='rol',
        allow_null=True,
        required=False
    )
    activo = serializers.BooleanField(source='is_active')

    class Meta:
        model = User
        fields = [
            'id', 'first_name', 'last_name', 'email',
            'rol', 'rol_id', 'activo', 'must_change_password',
            'tipo_documento', 'numero_documento', 'telefono', 'direccion'
        ]
        read_only_fields = ['id', 'must_change_password']

class UsuarioCreateSerializer(serializers.ModelSerializer):
    rol = serializers.PrimaryKeyRelatedField(
        queryset=Rol.objects.filter(activo=True),
        allow_null=True,
        required=False
    )
    email = serializers.EmailField(required=True)
    tipo_documento = serializers.ChoiceField(choices=User.TIPO_DOCUMENTO_CHOICES, required=False, allow_blank=True, allow_null=True)
    numero_documento = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    direccion = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = [
            'email', 'first_name', 'last_name', 'rol',
            'tipo_documento', 'numero_documento', 'telefono', 'direccion'
        ]
        extra_kwargs = {
            'first_name': {'required': True, 'allow_blank': False},
            'last_name': {'required': True, 'allow_blank': False},
        }

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Un usuario con este correo electrónico ya existe.")
        return value
    

    def validate_numero_documento(self, value):
        if User.objects.filter(numero_documento=value).exists():
            raise serializers.ValidationError("Ya existe un usuario con este número de documento.")
        return value


    # ✨ --- INICIO DE LA CORRECCIÓN --- ✨
    def create(self, validated_data):
        temp_password = secrets.token_urlsafe(10)

        # 1. Extraemos el email del diccionario. Esto lo obtiene Y lo elimina.
        email = validated_data.pop('email')
        
        # 2. Ahora validated_data ya no tiene la clave 'email', por lo que no hay duplicados.
        user = User.objects.create_user(
            email=email,
            password=temp_password,
            **validated_data
        )
        user.must_change_password = True
        user.save()

        # Lógica de envío de correo (sin cambios)
        subject = 'Bienvenido/a - Credenciales de Acceso al Sistema'
        message = (
            f'Hola {user.first_name},\n\n'
            f'Se ha creado una cuenta para ti en nuestro sistema.\n'
            f'Usuario (para iniciar sesión): {user.email}\n'
            f'Contraseña Temporal: {temp_password}\n\n'
            'Por favor, inicia sesión y el sistema te guiará para cambiar tu contraseña.\n'
            f"Puede iniciar sesión en: http://localhost:5173/login\n\n"
            f"Saludos cordiales,\nEl equipo del Sistema"
        )
        try:
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
        except Exception as e:
            print(f"ALERTA: Email de bienvenida no pudo ser enviado a {user.email}. Error: {e}")

        return user
    # ✨ --- FIN DE LA CORRECCIÓN --- ✨

class UsuarioUpdateSerializer(serializers.ModelSerializer):
    rol = serializers.PrimaryKeyRelatedField(
        queryset=Rol.objects.all(), allow_null=True, required=False
    )
    activo = serializers.BooleanField(source='is_active', required=False)
    tipo_documento = serializers.ChoiceField(choices=User.TIPO_DOCUMENTO_CHOICES, required=False, allow_blank=True, allow_null=True)
    numero_documento = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True, allow_null=True)
    direccion = serializers.CharField(max_length=255, required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'email', 'rol', 'activo',
            'tipo_documento', 'numero_documento', 'telefono', 'direccion'
        ]
        read_only_fields = ['email']

    def validate_numero_documento(self, value):
        if value and self.instance:
            if User.objects.filter(numero_documento=value).exclude(pk=self.instance.pk).exists():
                raise serializers.ValidationError("Este número de documento ya está en uso por otro usuario.")
        elif value and not self.instance:
            if User.objects.filter(numero_documento=value).exists():
                raise serializers.ValidationError("Este número de documento ya está en uso.")
        return value

class CambiarContrasenaSerializer(serializers.Serializer):
    password_actual = serializers.CharField(required=True, write_only=True, style={'input_type': 'password'})
    password_nuevo = serializers.CharField(required=True, write_only=True, style={'input_type': 'password'}, min_length=8)
    password_nuevo_confirmacion = serializers.CharField(required=True, write_only=True, style={'input_type': 'password'})

    def validate_password_nuevo(self, value):
        try:
            django_validate_password(value, user=self.context.get('user'))
        except DjangoValidationError as e:
            raise serializers.ValidationError(list(e.messages))
        return value

    def validate(self, data):
        if data['password_nuevo'] != data['password_nuevo_confirmacion']:
            raise serializers.ValidationError({"password_nuevo_confirmacion": "Las nuevas contraseñas no coinciden."})
        return data

class UserProfileSerializer(serializers.ModelSerializer):
    rol_nombre = serializers.CharField(source='rol.nombre', read_only=True, default='N/A')
    tipo_documento_display = serializers.CharField(source='get_tipo_documento_display', read_only=True)

    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'rol_nombre',
            'tipo_documento', 'tipo_documento_display', 'numero_documento',
            'telefono', 'direccion'
        ]
        read_only_fields = ['id', 'email', 'rol_nombre', 'tipo_documento_display']

class UserProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'telefono', 'direccion',
        ]
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
            'telefono': {'required': False},
            'direccion': {'required': False},
        }