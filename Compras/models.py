# backend_api/Compras/models.py

from django.db import models, transaction
from django.utils import timezone
from decimal import Decimal
import logging


logger = logging.getLogger(__name__)

class Compra(models.Model):
    ESTADO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('confirmada', 'Confirmada'),
        ('anulada', 'Anulada'),      
    ]
    
    numero_factura = models.CharField(
        max_length=50, 
        unique=True,
        verbose_name="Número de Factura del Proveedor",
        help_text="Número de factura o documento de compra proporcionado por el proveedor."
    )
    
    # Se usa un string para la relación
    proveedor = models.ForeignKey(
        'Proveedores.Proveedor', on_delete=models.PROTECT,
        null=True, blank=False, related_name='compras', verbose_name="Proveedor"
    )
    
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Subtotal")
    iva = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="IVA (19%)")
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Total Compra")
    fecha_compra = models.DateField(default=timezone.now, verbose_name="Fecha de compra del proveedor")
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro en Sistema")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='pendiente', verbose_name="Estado")
    fecha_actualizacion = models.DateTimeField(auto_now=True, verbose_name="Fecha de actualización")

    def __str__(self):
        proveedor_nombre = self.proveedor.nombre if self.proveedor else "N/A"
        return f"Compra Factura #{self.numero_factura} - {proveedor_nombre}"

    def _procesar_confirmacion(self):
        logger.info(f"COMPRA ID {self.id}: Procesando confirmación...")
        # Es necesario importar aquí para la lógica de negocio
        from Productos.models import Producto
        try:
            with transaction.atomic():
                for item in self.items.all():
                    producto = Producto.objects.select_for_update().get(id=item.producto.id)
                    producto.ultimo_costo_compra = item.costo_unitario
                    producto.stock_actual += item.cantidad
                    producto.save(update_fields=['stock_actual', 'ultimo_costo_compra'])
                    logger.info(f"  PRODUCTO '{producto.nombre}': stock +{item.cantidad}. Nuevo stock: {producto.stock_actual}. Nuevo costo: {producto.ultimo_costo_compra:.2f}")
        except Exception as e:
            logger.error(f"Error en transacción al procesar confirmación para Compra ID {self.id}: {str(e)}")
            raise e

    def _revertir_confirmacion(self):
        logger.info(f"COMPRA ID {self.id}: Revirtiendo stock...")
        # Es necesario importar aquí para la lógica de negocio
        from Productos.models import Producto
        with transaction.atomic():
            for item in self.items.all():
                producto = Producto.objects.select_for_update().get(id=item.producto.id)
                producto.stock_actual = max(0, producto.stock_actual - item.cantidad)
                producto.save(update_fields=['stock_actual'])
                logger.info(f"  PRODUCTO '{producto.nombre}': stock -{item.cantidad}. Nuevo stock: {producto.stock_actual}.")

    def save(self, *args, **kwargs):
        estado_original = None
        if self.pk:
            estado_original = Compra.objects.get(pk=self.pk).estado
        super().save(*args, **kwargs)
        if self.estado == 'confirmada' and estado_original != 'confirmada':
            self._procesar_confirmacion()
        elif estado_original == 'confirmada' and self.estado != 'confirmada':
            self._revertir_confirmacion()
    
    class Meta:
        verbose_name = "Compra"
        verbose_name_plural = "Compras"
        ordering = ['-fecha_compra', '-id']

class ItemCompra(models.Model):
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name='items', verbose_name="Compra")
    # Se usa un string para la relación
    producto = models.ForeignKey('Productos.Producto', on_delete=models.SET_NULL, null=True, blank=False, verbose_name="Producto")
    nombre_producto_historico = models.CharField(max_length=200, verbose_name="Nombre del producto (en compra)", help_text="Nombre del producto al momento de la compra, para historial.")
    cantidad = models.PositiveIntegerField(verbose_name="Cantidad")
    costo_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Costo Unitario de Compra")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Subtotal")

    def __str__(self):
        return f"{self.cantidad} x {self.nombre_producto_historico} en Compra #{self.compra.id}"

    def save(self, *args, **kwargs):
        if self.cantidad is not None and self.costo_unitario is not None:
            self.subtotal = self.cantidad * self.costo_unitario
        if self.producto and (not self.pk or not self.nombre_producto_historico):
            self.nombre_producto_historico = self.producto.nombre
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Ítem de compra"
        verbose_name_plural = "Ítems de compra"