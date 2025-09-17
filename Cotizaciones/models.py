# Cotizaciones/models.py

from django.db import models
from django.utils import timezone
from datetime import timedelta
import uuid
from decimal import Decimal



class Cotizacion(models.Model):
    ESTADO_CHOICES = [
        ('vigente', 'Vigente'),
        ('convertida', 'Convertida en Pedido'),
        ('vencida', 'Vencida'),
    ]

    id = models.AutoField(primary_key=True)
    token_acceso = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    
    # Se usa un string para la relación
    cliente = models.ForeignKey(
        'Clientes.Cliente', 
        on_delete=models.SET_NULL,
        null=True, 
        blank=True, 
        related_name='cotizaciones'
    )
    email_invitado = models.EmailField(max_length=254, blank=True, null=True)
    nombre_invitado = models.CharField(max_length=200, blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_vencimiento = models.DateTimeField()
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='vigente')
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    iva = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    def save(self, *args, **kwargs):
        if not self.pk:
            self.fecha_vencimiento = timezone.now() + timedelta(days=15)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.fecha_vencimiento

    def __str__(self):
        if self.cliente:
            return f"Cotización #{self.id} para {self.cliente.nombre}"
        return f"Cotización #{self.id} para invitado ({self.email_invitado})"

    class Meta:
        verbose_name = "Cotización"
        verbose_name_plural = "Cotizaciones"
        ordering = ['-fecha_creacion']

class DetalleCotizacion(models.Model):
    cotizacion = models.ForeignKey(Cotizacion, on_delete=models.CASCADE, related_name='detalles')
    # Se usa un string para la relación
    producto = models.ForeignKey('Productos.Producto', on_delete=models.SET_NULL, null=True)
    
    producto_nombre_historico = models.CharField(max_length=200)
    cantidad = models.PositiveIntegerField()
    precio_unitario_cotizado = models.DecimalField(max_digits=12, decimal_places=2)

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario_cotizado

    def save(self, *args, **kwargs):
        if self.producto and not self.producto_nombre_historico:
            self.producto_nombre_historico = self.producto.nombre
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.cantidad} x {self.producto_nombre_historico} en Cotización #{self.cotizacion.id}"

    class Meta:
        verbose_name = "Detalle de Cotización"
        verbose_name_plural = "Detalles de Cotización"