# Pedidos/models.py

import uuid
from django.db import models, transaction
from django.utils import timezone
from decimal import Decimal
import logging
from django.db.models import Q
from django.core.exceptions import ValidationError
from datetime import timedelta

# Se eliminan las importaciones directas de modelos de otras apps
# from Clientes.models import Cliente
# from Productos.models import Producto
# from Creditos.models import Credito

logger = logging.getLogger(__name__)

class ComprobantePago(models.Model):
    pedido = models.ForeignKey('Pedido', on_delete=models.CASCADE, related_name='comprobantes', verbose_name="Pedido Asociado")
    imagen = models.ImageField(upload_to='comprobantes/', verbose_name="Imagen del Comprobante")
    fecha_subida = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Subida")
    monto_verificado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Monto Verificado")
    verificado = models.BooleanField(default=False, verbose_name="Verificado")

    def __str__(self):
        return f"Comprobante para Pedido #{self.pedido.id} - Subido el {self.fecha_subida.strftime('%Y-%m-%d')}"

    class Meta:
        verbose_name = "Comprobante de Pago"
        verbose_name_plural = "Comprobantes de Pago"
        ordering = ['-fecha_subida']

class Pedido(models.Model):
    ESTADO_CHOICES = [('pendiente_pago', 'Pendiente de Pago'), ('pendiente_pago_temporal', 'Pendiente de Pago (1h)'), ('en_verificacion', 'En Verificación de Pago'), ('pago_incompleto', 'Pago Incompleto'), ('confirmado', 'Confirmado y en Preparación'), ('en_camino', 'En Camino'), ('entregado', 'Entregado'), ('cancelado', 'Cancelado'), ('cancelado_por_inactividad', 'Cancelado por Inactividad')]
    METODO_ENTREGA_CHOICES = [('domicilio', 'Domicilio'), ('tienda', 'Reclamar en Tienda')]

    id = models.AutoField(primary_key=True)
    # Se usan strings para las relaciones
    cliente = models.ForeignKey('Clientes.Cliente', on_delete=models.SET_NULL, null=True, blank=True, related_name='pedidos', verbose_name="Cliente Registrado", db_constraint=False)
    
    token_seguimiento = models.UUIDField(default=uuid.uuid4, editable=False, unique=True, db_index=True)
    email_invitado = models.EmailField(max_length=254, blank=True, null=True, verbose_name="Email del Invitado")
    tipo_documento_invitado = models.CharField(max_length=3, blank=True, null=True)
    documento_invitado = models.CharField(max_length=20, blank=True, null=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Creación")
    estado = models.CharField(max_length=30, choices=ESTADO_CHOICES, default='pendiente_pago', verbose_name="Estado")
    fecha_limite_pago = models.DateTimeField(null=True, blank=True, verbose_name="Fecha límite para pago")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    iva = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total = models.DecimalField(max_digits=12, decimal_places=2)
    metodo_entrega = models.CharField(max_length=20, choices=METODO_ENTREGA_CHOICES, default='domicilio')
    nombre_receptor = models.CharField(max_length=200, verbose_name="Nombre de quien recibe")
    telefono_receptor = models.CharField(max_length=20, verbose_name="Teléfono de contacto")
    direccion_entrega = models.CharField(max_length=255, verbose_name="Dirección de Entrega", blank=True, null=True)

    # Se usan strings para las relaciones
    credito_usado = models.ForeignKey('Creditos.Credito', on_delete=models.SET_NULL, null=True, blank=True, related_name='pedidos_asociados')
    
    monto_usado_credito = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    monto_pagado_verificado = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name="Monto Total Pagado y Verificado")
    motivo_cancelacion = models.TextField(blank=True, null=True, verbose_name="Motivo de la Cancelación")
    
    venta_asociada = models.OneToOneField('Ventas.Venta', on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Venta Asociada")
    
    es_carrito_activo = models.BooleanField(default=False, verbose_name="¿Es carrito activo?")
    
    # ... (todos los métodos se mantienen igual, pero las importaciones necesarias se mueven dentro de ellos)
    @transaction.atomic
    def descontar_stock(self):
        logger.info(f"Iniciando descuento de stock para el Pedido #{self.id}.")
        for detalle in self.detalles.all():
            producto = detalle.producto
            if producto.stock_actual < detalle.cantidad:
                logger.error(f"Stock insuficiente para {producto.nombre} (ID: {producto.id}) en Pedido #{self.id}.")
                raise ValidationError(f"No hay stock suficiente para '{producto.nombre}'. Disponible: {producto.stock_actual}, Requerido: {detalle.cantidad}.")
            
            producto.stock_actual -= detalle.cantidad
            producto.save(update_fields=['stock_actual'])
            logger.info(f"Stock de '{producto.nombre}' actualizado a {producto.stock_actual}.")
        logger.info(f"Descuento de stock completado para el Pedido #{self.id}.")

    @transaction.atomic
    def restaurar_stock(self):
        logger.info(f"Restaurando stock para el Pedido cancelado #{self.id}.")
        for detalle in self.detalles.all():
            if detalle.producto:
                producto = detalle.producto
                producto.stock_actual += detalle.cantidad
                producto.save(update_fields=['stock_actual'])
                logger.info(f"Stock de '{producto.nombre}' restaurado a {producto.stock_actual}.")

    @transaction.atomic
    def _process_confirmation(self):
        if self.estado == 'confirmado' and not self.venta_asociada:
            try:
                # Importaciones locales al método
                from Ventas.models import Venta, DetalleVenta
                from Clientes.models import Cliente
                
                if self.cliente:
                    cliente_para_venta = self.cliente
                else:
                    try:
                        cliente_para_venta = Cliente.objects.get(Q(documento=self.documento_invitado) | Q(correo=self.email_invitado))
                    except Cliente.DoesNotExist:
                        cliente_para_venta = Cliente.objects.create(nombre=self.nombre_receptor, correo=self.email_invitado, telefono=self.telefono_receptor, tipo_documento=self.tipo_documento_invitado or 'NIT', documento=self.documento_invitado or self.email_invitado, activo=True, es_invitado_temporal=True)
                        logger.info(f"Cliente temporal ID {cliente_para_venta.id} creado para el pedido de invitado #{self.id}.")

                self.descontar_stock()
                
                venta = Venta.objects.create(cliente=cliente_para_venta, subtotal=self.subtotal, iva=self.iva, total=self.total, estado='Completada', credito_usado=self.credito_usado, monto_cubierto_con_credito=self.monto_usado_credito, monto_pago_adicional=self.total - self.monto_usado_credito, metodo_pago_adicional='Transferencia' if self.monto_usado_credito < self.total else None, pedido_origen=self)
                
                for detalle in self.detalles.all():
                    DetalleVenta.objects.create(venta=venta, producto=detalle.producto, producto_nombre_historico=detalle.producto.nombre, precio_unitario_venta=detalle.precio_unitario, cantidad=detalle.cantidad)
                
                self.venta_asociada = venta
                Pedido.objects.filter(pk=self.pk).update(venta_asociada=venta)
                logger.info(f"Venta ID {venta.id} creada y asociada al Pedido ID {self.id}.")
                
            except ValidationError as e:
                self.estado = 'pago_incompleto'
                Pedido.objects.filter(pk=self.pk).update(estado='pago_incompleto')
                raise e
            except Exception as e:
                logger.error(f"Error al crear la venta para el pedido {self.id}: {e}")
                self.estado = 'pago_incompleto'
                Pedido.objects.filter(pk=self.pk).update(estado='pago_incompleto')
                raise ValidationError(f"Hubo un error al procesar el pedido. Contacta al administrador. Detalle: {e}")

    def save(self, *args, **kwargs):
        is_new = not self.pk
        estado_anterior = None
        if not is_new:
            try:
                original = Pedido.objects.get(pk=self.pk)
                estado_anterior = original.estado
            except Pedido.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        if self.estado in ['cancelado', 'cancelado_por_inactividad'] and estado_anterior == 'confirmado':
            self.restaurar_stock()
            if self.venta_asociada:
                self.venta_asociada.estado = 'Anulada'
                self.venta_asociada.save()
                logger.info(f"Venta ID {self.venta_asociada.id} asociada al Pedido ID {self.id} ha sido anulada.")
                      
    def __str__(self):
        if self.cliente:
            return f"Pedido #{self.id} - {self.cliente.nombre}"
        return f"Pedido Invitado #{self.id} - {self.email_invitado}"

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"
        ordering = ['-fecha_creacion']
        constraints = [models.UniqueConstraint(fields=['cliente', 'es_carrito_activo'], condition=models.Q(es_carrito_activo=True), name='unique_active_cart_per_customer')]

class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='detalles', verbose_name="Pedido", db_constraint=False, null=True)
    # Se usa un string para la relación
    producto = models.ForeignKey('Productos.Producto', on_delete=models.SET_NULL, null=True, verbose_name="Producto", db_constraint=False)
    cantidad = models.PositiveIntegerField(verbose_name="Cantidad")
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Precio Unitario en el Momento de la Compra")

    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def __str__(self):
        producto_nombre = self.producto.nombre if self.producto else "Producto Eliminado"
        return f"{self.cantidad} x {producto_nombre} en Pedido #{self.pedido.id}"

    class Meta:
        verbose_name = "Detalle de Pedido"
        verbose_name_plural = "Detalles de Pedidos"