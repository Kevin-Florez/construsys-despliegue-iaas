# backend_api/Devoluciones/serializers.py

from rest_framework import serializers
from django.db import transaction
from decimal import Decimal
from .models import Devolucion, ItemDevuelto, ItemCambio
from Ventas.models import Venta, DetalleVenta
from Productos.models import Producto
from Creditos.models import Credito
from rest_framework.exceptions import ValidationError
from Clientes.models import Cliente
from Stock.serializers import GestionProveedorReadSerializer
# --- FIN DE CAMBIOS ---

# --- INICIO DE CAMBIOS: Nuevo Serializador Mínimo para el Cliente ---
class MiniClienteSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.SerializerMethodField()
    tipo_documento_display_corto = serializers.SerializerMethodField()

    class Meta:
        model = Cliente
        fields = ['id', 'nombre_completo', 'tipo_documento_display_corto', 'documento']

    def get_nombre_completo(self, obj):
        return f"{obj.nombre} {obj.apellido or ''}".strip()

    def get_tipo_documento_display_corto(self, obj):
        doc_map = { 'Cédula de Ciudadanía': 'CC', 'NIT': 'NIT', 'Cédula de Extranjería': 'CE', 'Pasaporte': 'PASS' }
        return doc_map.get(obj.get_tipo_documento_display(), '')

class ItemDevueltoReadSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    motivo_display = serializers.CharField(source='get_motivo_display', read_only=True)

    class Meta:
        model = ItemDevuelto
        fields = ['id', 'producto_nombre', 'cantidad', 'precio_unitario_historico', 'subtotal', 'motivo', 'motivo_display', 'devuelto_a_proveedor']

class ItemCambioReadSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)

    class Meta:
        model = ItemCambio
        fields = ['id', 'producto_nombre', 'cantidad', 'precio_unitario_actual', 'subtotal']

