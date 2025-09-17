# Roles_Permisos/serializers.py
from rest_framework import serializers
from .models import Rol, Permiso

class PermisoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permiso
        # ✅ CORRECCIÓN: Añadir 'codename' y 'modulo' a los campos
        fields = ['id', 'nombre', 'codename', 'modulo']
        read_only_fields = ['id', 'codename', 'modulo']

class RolSerializer(serializers.ModelSerializer):
    permisos = PermisoSerializer(many=True, read_only=True)
    permisos_ids = serializers.PrimaryKeyRelatedField(
        queryset=Permiso.objects.all(),
        many=True,
        write_only=True,
        source='permisos',
        required=False
    )
    usuarios_asignados_count = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Rol
        fields = [
            'id', 'nombre', 'descripcion', 'activo', # ✅ Se añade 'descripcion'
            'permisos',
            'permisos_ids',
            'usuarios_asignados_count'
        ]
        read_only_fields = ['id', 'permisos']

    def get_usuarios_asignados_count(self, obj_rol_instance):
        # Esta función está correcta
        if hasattr(obj_rol_instance, 'usuarios') and obj_rol_instance.usuarios is not None:
            return obj_rol_instance.usuarios.count()
        return 0