# backend_api/Ventas/serializers.py

from rest_framework import serializers
from django.db import transaction
from decimal import Decimal
import json
import logging

from django.utils import timezone
# ✨ CORRECCIÓN 1: Importamos el modelo con su nuevo nombre
from .models import Venta, DetalleVenta
from Clientes.models import Cliente
from Productos.models import Producto
from Creditos.models import Credito
from Devoluciones.serializers import DevolucionReadSerializer

logger = logging.getLogger(__name__)

# ✨ CORRECCIÓN 2: Renombramos el serializador y su Meta.model
class DetalleVentaReadSerializer(serializers.ModelSerializer):
    # Usamos 'producto_nombre_historico' para asegurar que el nombre sea el del momento de la venta
    producto_nombre = serializers.CharField(source='producto_nombre_historico', read_only=True)
    # ✨ --- INICIO DE CAMBIOS --- ✨
    precio_final_unitario = serializers.DecimalField(
        source='precio_final_unitario_con_iva', 
        max_digits=12, 
        decimal_places=2, 
        read_only=True
    )
    # ✨ --- FIN DE CAMBIOS --- ✨

    class Meta:
        model = DetalleVenta
        # ✨ --- INICIO DE CAMBIOS --- ✨
        fields = ['id', 'producto_nombre', 'cantidad', 'precio_unitario_venta', 'iva_unitario', 'precio_final_unitario', 'costo_unitario_historico', 'subtotal']
        # ✨ --- FIN DE CAMBIOS --- ✨

class VentaReadSerializer(serializers.ModelSerializer):
    cliente_info = serializers.SerializerMethodField()
    resumen_productos = serializers.SerializerMethodField()
    resumen_pago = serializers.SerializerMethodField()
    es_ajustable = serializers.BooleanField(read_only=True)
    devolucion = DevolucionReadSerializer(read_only=True)

    # ✨ CORRECCIÓN CLAVE: Nos aseguramos de que los detalles se incluyan siempre
    # El related_name en el modelo Venta es 'detalles', así que esto funcionará
    detalles = DetalleVentaReadSerializer(many=True, read_only=True)
    
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    metodo_entrega_display = serializers.CharField(source='get_metodo_entrega_display', read_only=True)
    comprobante_pago_adicional_url = serializers.FileField(source='comprobante_pago_adicional', read_only=True, use_url=True)
    
    # Añadimos el ID del pedido de origen para referencia
    pedido_origen_id = serializers.PrimaryKeyRelatedField(source='pedido_origen', read_only=True)

    class Meta:
        model = Venta
        fields = [
            'id', 'fecha', 'cliente', 'cliente_info', 
            'subtotal', 'iva', 'total', 'estado', 'estado_display', 
            'metodo_entrega', 'metodo_entrega_display', 'direccion_entrega',
            'detalles', # Nos aseguramos de que 'detalles' esté en la lista de campos
            'resumen_productos',
            'credito_usado', 'monto_cubierto_con_credito', 
            'monto_pago_adicional', 'metodo_pago_adicional', 
            'resumen_pago',
            'comprobante_pago_adicional_url',
            'observaciones', 'es_ajustable', 'fecha_limite_ajuste',
            'devolucion',
            'pedido_origen_id',
            'fecha_creacion_registro', 'fecha_actualizacion_registro'
        ]
    
    def get_cliente_info(self, obj: Venta) -> str:
        if obj.cliente:
            doc_map = {
                'Cédula de Ciudadanía': 'C.C',
                'Tarjeta de Identidad (Menor de edad)': 'T.I', 
                'Cédula de Extranjería': 'C.E',
                'Pasaporte': 'PASS',
                'NIT': 'NIT',
            }
            tipo_doc_largo = obj.cliente.get_tipo_documento_display() or ''
            tipo_doc_corto = doc_map.get(tipo_doc_largo, tipo_doc_largo)
            doc = obj.cliente.documento or ''
            nombre_completo = f"{obj.cliente.nombre} {obj.cliente.apellido or ''}".strip()
            return f"{nombre_completo} ({tipo_doc_corto} {doc})"
        return "Cliente no especificado"

    def get_resumen_productos(self, obj: Venta) -> str:
        # ✨ CORRECCIÓN 5: Usamos obj.detalles.all() en lugar de obj.items.all()
        items_list = [f"{item.producto_nombre_historico} (x{item.cantidad})" for item in obj.detalles.all()]
        if not items_list:
            return "No hay productos en esta venta."
        resumen = ", ".join(items_list[:2])
        if len(items_list) > 2:
            resumen += f", y {len(items_list) - 2} más..."
        return resumen
        
    def get_resumen_pago(self, obj: Venta) -> str:
        partes = []
        if obj.monto_cubierto_con_credito > 0:
            partes.append(f"Crédito: ${obj.monto_cubierto_con_credito:,.0f}")
        if obj.monto_pago_adicional > 0 and obj.metodo_pago_adicional:
            partes.append(f"{obj.metodo_pago_adicional}: ${obj.monto_pago_adicional:,.0f}")
        if not partes:
            return "Pago pendiente"
        return " | ".join(partes)

