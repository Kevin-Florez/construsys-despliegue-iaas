# Productos/admin.py

from django.contrib import admin
from .models import CategoriaProducto, Marca, Producto, ImagenProducto

# No es necesario registrar Marca aquí si ya lo hiciste en otro admin.py
# pero si no, es bueno tenerlo. Si da error de que ya está registrado, elimina estas líneas.
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
    # --- INICIO DE LA MODIFICACIÓN ---
    # 1. Se reemplaza 'precio_venta_sugerido' por 'precio_venta'.
    # 2. Se añaden los nuevos campos para tener más información en la lista.
    list_display = (
        'nombre', 
        'categoria', 
        'marca', 
        'stock_actual', 
        'ultimo_costo_compra',      # <-- Campo añadido para visibilidad
        'ultimo_margen_aplicado',   # <-- Campo añadido para visibilidad
        'precio_venta',             # <-- ¡Este es el cambio principal que corrige el error!
        'activo'
    )
    # --- FIN DE LA MODIFICACIÓN ---

    list_filter = ('categoria', 'marca', 'activo')
    
    # Mejora técnica: para buscar en campos de modelos relacionados se usa '__'
    search_fields = ('nombre', 'marca__nombre', 'categoria__nombre')
    
    inlines = [ImagenProductoInline] # Aquí conectamos las imágenes con el producto

@admin.register(CategoriaProducto)
class CategoriaProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'descripcion', 'activo')
    search_fields = ('nombre',)