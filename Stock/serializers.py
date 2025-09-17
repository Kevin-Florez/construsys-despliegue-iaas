# backend_api/Stock/serializers.py

from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from .models import BajaDeStock, DevolucionAProveedor, ItemDevolucionAProveedor
from Productos.models import Producto
from Devoluciones.models import ItemDevuelto
from Proveedores.models import Proveedor # Asegúrate de que esta importación exista

# --- Serializers para Bajas de Stock (Sin cambios) ---
class BajaDeStockReadSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    motivo_display = serializers.CharField(source='get_motivo_display', read_only=True)

    class Meta:
        model = BajaDeStock
        fields = ['id', 'producto_nombre', 'cantidad', 'fecha_baja', 'motivo_display', 'descripcion']

class BajaDeStockCreateSerializer(serializers.ModelSerializer):
    producto_id = serializers.PrimaryKeyRelatedField(
        queryset=Producto.objects.filter(activo=True), source='producto', write_only=True
    )

    class Meta:
        model = BajaDeStock
        fields = ['producto_id', 'cantidad', 'motivo', 'descripcion']
    
    def validate(self, data):
        producto = data['producto']
        cantidad_baja = data['cantidad']
        if producto.stock_actual < cantidad_baja:
            raise serializers.ValidationError(f"Stock insuficiente para dar de baja. Stock actual de '{producto.nombre}': {producto.stock_actual}.")
        return data

    @transaction.atomic
    def create(self, validated_data):
        producto = validated_data['producto']
        cantidad_baja = validated_data['cantidad']
        producto.stock_actual -= cantidad_baja
        producto.save(update_fields=['stock_actual'])
        baja = BajaDeStock.objects.create(**validated_data)
        return baja

# --- Serializers para Devoluciones a Proveedor ---
class ItemGestionProveedorReadSerializer(serializers.ModelSerializer):
    producto_original_nombre = serializers.CharField(source='producto_original.nombre', read_only=True)
    producto_recibido_nombre = serializers.CharField(source='producto_recibido.nombre', read_only=True, allow_null=True)
    
    class Meta:
        model = ItemDevolucionAProveedor
        fields = ['id', 'producto_original_nombre', 'cantidad_enviada', 'cantidad_recibida', 'producto_recibido', 'producto_recibido_nombre', 'notas_recepcion', 'recepcion_confirmada']

class GestionProveedorReadSerializer(serializers.ModelSerializer):
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    items = ItemGestionProveedorReadSerializer(many=True, read_only=True)

    class Meta:
        model = DevolucionAProveedor
        fields = [
            'id', 'proveedor', 'proveedor_nombre',
            'fecha_envio', 'fecha_recepcion_final',  # 👈 añadir aquí
            'estado', 'estado_display', 'notas', 'items'
        ]


class ItemRecepcionSerializer(serializers.ModelSerializer):
    # Se añade 'id' para identificar el item
    id = serializers.IntegerField() 
    # Se hace explícito que producto_recibido puede ser nulo
    producto_recibido = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.all(), required=False, allow_null=True)

    class Meta:
        model = ItemDevolucionAProveedor
        fields = ['id', 'cantidad_recibida', 'producto_recibido', 'notas_recepcion']
        
class ConfirmarRecepcionSerializer(serializers.Serializer):
    items_recepcion = ItemRecepcionSerializer(many=True, required=True)
    notas = serializers.CharField(required=False, allow_blank=True, default='')


    fecha_recepcion_final = serializers.DateField(required=True, write_only=True)
    # --- INICIO DE CORRECCIÓN ---
    # Lógica de actualización completamente reescrita para ser más robusta.
    @transaction.atomic
    def update(self, instance, validated_data):
        items_data = validated_data.get('items_recepcion')
        instance.notas = validated_data.get('notas', instance.notas)
        
        items_a_actualizar = []
        productos_a_actualizar = {}

        for item_data in items_data:
            item_id = item_data.get('id')
            try:
                item_gestion = instance.items.get(id=item_id)
            except ItemDevolucionAProveedor.DoesNotExist:
                continue # Ignorar si el ID del item no corresponde a esta gestión



            cantidad_recibida = item_data.get('cantidad_recibida', 0)
            item_gestion.cantidad_recibida = cantidad_recibida
            item_gestion.producto_recibido = item_data.get('producto_recibido')
            item_gestion.notas_recepcion = item_data.get('notas_recepcion')
            item_gestion.recepcion_confirmada = True 
            items_a_actualizar.append(item_gestion)

            # 2. Prepara la actualización del stock
            if cantidad_recibida > 0:
                producto_a_ingresar = item_gestion.producto_recibido or item_gestion.producto_original
                if producto_a_ingresar.id not in productos_a_actualizar:
                    productos_a_actualizar[producto_a_ingresar.id] = {'instancia': producto_a_ingresar, 'cantidad_a_sumar': 0}
                productos_a_actualizar[producto_a_ingresar.id]['cantidad_a_sumar'] += cantidad_recibida
        
        # 3. Actualiza el stock
        if productos_a_actualizar:
            productos_qs = Producto.objects.select_for_update().filter(id__in=productos_a_actualizar.keys())
            for producto in productos_qs:
                producto.stock_actual += productos_a_actualizar[producto.id]['cantidad_a_sumar']
            Producto.objects.bulk_update(productos_qs, ['stock_actual'])

        # 4. Actualiza los items de la gestión
        ItemDevolucionAProveedor.objects.bulk_update(items_a_actualizar, ['cantidad_recibida', 'producto_recibido', 'notas_recepcion', 'recepcion_confirmada'])
        
        # 5. Determina el estado final de la gestión
        todos_recibidos_completamente = all(item.cantidad_recibida >= item.cantidad_enviada for item in instance.items.all())
        instance.estado = 'COMPLETADA' if todos_recibidos_completamente else 'RECIBIDO_PARCIAL'
        
        # ----> MODIFICA ESTA LÍNEA <----
        # Antes: instance.fecha_recepcion_final = timezone.localdate()
        # Ahora, usa la fecha que viene del frontend:
        instance.fecha_recepcion_final = validated_data.get('fecha_recepcion_final')

        instance.save()
        
        return instance