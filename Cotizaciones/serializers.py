# Cotizaciones/serializers.py

from rest_framework import serializers
from django.db import transaction
from decimal import Decimal
from django.conf import settings

from .models import Cotizacion, DetalleCotizacion
from Productos.models import Producto
from Clientes.models import Cliente

# Serializer para mostrar los detalles de un producto en una cotización
class DetalleProductoCotizadoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Producto
        fields = ['id', 'nombre', 'imagen_url']

# Serializer para leer los detalles de una cotización
class DetalleCotizacionReadSerializer(serializers.ModelSerializer):
    producto = DetalleProductoCotizadoSerializer(read_only=True)
    subtotal = serializers.ReadOnlyField()

    class Meta:
        model = DetalleCotizacion
        fields = [
            'id', 'producto', 'producto_nombre_historico', 
            'cantidad', 'precio_unitario_cotizado', 'subtotal'
        ]

# Serializer para mostrar info básica de un cliente
class ClienteCotizacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = ['id', 'nombre', 'apellido', 'correo']


# Serializer principal para leer una cotización completa
class CotizacionReadSerializer(serializers.ModelSerializer):
    detalles = DetalleCotizacionReadSerializer(many=True, read_only=True)
    cliente = ClienteCotizacionSerializer(read_only=True)
    
    
    # Cambiamos la forma de obtener el estado para que sea más explícita y segura.
    estado_display = serializers.SerializerMethodField()
   

    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = Cotizacion
        fields = [
            'id', 'token_acceso', 'cliente', 'email_invitado', 'nombre_invitado',
            'fecha_creacion', 'fecha_vencimiento', 'estado', 'estado_display', 'is_expired',
            'subtotal', 'iva', 'total', 'detalles'
        ]

    
    # Añadimos el método que define el valor para 'estado_display'
    def get_estado_display(self, obj):
        # obj es la instancia de la Cotizacion
        # Django provee automáticamente el método get_estado_display() en el modelo
        # cuando se usa 'choices' en un campo.
        return obj.get_estado_display()
    


# Serializer para crear una nueva cotización
class CotizacionCreateSerializer(serializers.Serializer):
    # No es un ModelSerializer porque la entrada es diferente al modelo
    
    cart_items = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=True
    )
    email_invitado = serializers.EmailField(required=False, allow_blank=True)
    nombre_invitado = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate_cart_items(self, items):
        if not items:
            raise serializers.ValidationError("El carrito no puede estar vacío para crear una cotización.")
        for item in items:
            if 'id' not in item or 'quantity' not in item:
                raise serializers.ValidationError("Cada item del carrito debe tener 'id' y 'quantity'.")
            if not isinstance(item['quantity'], int) or item['quantity'] <= 0:
                raise serializers.ValidationError(f"La cantidad para el producto ID {item['id']} debe ser un número entero positivo.")
        return items

    def validate(self, data):
        request = self.context.get('request')
        user = request.user if request else None

        if not user or not user.is_authenticated:
            if not data.get('email_invitado') or not data.get('nombre_invitado'):
                raise serializers.ValidationError({
                    "detail": "Para invitados, el nombre y el correo electrónico son requeridos para guardar la cotización."
                })
        return data

    @transaction.atomic
    def create(self, validated_data):
        request = self.context.get('request')
        user = request.user
        cart_items = validated_data['cart_items']
        
        product_ids = [item['id'] for item in cart_items]
        products_in_db = {p.id: p for p in Producto.objects.filter(id__in=product_ids)}

        calculated_subtotal = Decimal('0.00')
        detalles_para_crear = []

        for item in cart_items:
            producto = products_in_db.get(item['id'])
            if not producto:
                raise serializers.ValidationError(f"Producto con ID {item['id']} no encontrado.")
            if not producto.activo or producto.precio_venta <= 0:
                raise serializers.ValidationError(f"El producto '{producto.nombre}' no está disponible para la venta.")
            
            cantidad = item['quantity']
            precio_congelado = producto.precio_venta
            
            detalles_para_crear.append({
                'producto': producto,
                'cantidad': cantidad,
                'precio_unitario_cotizado': precio_congelado,
                'producto_nombre_historico': producto.nombre
            })
            calculated_subtotal += cantidad * precio_congelado

        tasa_iva = Decimal(settings.TASA_IVA) / Decimal('100.0')
        calculated_iva = round(calculated_subtotal * tasa_iva, 2)
        calculated_total = calculated_subtotal + calculated_iva

        cotizacion_data = {
            'subtotal': calculated_subtotal,
            'iva': calculated_iva,
            'total': calculated_total,
        }

        if user.is_authenticated:
            cliente_instance = Cliente.objects.filter(id=user.id).first()
            if cliente_instance:
                cotizacion_data['cliente'] = cliente_instance
            else:
                 cotizacion_data['email_invitado'] = user.email
                 cotizacion_data['nombre_invitado'] = f"{user.first_name} {user.last_name}".strip()
        else:
            cotizacion_data['email_invitado'] = validated_data['email_invitado']
            cotizacion_data['nombre_invitado'] = validated_data['nombre_invitado']

        cotizacion = Cotizacion.objects.create(**cotizacion_data)

        detalles_cotizacion_obj = [
            DetalleCotizacion(cotizacion=cotizacion, **detalle_data)
            for detalle_data in detalles_para_crear
        ]
        DetalleCotizacion.objects.bulk_create(detalles_cotizacion_obj)

        return cotizacion
    


class AdminDetalleCotizacionCreateSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField(required=True)
    cantidad = serializers.IntegerField(required=True, min_value=1)

class AdminCotizacionCreateSerializer(serializers.Serializer):
    cliente_id = serializers.IntegerField(required=False, allow_null=True)
    email_invitado = serializers.EmailField(required=False, allow_blank=True)
    nombre_invitado = serializers.CharField(max_length=200, required=False, allow_blank=True)
    detalles = AdminDetalleCotizacionCreateSerializer(many=True, required=True)

    def validate(self, data):
        """
        Valida que se provea un cliente o los datos de un invitado, pero no ambos.
        También valida que la lista de detalles no esté vacía.
        """
        cliente_id = data.get('cliente_id')
        email_invitado = data.get('email_invitado')
        nombre_invitado = data.get('nombre_invitado')
        detalles = data.get('detalles')

        if not cliente_id and (not email_invitado or not nombre_invitado):
            raise serializers.ValidationError("Debe proporcionar un cliente existente o los datos completos del invitado (nombre y correo).")
        
        if cliente_id and (email_invitado or nombre_invitado):
            raise serializers.ValidationError("No puede proporcionar un cliente y datos de invitado al mismo tiempo.")

        if not detalles:
            raise serializers.ValidationError({"detalles": "La lista de productos no puede estar vacía."})
            
        return data

    @transaction.atomic
    def create(self, validated_data):
        detalles_data = validated_data.pop('detalles')
        
        product_ids = [item['producto_id'] for item in detalles_data]
        products_in_db = {p.id: p for p in Producto.objects.filter(id__in=product_ids)}

        calculated_subtotal = Decimal('0.00')
        detalles_para_crear = []

        for item in detalles_data:
            producto = products_in_db.get(item['producto_id'])
            if not producto:
                raise serializers.ValidationError(f"Producto con ID {item['producto_id']} no encontrado.")
            if not producto.activo or producto.precio_venta <= 0:
                raise serializers.ValidationError(f"El producto '{producto.nombre}' no está disponible para la venta.")
            
            cantidad = item['cantidad']
            precio_congelado = producto.precio_venta
            
            detalles_para_crear.append({
                'producto': producto,
                'cantidad': cantidad,
                'precio_unitario_cotizado': precio_congelado,
                'producto_nombre_historico': producto.nombre
            })
            calculated_subtotal += cantidad * precio_congelado

        tasa_iva = Decimal(settings.TASA_IVA) / Decimal('100.0')
        calculated_iva = round(calculated_subtotal * tasa_iva, 2)
        calculated_total = calculated_subtotal + calculated_iva

        cotizacion_data = {
            'subtotal': calculated_subtotal,
            'iva': calculated_iva,
            'total': calculated_total,
        }

        if validated_data.get('cliente_id'):
            try:
                cliente = Cliente.objects.get(id=validated_data['cliente_id'])
                cotizacion_data['cliente'] = cliente
            except Cliente.DoesNotExist:
                raise serializers.ValidationError(f"Cliente con ID {validated_data['cliente_id']} no encontrado.")
        else:
            cotizacion_data['email_invitado'] = validated_data['email_invitado']
            cotizacion_data['nombre_invitado'] = validated_data['nombre_invitado']

        cotizacion = Cotizacion.objects.create(**cotizacion_data)

        detalles_cotizacion_obj = [
            DetalleCotizacion(cotizacion=cotizacion, **detalle)
            for detalle in detalles_para_crear
        ]
        DetalleCotizacion.objects.bulk_create(detalles_cotizacion_obj)

        return cotizacion
