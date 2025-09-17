# Clientes/admin.py
from django.contrib import admin
from .models import Cliente

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'apellido', 'correo', 'documento', 'telefono', 'activo', 'fecha_registro')
    search_fields = ('nombre', 'apellido', 'correo', 'documento')
    list_filter = ('activo', 'tipo_documento', 'fecha_registro')
    readonly_fields = ('fecha_registro', 'password')

    # Si quieres poder ver los campos de reseteo pero no editarlos directamente:
    # fieldsets = (
    #     (None, {'fields': ('nombre', 'apellido', 'correo', 'telefono', 'activo')}),
    #     ('Información Documental', {'fields': ('tipo_documento', 'documento')}),
    #     ('Ubicación', {'fields': ('barrio', 'direccion')}),
    #     ('Seguridad', {'fields': ('password',)}), # Password se maneja por forms especiales
    #     ('Reseteo de Contraseña (Info)', {'fields': ('reset_password_token', 'reset_password_token_expiry'), 'classes': ('collapse',)}),
    #     ('Fechas', {'fields': ('fecha_registro',)}),
    # )

# No necesitas registrar ClientePasswordResetToken porque los campos están en Cliente.