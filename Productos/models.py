# backend_api/Productos/models.py

from django.db import models
from django.core.exceptions import ValidationError
from decimal import Decimal

class CategoriaProducto(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre de categoría")
    descripcion = models.TextField(verbose_name="Descripción")
    activo = models.BooleanField(default=True, verbose_name="Activo")

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Categoría de Producto"
        verbose_name_plural = "Categorías de Productos"

class Marca(models.Model):
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre de la Marca")
    # --- INICIO DE CAMBIOS ---
    activo = models.BooleanField(default=True, verbose_name="Activo")
    # --- FIN DE CAMBIOS ---
    
    class Meta:
        verbose_name = "Marca"
        verbose_name_plural = "Marcas"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

class Producto(models.Model):
    # Productos/models.py -> class Producto
    categoria = models.ForeignKey(
    CategoriaProducto, on_delete=models.PROTECT, # Cambiar a PROTECT
    null=True, blank=True, verbose_name="Categoría", related_name="productos"
)
    
    marca = models.ForeignKey(
        Marca, 
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name="Marca",
        related_name="productos"
    )
    
    nombre = models.CharField(max_length=200, verbose_name="Nombre del producto")
    descripcion = models.TextField(
        verbose_name="Descripción para el Catálogo",
        blank=True,
        help_text="Descripción detallada que aparecerá en la tienda."
    )
    imagen_url = models.URLField(
        max_length=1024,
        verbose_name="URL de la Imagen Principal",
        blank=True,
        null=True,
        help_text="Enlace a la imagen principal que se muestra en la tarjeta del catálogo."
    )
    
    peso = models.CharField(max_length=50, blank=True, verbose_name="Peso", help_text="Ej: 50 kg, 25 lbs")
    dimensiones = models.CharField(max_length=100, blank=True, verbose_name="Dimensiones", help_text="Ej: 120cm x 60cm x 15cm")
    material = models.CharField(max_length=100, blank=True, verbose_name="Material Principal")
    otros_detalles = models.TextField(blank=True, verbose_name="Otros Detalles", help_text="Cualquier otra especificación relevante.")
    
    # --- INICIO DE CAMBIOS ---
    # 1. Se renombra 'precio_venta_sugerido' a 'precio_venta'
    precio_venta = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Precio de Venta")
    # 2. Se añade campo para el último margen
    ultimo_margen_aplicado = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Último Margen Aplicado (%)")
    # --- FIN DE CAMBIOS ---
    
    ultimo_costo_compra = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Último Costo de Compra")
    stock_actual = models.IntegerField(default=0, verbose_name="Stock Actual (Vendible)")
    stock_minimo = models.PositiveIntegerField(default=10, verbose_name="Stock Mínimo")
    stock_maximo = models.PositiveIntegerField(default=100, verbose_name="Stock Máximo")
    stock_defectuoso = models.IntegerField(default=0, verbose_name="Stock Defectuoso/No Vendible")
    activo = models.BooleanField(default=True, verbose_name="Activo")

    @property
    def stock(self):
        return self.stock_actual

    @stock.setter
    def stock(self, value):
        if not isinstance(value, int) or value < 0:
            raise ValidationError("El stock debe ser un número entero no negativo.")
        self.stock_actual = value

    def __str__(self):
        return self.nombre

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"


class ImagenProducto(models.Model):
    producto = models.ForeignKey(
        Producto, 
        related_name='imagenes', 
        on_delete=models.CASCADE,
        verbose_name="Producto"
    )
    imagen_url = models.URLField(
        max_length=1024,
        verbose_name="URL de la Imagen Adicional"
    )

    def __str__(self):
        return f"Imagen para {self.producto.nombre}"

    class Meta:
        verbose_name = "Imagen de Producto"
        verbose_name_plural = "Imágenes de Productos"