class VentaCreateSerializer(serializers.ModelSerializer):
    items_json = serializers.CharField(write_only=True)
    cliente = serializers.PrimaryKeyRelatedField(queryset=Cliente.objects.filter(activo=True))
    credito_usado_id = serializers.PrimaryKeyRelatedField(
        queryset=Credito.objects.all(), source='credito_usado', required=False, allow_null=True
    )

    class Meta:
        model = Venta
        fields = [
            'fecha', 'cliente', 'estado', 'observaciones', 'items_json',
            'metodo_entrega', 'direccion_entrega',
            'credito_usado_id', 'monto_cubierto_con_credito',
            'monto_pago_adicional', 'metodo_pago_adicional', 'comprobante_pago_adicional'
        ]

    def validate(self, data):
        items_data_list = json.loads(data['items_json'])
        if not items_data_list:
            raise serializers.ValidationError({"items_json": "La venta debe tener al menos un producto."})
        
        cliente_obj = data.get('cliente')
        credito_obj = data.get('credito_usado')
        
        if credito_obj and cliente_obj and credito_obj.cliente.id != cliente_obj.id:
            raise serializers.ValidationError({"credito_usado_id": "El crédito seleccionado no pertenece al cliente de la venta."})
        
        if data.get('estado') == 'Completada':
            for item_data in items_data_list:
                try:
                    producto = Producto.objects.get(pk=item_data['producto_id'])
                    if producto.stock_actual < item_data['cantidad']:
                        raise serializers.ValidationError(f"Stock para '{producto.nombre}' insuficiente (disponible: {producto.stock_actual}).")
                except Producto.DoesNotExist:
                    raise serializers.ValidationError(f"El producto con ID {item_data['producto_id']} no existe.")
        return data

    @transaction.atomic
    def create(self, validated_data):
        items_data = json.loads(validated_data.pop('items_json'))
        final_estado = validated_data.get('estado', 'Completada')

        validated_data['estado'] = 'Pendiente'
        venta = Venta.objects.create(**validated_data)

        calculated_subtotal = Decimal('0.00')
        TASA_IVA = Decimal('0.19')

        for item_data in items_data:
            producto = Producto.objects.get(pk=item_data['producto_id'])
            precio_unitario = Decimal(item_data['precio_unitario_venta'])
            cantidad = item_data['cantidad']
            
            # ✨ --- INICIO DE CAMBIOS --- ✨
            iva_unitario_calculado = precio_unitario * TASA_IVA
            
            # Creamos la instancia del detalle de venta incluyendo el IVA por unidad
            DetalleVenta.objects.create(
                venta=venta,
                producto=producto,
                cantidad=cantidad,
                precio_unitario_venta=precio_unitario,
                iva_unitario=iva_unitario_calculado # Guardamos el IVA unitario
            )
            # ✨ --- FIN DE CAMBIOS --- ✨
            calculated_subtotal += (cantidad * precio_unitario)

        venta.subtotal = calculated_subtotal
        venta.iva = venta.subtotal * TASA_IVA
        venta.total = venta.subtotal + venta.iva
        
        venta.estado = final_estado
        
        venta.save()
        
        return venta

class VentaUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venta
        fields = ['estado', 'observaciones']

    def validate_estado(self, value):
        if self.instance and self.instance.estado == 'Completada' and value != 'Anulada':
            raise serializers.ValidationError("Una venta completada solo puede ser anulada.")
        if self.instance and self.instance.estado in ['Anulada', 'Pendiente'] and value == 'Anulada' and self.instance.estado != 'Completada':
            raise serializers.ValidationError("Solo se pueden anular ventas que han sido completadas.")
        return value

class ClienteDashboardSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.CharField(source='__str__', read_only=True)
    class Meta:
        model = Cliente
        fields = ['nombre_completo']

class VentaDashboardSerializer(serializers.ModelSerializer):
    cliente = ClienteDashboardSerializer(read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    class Meta:
        model = Venta
        fields = ['id', 'fecha', 'total', 'estado_display', 'cliente']