# backend_api/Productos/serializers.py

from rest_framework import serializers
from .models import CategoriaProducto, Producto, ImagenProducto, Marca
from decimal import Decimal

class CategoriaProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoriaProducto
        fields = ['id', 'nombre', 'descripcion', 'activo']

class ImagenProductoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ImagenProducto
        fields = ['id', 'imagen_url']

class MarcaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Marca
        # --- INICIO DE CAMBIOS ---
        fields = ['id', 'nombre', 'activo']
        # --- FIN DE CAMBIOS ---

class ProductoSerializer(serializers.ModelSerializer):
    categoria = CategoriaProductoSerializer(read_only=True)
    categoria_id = serializers.PrimaryKeyRelatedField(
        queryset=CategoriaProducto.objects.all(),
        source='categoria', write_only=True, allow_null=True, required=False
    )
    
    marca = MarcaSerializer(read_only=True)
    marca_id = serializers.PrimaryKeyRelatedField(
        queryset=Marca.objects.all(),
        source='marca', write_only=True, allow_null=True, required=False
    )
    
    imagenes = ImagenProductoSerializer(many=True, read_only=True)
    imagenes_write = serializers.ListField(
        child=serializers.URLField(max_length=1024),
        write_only=True, required=False
    )

    class Meta:
        model = Producto
        fields = [
            'id', 'nombre', 
            'descripcion', 'imagen_url', 
            'peso', 'dimensiones', 'material', 'otros_detalles',
            'imagenes', 'imagenes_write',
            
            # --- INICIO DE CAMBIOS ---
            'precio_venta', 
            'ultimo_margen_aplicado',
            # --- FIN DE CAMBIOS ---
            
            'ultimo_costo_compra',
            'stock_actual', 'stock_minimo', 'stock_maximo', 'activo',
            'categoria', 'categoria_id',
            'marca', 'marca_id'
        ]
        # --- INICIO DE CAMBIOS ---
        # El precio de venta ahora es de solo lectura directa, se calcula via margen.
        read_only_fields = ['id', 'ultimo_costo_compra', 'stock_actual', 'precio_venta']
        # --- FIN DE CAMBIOS ---

    def create(self, validated_data):
        # Al crear, no se establece precio de venta ni margen, empiezan en 0 o nulo.
        validated_data.pop('precio_venta', None)
        validated_data.pop('ultimo_margen_aplicado', None)
        
        imagenes_urls = validated_data.pop('imagenes_write', [])
        producto = Producto.objects.create(**validated_data)
        for url in imagenes_urls:
            if url:
                ImagenProducto.objects.create(producto=producto, imagen_url=url)
        return producto

    def update(self, instance, validated_data):
        imagenes_urls = validated_data.pop('imagenes_write', None)
        
        # --- INICIO DE LÓGICA DE PRECIOS ---
        # Si se envía un nuevo margen, calculamos el nuevo precio de venta.
        if 'ultimo_margen_aplicado' in validated_data:
            nuevo_margen = validated_data.get('ultimo_margen_aplicado')
            if nuevo_margen is not None and instance.ultimo_costo_compra is not None:
                costo = instance.ultimo_costo_compra
                # Formula: Precio Venta = Costo * (1 + Margen / 100)
                nuevo_precio = costo * (Decimal('1') + (Decimal(nuevo_margen) / Decimal('100')))
                instance.precio_venta = nuevo_precio
        # --- FIN DE LÓGICA DE PRECIOS ---

        # Actualiza el resto de los campos
        instance = super().update(instance, validated_data)

        if imagenes_urls is not None:
            instance.imagenes.all().delete()
            for url in imagenes_urls:
                if url:
                    ImagenProducto.objects.create(producto=instance, imagen_url=url)
        return instance


class ProductoDashboardStockSerializer(serializers.ModelSerializer):
    marca_nombre = serializers.CharField(source='marca.nombre', read_only=True, default='')
    class Meta:
        model = Producto
        fields = ['id', 'nombre', 'marca_nombre', 'stock_actual', 'stock_minimo']