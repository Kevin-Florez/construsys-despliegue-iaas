# Pedidos/serializers.py

from rest_framework import serializers
from django.db import transaction
from decimal import Decimal
import json
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from rest_framework.exceptions import ValidationError

from .models import Pedido, DetallePedido, ComprobantePago 
from Productos.models import Producto
from Creditos.models import Credito
from Clientes.models import Cliente as ModeloCliente
from .emails import enviar_correo_confirmacion_pedido

class ComprobantePagoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComprobantePago
        fields = ['id', 'imagen', 'fecha_subida', 'monto_verificado', 'verificado']
        read_only_fields = ['id', 'fecha_subida']

class DetalleProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Producto
        fields = ['id', 'nombre', 'imagen_url']

class DetallePedidoSerializer(serializers.ModelSerializer):
    producto = DetalleProductoSerializer(read_only=True)
    subtotal = serializers.ReadOnlyField()
    class Meta:
        model = DetallePedido
        fields = ['id', 'producto', 'cantidad', 'precio_unitario', 'subtotal']

class ClientePedidoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModeloCliente
        fields = ['id', 'nombre', 'correo']

class PedidoSerializer(serializers.ModelSerializer):
    productos = serializers.CharField(write_only=True, required=True)
    detalles = DetallePedidoSerializer(many=True, read_only=True)
    cliente = ClientePedidoSerializer(read_only=True)
    comprobantes = ComprobantePagoSerializer(many=True, read_only=True)
    comprobantes_iniciales = serializers.ListField(
        child=serializers.ImageField(allow_empty_file=False, use_url=False),
        write_only=True,
        required=False
    )
    
    # ✨ --- INICIO DEL CAMBIO ---
    # Añadimos un campo para saber si se usó crédito.
    # Es un campo de solo lectura que se calcula en el momento.
    fue_pagado_con_credito = serializers.SerializerMethodField()
    # ✨ --- FIN DEL CAMBIO ---
    
    credito_usado_id = serializers.PrimaryKeyRelatedField(
        queryset=Credito.objects.all(),
        source='credito_usado',
        write_only=True,
        required=False,
        allow_null=True
    )

    class Meta:
        model = Pedido
        fields = [
            'id', 'cliente', 'fecha_creacion', 
            'subtotal', 'iva', 'total', 
            'estado', 'metodo_entrega', 'nombre_receptor', 'telefono_receptor', 
            'direccion_entrega', 'credito_usado_id', 'monto_usado_credito',
            # ✨ --- INICIO DEL CAMBIO ---
            'fue_pagado_con_credito', # Añadimos el nuevo campo a la lista
            # ✨ --- FIN DEL CAMBIO ---
            'productos', 'detalles', 'token_seguimiento',
            'email_invitado',
            'tipo_documento_invitado',
            'documento_invitado', 
            'monto_pagado_verificado', 'motivo_cancelacion', 
            'comprobantes', 'comprobantes_iniciales'
        ]
        read_only_fields = [
            'id', 'fecha_creacion', 'subtotal', 'iva', 'total', 
            'token_seguimiento', 'detalles', 'cliente', 'comprobantes',
            'monto_pagado_verificado', 'monto_usado_credito',
            # ✨ --- INICIO DEL CAMBIO ---
            'fue_pagado_con_credito' # Lo marcamos como solo lectura
            # ✨ --- FIN DEL CAMBIO ---
        ]
    
    # ✨ --- INICIO DEL CAMBIO ---
    # Esta función define el valor para el campo 'fue_pagado_con_credito'.
    # Django REST Framework la llamará automáticamente para cada pedido.
    def get_fue_pagado_con_credito(self, obj):
        """
        Devuelve True si el pedido tiene un monto de crédito usado mayor a cero.
        """
        return obj.monto_usado_credito > 0
    
    def validate(self, data):
        request = self.context.get('request')
        user = request.user
        
        if not user.is_authenticated:
            if not data.get('email_invitado'):
                raise serializers.ValidationError({"email_invitado": "El correo electrónico es requerido para invitados."})
            if data.get('credito_usado'):
                raise serializers.ValidationError({"credito": "Los invitados no pueden usar crédito."})
        
        if not data.get('productos'):
            raise serializers.ValidationError({"productos": "El carrito no puede estar vacío."})
            
        return data

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user
        
        credito_usado = validated_data.pop('credito_usado', None)
        lista_comprobantes = validated_data.pop('comprobantes_iniciales', [])
        productos_json_str = validated_data.pop('productos')
        
        try:
            productos_data = json.loads(productos_json_str)
        except json.JSONDecodeError:
            raise serializers.ValidationError({'productos': 'Formato de productos inválido.'})
        
        if not isinstance(productos_data, list) or not productos_data:
            raise serializers.ValidationError({"productos": "El carrito no puede estar vacío."})

        subtotal_pedido = Decimal('0.00')
        ids_productos = [item['id'] for item in productos_data]
        productos_db = {p.id: p for p in Producto.objects.filter(id__in=ids_productos)}

        for item in productos_data:
            producto = productos_db.get(item['id'])
            if not producto:
                raise serializers.ValidationError(f"Producto con ID {item['id']} no encontrado.")
            if producto.precio_venta <= 0:
                raise serializers.ValidationError(f"El producto '{producto.nombre}' no tiene un precio válido y no se puede comprar.")
            cantidad = int(item['quantity'])
            if producto.stock_actual < cantidad:
                raise serializers.ValidationError(f"Stock insuficiente para {producto.nombre}.")
            subtotal_pedido += Decimal(producto.precio_venta) * cantidad
        
        tasa_iva_decimal = Decimal(settings.TASA_IVA) / Decimal('100.0')
        iva_pedido = round(subtotal_pedido * tasa_iva_decimal, 2)
        total_pedido = subtotal_pedido + iva_pedido
        
        monto_usado_credito = Decimal('0.00')
        estado_inicial = 'pendiente_pago'
        
        cliente_inst = None
        if user.is_authenticated:
            cliente_inst = ModeloCliente.objects.filter(id=user.id).first()
            if not cliente_inst:
                raise ValidationError("El usuario autenticado no tiene un perfil de cliente asociado.")

        if credito_usado:
            if credito_usado.saldo_disponible_para_ventas < total_pedido:
                raise serializers.ValidationError({"credito": "El crédito no tiene saldo suficiente para cubrir el total del pedido."})
            monto_usado_credito = total_pedido
            estado_inicial = 'confirmado'
            
        # ✨ CORRECCIÓN: La creación del pedido ocurre aquí, fuera de la condición del crédito
        pedido = Pedido.objects.create(
            subtotal=subtotal_pedido,
            iva=iva_pedido,
            total=total_pedido,
            estado=estado_inicial,
            credito_usado=credito_usado,
            monto_usado_credito=monto_usado_credito,
            cliente=cliente_inst,
            **validated_data
        )

        detalles_a_crear = [
            DetallePedido(
                pedido=pedido,
                producto=productos_db.get(item['id']),
                cantidad=item['quantity'],
                precio_unitario=productos_db.get(item['id']).precio_venta
            ) for item in productos_data
        ]
        DetallePedido.objects.bulk_create(detalles_a_crear)
        
        if lista_comprobantes:
            for imagen in lista_comprobantes:
                ComprobantePago.objects.create(pedido=pedido, imagen=imagen)
            pedido.estado = 'en_verificacion'
            pedido.save(update_fields=['estado'])
        
        # ✨ CORRECCIÓN: Se aplica a CUALQUIER usuario (logueado o invitado) que no pague con crédito ni suba comprobante
        elif not credito_usado:
            pedido.estado = 'pendiente_pago_temporal'
            pedido.fecha_limite_pago = timezone.now() + timedelta(minutes=60)
            pedido.save(update_fields=['estado', 'fecha_limite_pago'])
        
        if pedido.estado == 'confirmado':
            pedido._process_confirmation()
        
        enviar_correo_confirmacion_pedido(pedido)
        return pedido

# --- Serializer de invitado (con pequeños cambios) ---
class GuestPedidoStatusSerializer(serializers.ModelSerializer):
    detalles = DetallePedidoSerializer(many=True, read_only=True)
    comprobantes = ComprobantePagoSerializer(many=True, read_only=True)
    email_contacto = serializers.SerializerMethodField()
    
    class Meta:
        model = Pedido
        # 👇 2. Reemplaza 'email_invitado' por 'email_contacto'
        fields = [
            'id', 'fecha_creacion', 'subtotal', 'iva', 'total', 'estado', 'metodo_entrega',
            'nombre_receptor', 'detalles', 'email_contacto', 'comprobantes', 'token_seguimiento',
            'motivo_cancelacion', 'fecha_limite_pago',
            'monto_pagado_verificado', 'monto_usado_credito'
        ]

    # 👇 3. Define la lógica para obtener el email
    def get_email_contacto(self, obj):
        if obj.cliente and obj.cliente.correo:
            return obj.cliente.correo
        return obj.email_invitado