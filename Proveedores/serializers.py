# Proveedores/serializers.py
from rest_framework import serializers
from .models import Proveedor

class ProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proveedor
        fields = [
            'id', 'nombre', 'tipo_documento', 'documento', 'telefono',
            'correo', 'direccion', 'contacto', 'estado', 'fecha_registro' # ✨ CORREO AÑADIDO AQUÍ ✨
        ]
        read_only_fields = ['id', 'fecha_registro']

    # ✨ Opcional: Añadir validación para el correo ✨
def validate_correo(self, value):
         if value and Proveedor.objects.filter(correo=value).exists():
              #Para actualizaciones, excluir el registro actual
             if self.instance and self.instance.correo == value:
                 pass # Es el mismo correo, no hay cambio o es el mismo registro
             else:
                 raise serializers.ValidationError("Este correo electrónico ya está registrado para otro proveedor.")
         return value