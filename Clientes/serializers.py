# Clientes/serializers.py
from rest_framework import serializers
from .models import Cliente
from django.contrib.auth.hashers import make_password
from django.utils.crypto import get_random_string # Para generar contraseñas aleatorias
from django.core.mail import send_mail # Para enviar correos
from django.conf import settings # Para el remitente del correo

class ClienteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        required=False,
        allow_blank=True,
        style={'input_type': 'password'}
    )
    

    class Meta:
        model = Cliente
        fields = [
            'id', 'nombre', 'apellido', 'correo', 'telefono',
            'tipo_documento', 'documento', 'direccion',
            'activo', 'password', 'fecha_registro',
            'must_change_password'
        ]
        read_only_fields = ['id', 'fecha_registro']

    def create(self, validated_data):
        validated_data.pop('password', None)
        force_change = validated_data.pop('must_change_password', True)
        cliente = Cliente(**validated_data)
        temporary_password = get_random_string(10)
        cliente.set_password(temporary_password)
        cliente.must_change_password = force_change
        cliente.save()

        if cliente.must_change_password:
            try:
                subject = '¡Bienvenido/a a ConstruSys - Su cuenta ha sido creada!'
                message_body = (
                    f"Hola {cliente.nombre},\n\n"
                    f"Un administrador ha creado una cuenta para usted en ConstruSys.\n\n"
                    f"Puede iniciar sesión utilizando su correo electrónico ({cliente.correo}) y la siguiente contraseña temporal:\n"
                    f"Contraseña Temporal: {temporary_password}\n\n"
                    f"Por su seguridad, el sistema le pedirá que cambie esta contraseña inmediatamente después de iniciar sesión.\n"
                    f"Puede iniciar sesión en: http://localhost:5173/login\n\n"
                    f"Saludos cordiales,\nEl equipo de ConstruSys"
                )
                send_mail(
                    subject,
                    message_body,
                    settings.DEFAULT_FROM_EMAIL,
                    [cliente.correo],
                    fail_silently=False,
                )
            except Exception as e:
                print(f"ERROR: No se pudo enviar el correo de bienvenida a {cliente.correo}. Causa: {str(e)}")
        return cliente

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)
            instance.must_change_password = validated_data.get('must_change_password', False)
        else:
            instance.must_change_password = validated_data.get('must_change_password', instance.must_change_password)

        return super().update(instance, validated_data)


class ClienteLoginSerializer(serializers.Serializer):
    correo = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        correo = data.get('correo')
        password = data.get('password')

        try:
            cliente = Cliente.objects.get(correo__iexact=correo)
        except Cliente.DoesNotExist:
            raise serializers.ValidationError('Correo o contraseña incorrectos.')

        if not cliente.activo:
            raise serializers.ValidationError('Este cliente está inactivo.')

        if not cliente.check_password(password):
            raise serializers.ValidationError('Correo o contraseña incorrectos.')

        data['cliente'] = cliente
        return data




class ClienteProfileSerializer(serializers.ModelSerializer):
    """ Serializer para mostrar el perfil de un Cliente. """
    
    tipo_documento_display = serializers.CharField(source='get_tipo_documento_display', read_only=True)
    nombre_completo = serializers.SerializerMethodField() # 
    rol_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Cliente
        fields = [
            'id', 'correo', 'nombre', 'apellido', 'nombre_completo', 'rol_nombre', # 
            'tipo_documento', 'tipo_documento_display', 'documento',
            'telefono', 'direccion'
        ]
        
        read_only_fields = ['id', 'correo', 'rol_nombre', 'tipo_documento_display', 'tipo_documento', 'documento']
        

    def get_rol_nombre(self, obj):
        return "Cliente"
    
    def get_nombre_completo(self, obj): 
        return f"{obj.nombre} {obj.apellido}".strip()


class ClienteProfileUpdateSerializer(serializers.ModelSerializer):
    """ Serializer para actualizar el perfil de un Cliente (solo campos permitidos). """
    
    class Meta:
        model = Cliente
        fields = [
            'nombre', 'apellido',
            'telefono', 'direccion',
            
        ]
        extra_kwargs = {
            'nombre': {'required': False},
            'apellido': {'required': False},
            'telefono': {'required': False},
            'direccion': {'required': False},
        }




class ClienteLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = ['nombre', 'apellido', 'telefono', 'direccion', 'correo']