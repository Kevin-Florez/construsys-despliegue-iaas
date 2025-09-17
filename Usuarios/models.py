# Usuarios/models.py

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils.translation import gettext_lazy as _

# Se elimina la importación directa de modelos de otras apps
# from Roles_Permisos.models import Rol

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('El campo Email es obligatorio'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))
        extra_fields.setdefault('rol', None)
        return self.create_user(email, password, **extra_fields)

class CustomUser(AbstractBaseUser, PermissionsMixin):
    TIPO_DOCUMENTO_CHOICES = [('CC', 'Cédula de Ciudadanía'), ('TI', 'Tarjeta de Identidad'), ('CE', 'Cédula de Extranjería'), ('NIT', 'NIT'), ('PAS', 'Pasaporte'), ('PPT', 'Permiso por Protección Temporal')]
    
    email = models.EmailField(_("dirección de correo electrónico"), unique=True, help_text=_("Requerido. Usado para el inicio de sesión."), error_messages={'unique': _("Ya existe un usuario con este correo electrónico.")})
    first_name = models.CharField(_('nombres'), max_length=150, blank=True)
    last_name = models.CharField(_('apellidos'), max_length=150, blank=True)
    is_staff = models.BooleanField(_('es staff'), default=False, help_text=_('Designa si el usuario puede iniciar sesión en el sitio de administración de Django.'))
    is_active = models.BooleanField(_('activo'), default=True, help_text=_('Designa si este usuario debe ser tratado como activo. Desmarque esto en lugar de eliminar cuentas.'))
    date_joined = models.DateTimeField(_('fecha de registro'), auto_now_add=True)

    # Se usa un string para la relación
    rol = models.ForeignKey(
        'Roles_Permisos.Rol',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Rol del Usuario"),
        related_name="usuarios"
    )
    
    must_change_password = models.BooleanField(default=False, verbose_name=_("Debe Cambiar Contraseña"))
    tipo_documento = models.CharField(_("tipo de documento"), max_length=3, choices=TIPO_DOCUMENTO_CHOICES, blank=True, null=True)
    numero_documento = models.CharField(_("número de documento"), max_length=20, blank=True, null=True, unique=True)
    telefono = models.CharField(_("teléfono"), max_length=20, blank=True, null=True)
    direccion = models.CharField(_("dirección"), max_length=255, blank=True, null=True)

    objects = CustomUserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    def __str__(self):
        return self.email
    
    def has_privilege(self, privilege_code_name):
        if self.is_superuser:
            return True
        if not self.rol:
            return False
        return self.rol.privilegios.filter(codigo=privilege_code_name).exists()

    class Meta:
        verbose_name = "Usuario del Sistema"
        verbose_name_plural = "Usuarios del Sistema"
        ordering = ['email']