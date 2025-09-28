# backend_api/Ventas/models.py

from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import timedelta
import logging

# Se eliminan las importaciones directas de modelos de otras apps
# from Clientes.models import Cliente
# from Productos.models import Producto
# from Creditos.models import Credito

logger = logging.getLogger(__name__)

class Venta(models.Model):
    ESTADO_CHOICES = [('Pendiente', 'Pendiente'), ('Completada', 'Completada'), ('Anulada', 'Anulada')]
    METODO_PAGO_ADICIONAL_CHOICES = [('Efectivo', 'Efectivo'), ('Transferencia', 'Transferencia')]
    METODO_ENTREGA_CHOICES = [('domicilio', 'Domicilio'), ('tienda', 'Reclama en Tienda')]
    
    fecha = models.DateField(default=timezone.now, verbose_name="Fecha de venta")
    # Se usan strings para las relaciones
    cliente = models.ForeignKey('Clientes.Cliente', on_delete=models.PROTECT, related_name='ventas')
    credito_usado = models.ForeignKey('Creditos.Credito', on_delete=models.SET_NULL, null=True, blank=True, related_name='ventas_asociadas')
    
    metodo_entrega = models.CharField(max_length=20, choices=METODO_ENTREGA_CHOICES, default='tienda', verbose_name="Método de Entrega")
    direccion_entrega = models.CharField(max_length=255, verbose_name="Dirección de Entrega", blank=True, null=True)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    iva = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    monto_cubierto_con_credito = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    monto_pago_adicional = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    metodo_pago_adicional = models.CharField(max_length=50, choices=METODO_PAGO_ADICIONAL_CHOICES, blank=True, null=True)
    comprobante_pago_adicional = models.FileField(upload_to='comprobantes_pago_adicional/', blank=True, null=True)
    estado = models.CharField(max_length=20, default='Pendiente', choices=ESTADO_CHOICES)
    tiene_devolucion = models.BooleanField(default=False, verbose_name="¿Tiene Devoluciones?")
    observaciones = models.TextField(blank=True, null=True)
    fecha_creacion_registro = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion_registro = models.DateTimeField(auto_now=True)
    
    pedido_origen = models.OneToOneField('Pedidos.Pedido', on_delete=models.SET_NULL, null=True, blank=True, related_name='venta', verbose_name="Pedido de Origen")

    # ... (todos los @property y métodos se mantienen igual, con importaciones locales)
    @property
    def fecha_limite_ajuste(self):
        return self.fecha + timedelta(days=15)

    @property
    def es_ajustable(self):
        return (self.estado == 'Completada' and not self.tiene_devolucion and timezone.now().date() <= self.fecha_limite_ajuste)

    def __str__(self):
        cliente_info = f"Cliente ID {self.cliente.id}" if self.cliente else "Cliente Genérico"
        return f"Venta #{self.id} - {cliente_info} - Total: ${self.total:,.0f} - Estado: {self.estado}"

    def _procesar_completado(self):
        logger.info(f"VENTA ID {self.id}: Procesando completado de venta...")
        # Importaciones locales al método
        from Productos.models import Producto
        from Creditos.models import Credito
        with transaction.atomic():
            if self.credito_usado and self.monto_cubierto_con_credito > 0:
                credito = Credito.objects.select_for_update().get(id=self.credito_usado.id)
                monto_usado = self.monto_cubierto_con_credito
                if credito.saldo_disponible_para_ventas < monto_usado:
                    raise ValidationError(f"El crédito ID {credito.id} no tiene suficiente saldo disponible para cubrir ${monto_usado:,.0f}.")
                credito.capital_utilizado += monto_usado
                credito.save(update_fields=['capital_utilizado'])
                logger.info(f"   CRÉDITO: Actualizado cupo utilizado para crédito ID {credito.id}")

            for detalle in self.detalles.all():
                producto = Producto.objects.select_for_update().get(id=detalle.producto.id)
                if not self.pedido_origen:
                    if producto.stock_actual < detalle.cantidad:
                        raise ValidationError(f"Stock insuficiente para '{producto.nombre}' al confirmar la venta directa.")
                    producto.stock_actual -= detalle.cantidad
                    producto.save(update_fields=['stock_actual'])
                    logger.info(f"   STOCK: Descontado {detalle.cantidad} de '{producto.nombre}' (Venta Directa).")
                else:
                    logger.info(f"   STOCK: Verificado el descuento de stock para '{producto.nombre}' (Venta desde Pedido).")
                
                detalle.costo_unitario_historico = producto.ultimo_costo_compra
                detalle.save(update_fields=['costo_unitario_historico'])

    def _revertir_anulacion(self):
        logger.info(f"VENTA ID {self.id}: Reversión por anulación...")
        # Importaciones locales al método
        from Productos.models import Producto
        from Creditos.models import Credito
        with transaction.atomic():
            if not self.pedido_origen:
                for detalle in self.detalles.all():
                    producto = Producto.objects.select_for_update().get(id=detalle.producto.id)
                    producto.stock_actual += detalle.cantidad
                    producto.save(update_fields=['stock_actual'])
                    logger.info(f"   STOCK: Devuelto {detalle.cantidad} a '{producto.nombre}'. Nuevo stock: {producto.stock_actual}")
            else:
                logger.info(f"   La venta proviene de un pedido. El stock se restauró en el modelo Pedido.")
            
            if self.credito_usado and self.monto_cubierto_con_credito > 0:
                credito = Credito.objects.select_for_update().get(id=self.credito_usado.id)
                monto_revertir = self.monto_cubierto_con_credito
                credito.capital_utilizado = max(Decimal('0.00'), credito.capital_utilizado - monto_revertir)
                credito.save(update_fields=['capital_utilizado'])
                logger.info(f"   CRÉDITO: Revertido uso de crédito ID {credito.id}")
    
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        estado_original = None
        if not is_new:
            try:
                estado_original = Venta.objects.get(pk=self.pk).estado
            except Venta.DoesNotExist:
                pass
        super().save(*args, **kwargs)
        if self.estado == 'Completada' and (is_new or estado_original != 'Completada'):
            self._procesar_completado()
        elif self.estado == 'Anulada' and estado_original == 'Completada':
            self._revertir_anulacion()

    class Meta:
        verbose_name = "Venta"
        verbose_name_plural = "Ventas"
        ordering = ['-fecha', '-id']

class DetalleVenta(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='detalles')
    # Se usa un string para la relación
    producto = models.ForeignKey('Productos.Producto', on_delete=models.PROTECT)
    producto_nombre_historico = models.CharField(max_length=200)
    precio_unitario_venta = models.DecimalField(max_digits=10, decimal_places=2)

    iva_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    costo_unitario_historico = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    cantidad = models.PositiveIntegerField(default=1)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)


    @property
    def precio_final_unitario_con_iva(self):
        """Devuelve el precio de una sola unidad incluyendo su IVA."""
        return self.precio_unitario_venta + self.iva_unitario
    # ✨ --- FIN DE CAMBIOS --- ✨

    def save(self, *args, **kwargs):
        self.subtotal = Decimal(self.cantidad) * self.precio_unitario_venta
        if self.producto and not self.producto_nombre_historico:
            self.producto_nombre_historico = self.producto.nombre
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.cantidad} x {self.producto_nombre_historico} en Venta #{self.venta.id}"

    class Meta:
        verbose_name = "Detalle de Venta"
        verbose_name_plural = "Detalles de Venta"