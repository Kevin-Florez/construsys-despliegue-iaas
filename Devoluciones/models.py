# backend_api/Devoluciones/models.py
from django.db import models
from django.utils import timezone
from decimal import Decimal

class Devolucion(models.Model):
    ESTADO_CHOICES = [('PROCESANDO', 'Procesando'), ('COMPLETADA', 'Completada'), ('CANCELADA', 'Cancelada')]
    # IMPLEMENTACIÓN: Se elimina la opción 'PENDIENTE' del TIPO_REEMBOLSO_CHOICES.
    TIPO_REEMBOLSO_CHOICES = [('AL_CREDITO', 'Abonado al Crédito'), ('EFECTIVO', 'Reembolsado en Efectivo'), ('SIN_REEMBOLSO', 'Sin Reembolso (Cambio Exacto o a Favor)')]
    ESTADO_CAMBIO_CHOICES = [('SIN_CAMBIO', 'Sin cambio de producto'), ('MISMO_PRODUCTO', 'Cambio por el mismo producto'), ('OTRO_PRODUCTO', 'Cambio por un producto diferente')]
    
    # IMPLEMENTACIÓN: Nuevas opciones para el pago del cliente cuando el balance es positivo.
    METODO_PAGO_ADICIONAL_CHOICES = [('CREDITO', 'Uso de Crédito'), ('EFECTIVO', 'Efectivo'), ('TRANSFERENCIA', 'Transferencia')]

    venta_original = models.OneToOneField('Ventas.Venta', on_delete=models.PROTECT, related_name='devolucion', verbose_name="Venta Original")
    cliente = models.ForeignKey('Clientes.Cliente', on_delete=models.PROTECT, related_name='devoluciones', verbose_name="Cliente")
    
    fecha_devolucion = models.DateField(default=timezone.localdate, verbose_name="Fecha de la Devolución")
    motivo_general = models.TextField(blank=True, null=True, verbose_name="Motivo general de la devolución")
    total_productos_devueltos = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_productos_cambio = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    balance_final = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Negativo si la empresa debe dinero, positivo si el cliente debe pagar.")
    
    # Campos para cuando la EMPRESA debe dinero (balance < 0)
    tipo_reembolso = models.CharField(max_length=20, choices=TIPO_REEMBOLSO_CHOICES, blank=True)
    monto_reembolsado_efectivo = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Monto devuelto en efectivo.")
    monto_abonado_credito = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Monto que se abonó al crédito del cliente.")

    # IMPLEMENTACIÓN: Nuevos campos para cuando el CLIENTE debe dinero (balance > 0)
    monto_pagado_adicional = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Monto adicional pagado por el cliente.")
    metodo_pago_adicional = models.CharField(max_length=20, choices=METODO_PAGO_ADICIONAL_CHOICES, blank=True, null=True, help_text="Método usado por el cliente para pagar la diferencia.")
    credito_usado_para_pago = models.ForeignKey('Creditos.Credito', on_delete=models.SET_NULL, null=True, blank=True, related_name='devoluciones_pagadas', help_text="Crédito usado para cubrir el balance a favor de la tienda.")

    estado_del_cambio = models.CharField(max_length=20, choices=ESTADO_CAMBIO_CHOICES, default='SIN_CAMBIO')
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='COMPLETADA')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.balance_final = self.total_productos_cambio - self.total_productos_devueltos
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Devolución para Venta #{self.venta_original.id} - Balance: {self.balance_final:,.2f}"

    class Meta:
        verbose_name = "Devolución de Venta"
        verbose_name_plural = "Devoluciones de Venta"
        ordering = ['-fecha_devolucion']

class ItemDevuelto(models.Model):
    class MotivoDevolucion(models.TextChoices):
        EQUIVOCO_PRODUCTO = 'EQUIVOCO_PRODUCTO', 'Se equivocó de producto'
        NO_NECESITA = 'NO_NECESITA', 'No necesita el producto'
        PRODUCTO_DEFECTUOSO = 'PRODUCTO_DEFECTUOSO', 'Producto defectuoso'

    @staticmethod
    def puede_reabastecer(motivo):
        return motivo in [ItemDevuelto.MotivoDevolucion.EQUIVOCO_PRODUCTO, ItemDevuelto.MotivoDevolucion.NO_NECESITA]

    devolucion = models.ForeignKey(Devolucion, on_delete=models.CASCADE, related_name='items_devueltos')
    # Se usa un string para la relación
    producto = models.ForeignKey('Productos.Producto', on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    precio_unitario_historico = models.DecimalField(max_digits=10, decimal_places=2, help_text="Precio al que se vendió originalmente el producto.")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    motivo = models.CharField(max_length=30, choices=MotivoDevolucion.choices)
    devuelto_a_proveedor = models.BooleanField(default=False, help_text="Indica si este item ya fue incluido en una devolución a proveedor.")

    def save(self, *args, **kwargs):
        self.subtotal = Decimal(self.cantidad) * self.precio_unitario_historico
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre} (Devuelto - {self.get_motivo_display()})"

class ItemCambio(models.Model):
    devolucion = models.ForeignKey(Devolucion, on_delete=models.CASCADE, related_name='items_cambio')
    # Se usa un string para la relación
    producto = models.ForeignKey('Productos.Producto', on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    precio_unitario_actual = models.DecimalField(max_digits=10, decimal_places=2, help_text="Precio de venta actual del producto nuevo.")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    def save(self, *args, **kwargs):
        self.subtotal = Decimal(self.cantidad) * self.precio_unitario_actual
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre} (Cambio)"