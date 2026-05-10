# Productos/admin.py

from django.contrib import admin
from .models import CategoriaProducto, Marca, Producto, ImagenProducto

from .models import Marca
try:
    admin.site.register(Marca)
except admin.sites.AlreadyRegistered:
    pass


# Esta clase permite editar las imágenes directamente dentro del producto
class ImagenProductoInline(admin.TabularInline):
    model = ImagenProducto
    extra = 1  # Cuántos campos vacíos para nuevas imágenes mostrar

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):

    list_display = (
        'nombre', 
        'categoria', 
        'marca', 
        'stock_actual', 
        'ultimo_costo_compra',      
        'ultimo_margen_aplicado',   
        'precio_venta',             
        'activo'
    )
    

    list_filter = ('categoria', 'marca', 'activo')
    
    # Mejora técnica: para buscar en campos de modelos relacionados se usa '__'
    search_fields = ('nombre', 'marca__nombre', 'categoria__nombre')
    
    inlines = [ImagenProductoInline] # Aquí conectamos las imágenes con el producto

@admin.register(CategoriaProducto)
class CategoriaProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion', 'activo')
    search_fields = ('nombre',)