class DevolucionReadSerializer(serializers.ModelSerializer):
    # --- INICIO DE CAMBIOS: Usar el nuevo serializador para el cliente ---
    cliente = MiniClienteSerializer(read_only=True)
    gestion_proveedor = GestionProveedorReadSerializer(read_only=True) # Incluimos la gestión aquí
    # --- FIN DE CAMBIOS ---
    
    items_devueltos = ItemDevueltoReadSerializer(many=True, read_only=True)
    items_cambio = ItemCambioReadSerializer(many=True, read_only=True)
    tipo_reembolso_display = serializers.CharField(source='get_tipo_reembolso_display', read_only=True)
    estado_del_cambio_display = serializers.CharField(source='get_estado_del_cambio_display', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    
    class Meta:
        model = Devolucion
        fields = [
            'id', 'venta_original', 'cliente', 'fecha_devolucion', 'motivo_general', 
            'total_productos_devueltos', 'total_productos_cambio', 'balance_final', 
            'tipo_reembolso_display', 'estado', 'estado_display',
            'items_devueltos', 'items_cambio',
            'estado_del_cambio', 'estado_del_cambio_display',
            'gestion_proveedor' # Añadimos el campo de la gestión con proveedor
        ]

class ItemDevueltoCreateSerializer(serializers.Serializer):
    item_venta_original_id = serializers.IntegerField(required=True)
    cantidad_a_devolver = serializers.IntegerField(required=True, min_value=1)
    motivo = serializers.ChoiceField(choices=ItemDevuelto.MotivoDevolucion.choices, required=True)

class ItemCambioCreateSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField(required=True)
    cantidad = serializers.IntegerField(required=True, min_value=1)
    precio_unitario_actual = serializers.DecimalField(required=True, max_digits=10, decimal_places=2, min_value=Decimal('0.01'))

class DevolucionCreateSerializer(serializers.ModelSerializer):
    venta_original_id = serializers.IntegerField(write_only=True, required=True)
    items_devueltos = ItemDevueltoCreateSerializer(many=True, write_only=True, required=True)
    items_cambio = ItemCambioCreateSerializer(many=True, write_only=True, required=False)
    
    tipo_reembolso = serializers.ChoiceField(
        choices=[choice for choice in Devolucion.TIPO_REEMBOLSO_CHOICES if choice[0] != 'SIN_REEMBOLSO'], 
        required=False, write_only=True
    )
    
    # IMPLEMENTACIÓN: Nuevo campo para recibir el método de pago desde el frontend
    metodo_pago_adicional = serializers.ChoiceField(
        choices=Devolucion.METODO_PAGO_ADICIONAL_CHOICES, 
        required=False, write_only=True
    )

    estado_del_cambio = serializers.ChoiceField(choices=Devolucion.ESTADO_CAMBIO_CHOICES, required=True, write_only=True)

    class Meta:
        model = Devolucion
        fields = [
            'id', 'venta_original_id', 'motivo_general', 'items_devueltos', 'items_cambio',
            'total_productos_devueltos', 'total_productos_cambio', 'balance_final', 'fecha_devolucion',
            'monto_abonado_credito', 'monto_reembolsado_efectivo',
            'tipo_reembolso', 'estado_del_cambio',
            'metodo_pago_adicional' # IMPLEMENTACIÓN: Añadir campo a la lista
        ]
        read_only_fields = [
            'id', 'total_productos_devueltos', 'total_productos_cambio', 
            'balance_final', 'fecha_devolucion', 'monto_abonado_credito',
            'monto_reembolsado_efectivo'
        ]

    def validate_venta_original_id(self, value):
        try:
            venta = Venta.objects.get(pk=value)
            if hasattr(venta, 'devolucion'):
                raise serializers.ValidationError("Esta venta ya tiene una devolución registrada.")
        except Venta.DoesNotExist:
            raise serializers.ValidationError(f"La venta original con ID {value} no existe.")
        return venta
    
    # IMPLEMENTACIÓN: Validación para requerir método de pago o reembolso según el balance
    def validate(self, data):
        items_devueltos_data = data.get('items_devueltos', [])
        items_cambio_data = data.get('items_cambio', [])
        
        total_devolucion = sum(
            DetalleVenta.objects.get(pk=item['item_venta_original_id']).precio_unitario_venta * item['cantidad_a_devolver'] 
            for item in items_devueltos_data
        )
        total_cambio = sum(Decimal(item['precio_unitario_actual']) * item['cantidad'] for item in items_cambio_data)
        balance_provisional = total_cambio - total_devolucion

        if balance_provisional > 0 and 'metodo_pago_adicional' not in data:
            raise ValidationError({"metodo_pago_adicional": "Debe especificar un método de pago para el saldo a cargo del cliente."})
        
        if balance_provisional < 0 and 'tipo_reembolso' not in data:
             raise ValidationError({"tipo_reembolso": "Debe especificar cómo se gestionará el saldo a favor del cliente."})
        
        return data

    @transaction.atomic
    def create(self, validated_data):
        venta_original = validated_data.pop('venta_original_id')
        items_devueltos_data = validated_data.pop('items_devueltos', [])
        items_cambio_data = validated_data.pop('items_cambio', [])
        tipo_reembolso_elegido = validated_data.get('tipo_reembolso')
        metodo_pago_adicional_elegido = validated_data.get('metodo_pago_adicional')
        
        if not items_devueltos_data:
            raise serializers.ValidationError("Debe haber al menos un producto devuelto.")

        total_devolucion = sum(
            DetalleVenta.objects.get(pk=item['item_venta_original_id']).precio_unitario_venta * item['cantidad_a_devolver'] 
            for item in items_devueltos_data
        )
        total_cambio = sum(Decimal(item['precio_unitario_actual']) * item['cantidad'] for item in items_cambio_data)
        
        devolucion = Devolucion.objects.create(
            venta_original=venta_original, cliente=venta_original.cliente,
            total_productos_devueltos=total_devolucion, total_productos_cambio=total_cambio,
            motivo_general=validated_data.get('motivo_general'),
            estado_del_cambio=validated_data.get('estado_del_cambio')
        )

        for item_data in items_devueltos_data:
            item_original = DetalleVenta.objects.get(pk=item_data['item_venta_original_id'])
            producto_devuelto = item_original.producto
            cantidad_devuelta = item_data['cantidad_a_devolver']
            motivo = item_data['motivo']
            
            ItemDevuelto.objects.create(
                devolucion=devolucion, producto=producto_devuelto, cantidad=cantidad_devuelta,
                precio_unitario_historico=item_original.precio_unitario_venta, motivo=motivo
            )
            
            # --- INICIO DE CAMBIOS ---
            # Solo se reabastece si el motivo lo permite.
            # Los productos defectuosos NO reabastecen el stock aquí. Quedan pendientes
            # para ser gestionados en el módulo de devoluciones a proveedor.
            if ItemDevuelto.puede_reabastecer(motivo):
                producto_devuelto.stock_actual += cantidad_devuelta
                producto_devuelto.save(update_fields=['stock_actual'])
            # --- FIN DE CAMBIOS ---

        for item_data in items_cambio_data:
            producto_nuevo = Producto.objects.get(pk=item_data['producto_id'])
            cantidad_nueva = item_data['cantidad']
            if producto_nuevo.stock_actual < cantidad_nueva:
                raise serializers.ValidationError(f"Stock insuficiente para el producto de cambio '{producto_nuevo.nombre}'.")
            
            ItemCambio.objects.create(
                devolucion=devolucion, producto=producto_nuevo, cantidad=cantidad_nueva,
                precio_unitario_actual=item_data['precio_unitario_actual']
            )
            producto_nuevo.stock_actual -= cantidad_nueva
            producto_nuevo.save(update_fields=['stock_actual'])

        if devolucion.balance_final < 0: # La empresa debe al cliente
            monto_a_favor_cliente = abs(devolucion.balance_final)
            if tipo_reembolso_elegido == 'AL_CREDITO':
                credito_activo = Credito.objects.filter(cliente=venta_original.cliente, estado='Activo').first()
                if not credito_activo:
                    raise serializers.ValidationError({"tipo_reembolso": "El cliente no tiene un crédito activo para abonar el saldo."})
                
                credito_activo.capital_utilizado = max(Decimal('0.00'), credito_activo.capital_utilizado - monto_a_favor_cliente)
                credito_activo.save(update_fields=['capital_utilizado'])
                devolucion.monto_abonado_credito = monto_a_favor_cliente
                devolucion.tipo_reembolso = 'AL_CREDITO'
            
            elif tipo_reembolso_elegido == 'EFECTIVO':
                devolucion.monto_reembolsado_efectivo = monto_a_favor_cliente
                devolucion.tipo_reembolso = 'EFECTIVO'
            
        elif devolucion.balance_final > 0: # El cliente debe a la empresa
            # IMPLEMENTACIÓN: Manejar el pago del cliente.
            monto_a_pagar_cliente = devolucion.balance_final
            devolucion.monto_pagado_adicional = monto_a_pagar_cliente
            devolucion.metodo_pago_adicional = metodo_pago_adicional_elegido

            if metodo_pago_adicional_elegido == 'CREDITO':
                credito_activo = Credito.objects.filter(cliente=venta_original.cliente, estado='Activo').first()
                if not credito_activo:
                    raise serializers.ValidationError({"metodo_pago_adicional": "El cliente no tiene un crédito activo para cubrir el saldo."})
                
                if credito_activo.saldo_disponible_para_ventas < monto_a_pagar_cliente:
                    raise serializers.ValidationError({"metodo_pago_adicional": f"Saldo de crédito insuficiente. Disponible: ${credito_activo.saldo_disponible_para_ventas:,.0f}"})

                credito_activo.capital_utilizado += monto_a_pagar_cliente
                credito_activo.save(update_fields=['capital_utilizado'])
                devolucion.credito_usado_para_pago = credito_activo
            devolucion.tipo_reembolso = 'SIN_REEMBOLSO'

        else: # Balance es cero
            devolucion.tipo_reembolso = 'SIN_REEMBOLSO'

        venta_original.tiene_devolucion = True
        venta_original.save(update_fields=['tiene_devolucion'])
        
        devolucion.save()
        return devolucion