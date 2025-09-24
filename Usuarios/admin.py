# Usuarios/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser

class CustomUserAdmin(UserAdmin):
    """
    Configuración para mostrar el CustomUser en el panel de administración de Django.
    """
    model = CustomUser

    list_display = ('email', 'first_name', 'last_name', 'rol', 'is_staff', 'is_active')
    list_filter = ('is_staff', 'is_active', 'rol')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)

    # ✨ INICIO DE LA CORRECCIÓN
    # 1. Definimos los campos que solo se pueden ver, pero no editar.
    readonly_fields = ('last_login', 'date_joined')

    # 2. Quitamos la sección 'Fechas Importantes' del formulario de edición.
    fieldsets = (
        (None, {'fields': ('email', 'password')}), 
        ('Información Personal', {'fields': ('first_name', 'last_name', 'rol', 'tipo_documento', 'numero_documento', 'telefono', 'direccion')}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        # La línea de 'Fechas Importantes' ha sido eliminada.
        ('Seguridad', {'fields': ('must_change_password',)}),
    )
    # ✨ FIN DE LA CORRECCIÓN
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password', 'password2'),
        }),
    )

admin.site.register(CustomUser, CustomUserAdmin)