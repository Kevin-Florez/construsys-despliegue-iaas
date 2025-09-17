# backend/Stock/models.py

from django.db import models
from django.utils import timezone

class BajaDeStock(models.Model):
    class Motivo(models.TextChoices):
        DANIO_INTERNO = 'DANIO_INTERNO', 'Daño en almacén'
        PERDIDA = 'PERDIDA', 'Pérdida o hurto'
        OTRO = 'OTRO', 'Otro motivo'

    producto = models.ForeignKey('Productos.Producto', on_delete=models.PROTECT, related_name="bajas_de_stock")
    cantidad = models.PositiveIntegerField()
    fecha_baja = models.DateTimeField(auto_now_add=True)
    motivo = models.CharField(max_length=20, choices=Motivo.choices)
    descripcion = models.TextField(help_text="Descripción detallada del motivo de la baja.")
    
    def __str__(self):
        return f"Baja de {self.cantidad} x {self.producto.nombre}"

    class Meta:
        verbose_name = "Baja de Stock"
        verbose_name_plural = "Bajas de Stock"
        ordering = ['-fecha_baja']

class DevolucionAProveedor(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'PENDIENTE', 'Pendiente de envío'
        ENVIADA = 'ENVIADA', 'Enviada a proveedor'
        RECIBIDO_PARCIAL = 'RECIBIDO_PARCIAL', 'Recibido Parcialmente'
        COMPLETADA = 'COMPLETADA', 'Completada'

    devolucion_origen = models.OneToOneField('Devoluciones.Devolucion', on_delete=models.CASCADE, related_name='gestion_proveedor')
    proveedor = models.ForeignKey('Proveedores.Proveedor', on_delete=models.PROTECT, related_name='devoluciones_gestionadas')
    fecha_envio = models.DateField(null=True, blank=True)
    fecha_recepcion_final = models.DateField(null=True, blank=True, help_text="Fecha en que se recibieron los productos de vuelta o se finalizó.")
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    notas = models.TextField(blank=True, null=True, help_text="Notas internas o comunicación con el proveedor.")

    def __str__(self):
        return f"Gestión con proveedor para Devolución #{self.devolucion_origen.id}"

    class Meta:
        verbose_name = "Devolución a Proveedor"
        verbose_name_plural = "Devoluciones a Proveedores"
        ordering = ['-devolucion_origen__fecha_devolucion']

class ItemDevolucionAProveedor(models.Model):
    gestion_proveedor = models.ForeignKey(DevolucionAProveedor, on_delete=models.CASCADE, related_name='items')
    item_devuelto_origen = models.OneToOneField('Devoluciones.ItemDevuelto', on_delete=models.PROTECT, related_name='item_gestion_proveedor')
    producto_original = models.ForeignKey('Productos.Producto', on_delete=models.PROTECT, related_name='+')
    cantidad_enviada = models.PositiveIntegerField()
    cantidad_recibida = models.PositiveIntegerField(default=0)
    producto_recibido = models.ForeignKey('Productos.Producto', on_delete=models.SET_NULL, null=True, blank=True, help_text="Producto recibido (si es diferente al original).")
    notas_recepcion = models.TextField(blank=True, null=True)
    recepcion_confirmada = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.cantidad_enviada} x {self.producto_original.nombre}"