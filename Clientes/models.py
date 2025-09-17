# Clientes/models.py
from django.db import models
from django.contrib.auth.hashers import make_password, check_password
from django.utils import timezone
import uuid

# Definimos las opciones para el campo municipio

class Cliente(models.Model):
    TIPO_DOCUMENTO_CHOICES = [
        ('CC', 'Cédula de Ciudadanía'),
        ('CE', 'Cédula de Extranjería'),
        ('NIT', 'NIT (Empresa o Persona Natural)'),
        ('PAS', 'Pasaporte'),
        ('TI', 'Tarjeta de Identidad (Menor de edad)'),
        ('RC', 'Registro Civil (Menor de edad NUIP)'),
        ('PEP', 'Permiso Especial de Permanencia'),
        ('PPT', 'Permiso por Protección Temporal'),
    ]

    nombre = models.CharField(max_length=100, verbose_name="Nombre")
    apellido = models.CharField(max_length=100, verbose_name="Apellido")
    
    
    correo = models.EmailField(
        unique=True, 
        verbose_name="Correo electrónico",
        error_messages={
            'unique': "Un cliente con este correo electrónico ya existe. Por favor, ingrese uno diferente."
        }
    )
    telefono = models.CharField(max_length=20, verbose_name="Teléfono")
    tipo_documento = models.CharField(max_length=3, choices=TIPO_DOCUMENTO_CHOICES, verbose_name="Tipo de Documento")
    documento = models.CharField(
        max_length=30, 
        verbose_name="Número de Documento", 
        unique=True,
        error_messages={
            'unique': "Un cliente con este número de documento ya existe. Por favor, verifique."
        }
    )

    es_invitado_temporal = models.BooleanField(default=False, verbose_name="¿Es cliente temporal creado desde un pedido?")
    
    
    
    direccion = models.CharField(max_length=200, verbose_name="Dirección")
    activo = models.BooleanField(default=True, verbose_name="Activo")
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de registro")
    password = models.CharField(max_length=128, verbose_name="Contraseña")

    must_change_password = models.BooleanField(default=False, verbose_name="Debe cambiar contraseña")

    

    @property
    def is_active(self):
        return self.activo

    @property
    def is_authenticated(self):
        return True

    

    def get_tipo_documento_display(self):
        return dict(self.TIPO_DOCUMENTO_CHOICES).get(self.tipo_documento)

    def __str__(self):
        return f"{self.nombre} {self.apellido} - {self.correo}"
    
    
    def get_full_info_display(self):

        return f"{self.nombre} {self.apellido} ({self.tipo_documento} {self.documento})"

    class Meta:
        verbose_name = "Cliente"
        verbose_name_plural = "Clientes"
        ordering = ['apellido', 'nombre']

    def set_password(self, raw_password):
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password)