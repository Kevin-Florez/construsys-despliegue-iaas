# Proveedores/models.py
from django.db import models

class Proveedor(models.Model):
    TIPO_DOCUMENTO_CHOICES = [
        ('CC', 'Cédula de Ciudadanía (C.C)'),
        ('TI', 'Tarjeta de Identidad (T.I)'),
        ('CE', 'Cédula de Extranjería'),
        ('PPT', 'Permiso por Protección Temporal'),
        ('Pasaporte', 'Pasaporte'),
        ('NIT', 'Número de Identificación Tributaria (NIT)'),
    ]
    ESTADO_CHOICES = [
        ('Activo', 'Activo'),
        ('Inactivo', 'Inactivo'),
    ]
    nombre = models.CharField(max_length=200, verbose_name="Nombre del proveedor")
    tipo_documento = models.CharField(
        max_length=20, # Suficiente para 'Pasaporte', 'PPT'
        choices=TIPO_DOCUMENTO_CHOICES,
        verbose_name="Tipo de documento"
    )
    documento = models.CharField(max_length=30, unique=True, verbose_name="Número de documento")
    telefono = models.CharField(max_length=20, verbose_name="Teléfono")
    # ✨ NUEVO CAMPO CORREO ✨
    correo = models.EmailField(max_length=254, blank=True, null=True, verbose_name="Correo Electrónico")
    direccion = models.CharField(max_length=255, verbose_name="Dirección")
    contacto = models.CharField(max_length=100, blank=True, null=True, verbose_name="Nombre del contacto")
    estado = models.CharField(
        max_length=10,
        choices=ESTADO_CHOICES,
        default='Activo',
        verbose_name="Estado"
    )
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de registro")

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Proveedor"
        verbose_name_plural = "Proveedores"
        ordering = ['nombre']