# Roles_Permisos/models.py
from django.db import models

class Permiso(models.Model):
    # ✨ --- INICIO DE CAMPOS MODIFICADOS --- ✨
    nombre = models.CharField(
        max_length=100,
        verbose_name="Nombre legible del Permiso",
        help_text="Un nombre descriptivo y legible para humanos. Ej: Crear Venta"
    )
    codename = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Codename",
        help_text="El identificador único usado en el código. Ej: ventas_crear"
    )
    modulo = models.CharField(
        max_length=50,
        verbose_name="Módulo",
        help_text="El módulo al que pertenece este permiso. Ej: Ventas"
    )
    # ✨ --- FIN DE CAMPOS MODIFICADOS --- ✨

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Permiso"
        verbose_name_plural = "Permisos"
        # Ordenar por módulo y luego por nombre para una mejor visualización en el admin
        ordering = ['modulo', 'nombre']

class Rol(models.Model):
    # --- ESTE MODELO NO NECESITA NINGÚN CAMBIO ---
    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nombre del rol",
        error_messages={
            'unique': "Ya existe un rol con este nombre. Por favor, elija un nombre diferente."
        }
    )
    descripcion = models.TextField(
        verbose_name="Descripción del rol",
        blank=True
    )
    es_protegido = models.BooleanField(
        default=False,
        verbose_name="Rol Protegido",
        help_text="Los roles protegidos no se pueden eliminar desde el panel de administración."
    )
    permisos = models.ManyToManyField(Permiso, related_name='roles', verbose_name="Permisos", blank=True)
    activo = models.BooleanField(default=True, verbose_name="Activo")

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Roles"
        ordering = ['nombre']