# Clientes/admin.py
from django.contrib import admin
from .models import Cliente

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'apellido', 'correo', 'documento', 'telefono', 'activo', 'fecha_registro')
    search_fields = ('nombre', 'apellido', 'correo', 'documento')
    list_filter = ('activo', 'tipo_documento', 'fecha_registro')
    readonly_fields = ('fecha_registro', 'password')
