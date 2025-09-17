# backend_api/Compras/serializers.py

from rest_framework import serializers
from django.db import transaction
from decimal import Decimal
from .models import Compra, ItemCompra
from Proveedores.models import Proveedor
from Productos.models import Producto

class ItemCompraSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)
    producto = serializers.PrimaryKeyRelatedField(queryset=Producto.objects.filter(activo=True))
    
    cantidad = serializers.IntegerField(min_value=1)
    costo_unitario = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)

    
    nuevo_precio_venta = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, write_only=True
    )
    margen_aplicado = serializers.DecimalField(
        max_digits=5, decimal_places=2, required=False, write_only=True
    )
   

    class Meta:
        model = ItemCompra
        fields = [
            'id', 'producto', 'producto_nombre', 'cantidad', 
            'costo_unitario', 'subtotal', 
            
            'nuevo_precio_venta', 'margen_aplicado'
        ]
        read_only_fields = ['id', 'subtotal', 'producto_nombre']


class CompraReadSerializer(serializers.ModelSerializer):
    proveedor_nombre = serializers.CharField(source='proveedor.nombre', read_only=True)
    items = ItemCompraSerializer(many=True, read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    items_resumen = serializers.SerializerMethodField()
    subtotal = serializers.SerializerMethodField()
    iva = serializers.SerializerMethodField()
    total = serializers.SerializerMethodField()

    class Meta:
        model = Compra
        fields = [
            'id', 
            
            'numero_factura', 
            'proveedor_nombre', 'items', 'items_resumen',
            'subtotal', 'iva', 'total',
            'fecha_compra', 'estado', 'estado_display', 
            
            'fecha_registro', 
            'fecha_actualizacion'
        ]
    
    def get_items_resumen(self, obj):
        items = obj.items.all()[:2]
        resumen = ", ".join([f"{item.cantidad}x {item.nombre_producto_historico}" for item in items])
        if obj.items.count() > 2:
            resumen += ", ..."
        return resumen if resumen else "Sin productos"

    def get_subtotal(self, obj: Compra) -> Decimal:
        if obj.subtotal > 0:
            return obj.subtotal
        return sum(item.subtotal for item in obj.items.all())

    def get_iva(self, obj: Compra) -> Decimal:
        if obj.iva > 0:
            return obj.iva
        subtotal = self.get_subtotal(obj)
        return subtotal * Decimal('0.19')

    def get_total(self, obj: Compra) -> Decimal:
        if obj.total > 0:
            return obj.total
        subtotal = self.get_subtotal(obj)
        iva = self.get_iva(obj)
        return subtotal + iva

class CompraCreateSerializer(serializers.ModelSerializer):
    proveedor = serializers.PrimaryKeyRelatedField(queryset=Proveedor.objects.filter(estado='Activo'))
    items = ItemCompraSerializer(many=True, write_only=True)

    class Meta:
        model = Compra
       
        fields = ['id', 'numero_factura', 'proveedor', 'fecha_compra', 'estado', 'items']
        read_only_fields = ['id']
        
    def validate_numero_factura(self, value):
       
        if not value or not value.strip():
            raise serializers.ValidationError("El número de factura no puede estar vacío.")
        return value

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        estado_compra = validated_data.get('estado', 'pendiente')

        with transaction.atomic():
            compra = Compra.objects.create(**validated_data)
            
            calculated_subtotal = Decimal('0.00')
            for item_data in items_data:
                subtotal_item = item_data['cantidad'] * item_data['costo_unitario']
                
                ItemCompra.objects.create(
                    compra=compra,
                    producto=item_data['producto'],
                    nombre_producto_historico=item_data['producto'].nombre,
                    cantidad=item_data['cantidad'],
                    costo_unitario=item_data['costo_unitario'],
                    subtotal=subtotal_item
                )
                calculated_subtotal += subtotal_item

                
                # Si la compra es 'confirmada', actualizamos los datos del producto
                if estado_compra == 'confirmada':
                    producto_obj = item_data['producto']
                    
                    # Actualiza el precio de venta si se envió uno nuevo
                    nuevo_precio = item_data.get('nuevo_precio_venta')
                    if nuevo_precio is not None:
                        producto_obj.precio_venta = nuevo_precio
                    
                    # Actualiza el margen si se envió uno
                    margen = item_data.get('margen_aplicado')
                    if margen is not None:
                        producto_obj.ultimo_margen_aplicado = margen
                    
                    # Guardamos los cambios en el producto
                    producto_obj.save(update_fields=['precio_venta', 'ultimo_margen_aplicado'])
               
            
            TASA_IVA = Decimal('0.19')
            compra.subtotal = calculated_subtotal
            compra.iva = calculated_subtotal * TASA_IVA
            compra.total = compra.subtotal + compra.iva
            compra.save(update_fields=['subtotal', 'iva', 'total'])

            # El método _procesar_confirmacion (en models.py) ya actualiza el stock y el costo.
            # Lo llamamos al final para asegurar que todo lo demás se haya guardado.
            if estado_compra == 'confirmada':
                compra._procesar_confirmacion()
        
        return compra