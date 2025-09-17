# authentication/serializers.py
from rest_framework import serializers
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from Clientes.models import Cliente
from django.core.validators import RegexValidator
from rest_framework.validators import UniqueValidator 
from django.core.exceptions import ValidationError as DjangoCoreValidationError

from django.core.mail import send_mail
from django.conf import settings

User = get_user_model()

class UnifiedLoginSerializer(serializers.Serializer):
    correo = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)

    def validate(self, data):
        correo = data.get('correo')
        password = data.get('password')

        if not correo or not password:
            raise serializers.ValidationError('Debe proporcionar tanto el correo electrónico como la contraseña.')

        # El backend de autenticación personalizado debería manejar la búsqueda por 'correo' para ambos modelos
        user_or_cliente = authenticate(request=self.context.get('request'), correo=correo, password=password)

        if user_or_cliente is None:
            raise serializers.ValidationError('Correo o contraseña incorrectos.')

        is_account_active = False
        account_type_for_message = "de la cuenta"

        if isinstance(user_or_cliente, User): # Si es un usuario del sistema (admin, empleado)
            is_account_active = user_or_cliente.is_active
            account_type_for_message = "de usuario del sistema"
        elif isinstance(user_or_cliente, Cliente): # Si es un Cliente
            is_account_active = user_or_cliente.activo
            account_type_for_message = "de cliente"
        else:
            # Esto no debería ocurrir si authenticate funciona como se espera
            raise serializers.ValidationError('Tipo de usuario no reconocido después de la autenticación.')

        if not is_account_active:
            raise serializers.ValidationError(f'Tu cuenta {account_type_for_message} ha sido desactivada. Por favor, contacta al administrador.')

        data['user'] = user_or_cliente # Contiene el objeto User o Cliente
        return data

class AdminUserRegistrationSerializer(serializers.ModelSerializer):
    
    password2 = serializers.CharField(style={'input_type': 'password'}, write_only=True)
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password', 'password2')
        extra_kwargs = { 'password': {'write_only': True} }
    def validate(self, data):
        if data['password'] != data['password2']:
            raise serializers.ValidationError({"password2": "Las contraseñas no coinciden."})
        validate_password(data['password'])
        return data
    def create(self, validated_data):
        validated_data.pop('password2')
        user = User.objects.create_user(**validated_data)
        return user


class ClienteRegistrationSerializer(serializers.ModelSerializer): # Para auto-registro de clientes
    password2 = serializers.CharField(write_only=True, style={'input_type': 'password'})
    nombre = serializers.CharField(
        max_length=100,
        validators=[RegexValidator(regex=r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', message='El nombre solo debe contener letras y espacios.')]
    )
    apellido = serializers.CharField(
        max_length=100,
        validators=[RegexValidator(regex=r'^[a-zA-ZáéíóúÁÉÍÓÚñÑ\s]+$', message='El apellido solo debe contener letras y espacios.')]
    )
    correo = serializers.EmailField(
        validators=[UniqueValidator(queryset=Cliente.objects.all(), message="Este correo electrónico ya está registrado.")]
    )
    telefono = serializers.CharField(
        max_length=20, min_length=7,
        validators=[RegexValidator(regex=r'^[0-9]{7,15}$', message='El teléfono debe contener entre 7 y 15 dígitos.')]
    )
    documento = serializers.CharField(
        max_length=30, min_length=6,
        validators=[
            RegexValidator(regex=r'^[0-9]{6,20}$', message='El documento debe contener entre 6 y 20 dígitos.'),
            UniqueValidator(queryset=Cliente.objects.all(), message="Este número de documento ya está registrado.")
        ]
    )
    
    direccion = serializers.CharField(max_length=200, min_length=3, error_messages={'min_length': 'La dirección debe tener al menos 3 caracteres.'})

    class Meta:
        model = Cliente
        fields = [
            'nombre', 'apellido', 'correo', 'telefono',
            'tipo_documento', 'documento', 'direccion',
            'password', 'password2'
        ]
        extra_kwargs = {
            'password': {'write_only': True, 'min_length': 8}
        }

    def validate(self, data):
        if data.get('password') != data.get('password2'):
            raise serializers.ValidationError({"password2": "Las contraseñas no coinciden."})
        if 'password' in data:
            try:
                validate_password(data['password'])
            except DjangoCoreValidationError as e:
                raise serializers.ValidationError({"password": list(e.messages)})
        return data

    def create(self, validated_data):
        validated_data.pop('password2', None)
        password = validated_data.pop('password')
        # En auto-registro, 'must_change_password' se queda en su default (False)
        cliente = Cliente(**validated_data)
        cliente.set_password(password) 
        cliente.save()


        try:
            subject = '¡Bienvenido/a a ConstruSys!'
            message_body = (
                f"Hola {cliente.nombre},\n\n"
                f"¡Gracias por registrarte en ConstruSys! Tu cuenta ha sido creada exitosamente.\n\n"
                f"Ya puedes iniciar sesión con tu correo electrónico y la contraseña que elegiste.\n"
                f"Visítanos en: http://localhost:5173/login\n\n" 
                f"Si tienes alguna pregunta o necesitas asistencia, no dudes en contactarnos.\n\n"
                f"Saludos cordiales,\nEl equipo de ConstruSys"
            )
            send_mail(
                subject,
                message_body,
                settings.DEFAULT_FROM_EMAIL, # email remitente configurado en settings.py
                [cliente.correo], # El correo del cliente recién registrado
                fail_silently=False 
            )
            print(f"INFO (ClienteRegistrationSerializer.create): Correo de bienvenida ENVIADO a {cliente.correo}")
        except Exception as e:
            # Es importante loggear este error para saber si algo falló con el envío del correo
            print(f"ERROR (ClienteRegistrationSerializer.create): No se pudo enviar el correo de bienvenida a {cliente.correo}. Causa: {str(e)}")
            # A pesar del error de correo, el cliente ya fue creado.
        
       

        return cliente

class SolicitudReseteoPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)