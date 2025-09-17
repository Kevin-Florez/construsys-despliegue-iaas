# backend_api/Creditos/models.py

from django.db import models, transaction
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
import logging

# Se eliminan las importaciones directas de modelos de otras apps
# from Clientes.models import Cliente
# from Configuracion.models import ConfiguracionSistema

logger = logging.getLogger(__name__)

class Credito(models.Model):
    ESTADO_CHOICES = [
        ('Activo', 'Activo'),
        ('Pagado', 'Pagado'),
        ('Anulado', 'Anulado'),
    ]
    
    # Se usa un string para la relación
    cliente = models.ForeignKey('Clientes.Cliente', on_delete=models.PROTECT, related_name='creditos', verbose_name="Cliente")
    cupo_aprobado = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Cupo Aprobado")
    capital_utilizado = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Suma de las compras que el cliente ha hecho. Reduce el saldo disponible.")
    deuda_del_cupo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Deuda principal originada por el cupo otorgado. Disminuye con los abonos.")
    intereses_acumulados = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Suma de los intereses generados sobre la deuda del cupo.")
    tasa_interes_mensual = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Tasa de Interés Mensual Aplicada (%)")
    fecha_otorgamiento = models.DateField(default=timezone.localdate, verbose_name="Fecha de Otorgamiento")
    plazo_dias = models.PositiveIntegerField(default=30, verbose_name="Plazo del Crédito (días)")
    fecha_ultimo_calculo_interes = models.DateField(verbose_name="Fecha del Último Cálculo de Interés")
    estado = models.CharField(max_length=20, choices=ESTADO_CHOICES, default='Activo', verbose_name="Estado del Crédito")
    fecha_creacion_registro = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion_registro = models.DateTimeField(auto_now=True)
    
    # ... (todos los @property y métodos se mantienen igual)
    @property
    def get_cliente_info_display(self):
        if self.cliente:
            doc_map = {
                'Cédula de Ciudadanía': 'C.C',
                'Tarjeta de Identidad (Menor de edad)': 'T.I',
                'Cédula de Extranjería': 'C.E',
                'Pasaporte': 'PASS',
                'NIT': 'NIT',
            }
            tipo_doc_largo = self.cliente.get_tipo_documento_display() or ''
            tipo_doc_corto = doc_map.get(tipo_doc_largo, tipo_doc_largo)
            doc = self.cliente.documento or ''
            nombre_completo = f"{self.cliente.nombre} {self.cliente.apellido or ''}".strip()
            return f"{nombre_completo} ({tipo_doc_corto} {doc})"
        return "Cliente no especificado"

    @property
    def saldo_disponible_para_ventas(self):
        return self.cupo_aprobado - self.capital_utilizado

    @property
    def fecha_vencimiento(self):
        if self.fecha_otorgamiento:
            return self.fecha_otorgamiento + timedelta(days=self.plazo_dias)
        return None

    @property
    def deuda_total_con_intereses(self):
        return self.deuda_del_cupo + self.intereses_acumulados

    def __str__(self):
        return f"Crédito #{self.id} - {self.cliente} - Cupo: ${self.cupo_aprobado:,.0f}"

    def actualizar_intereses(self, guardar=False):
        hoy = timezone.localdate()
        if self.estado != 'Activo' or self.fecha_ultimo_calculo_interes >= hoy:
            return False
        if self.deuda_del_cupo <= 0:
            self.fecha_ultimo_calculo_interes = hoy
            if guardar:
                self.save(update_fields=['fecha_ultimo_calculo_interes'])
            return False
        tasa_diaria = (self.tasa_interes_mensual / Decimal('100')) / Decimal('30')
        dias_a_calcular = (hoy - self.fecha_ultimo_calculo_interes).days
        if dias_a_calcular <= 0:
            return False
        interes_generado = self.deuda_del_cupo * tasa_diaria * Decimal(dias_a_calcular)
        if interes_generado > 0:
            self.intereses_acumulados += interes_generado
            self.fecha_ultimo_calculo_interes = hoy
            logger.info(f"Crédito #{self.id}: Intereses actualizados. Generado: ${interes_generado:,.2f}. Total ahora: ${self.intereses_acumulados:,.2f}")
            if guardar:
                with transaction.atomic():
                    Credito.objects.filter(pk=self.pk).update(
                        intereses_acumulados=self.intereses_acumulados,
                        fecha_ultimo_calculo_interes=self.fecha_ultimo_calculo_interes
                    )
            return True
        return False

    def save(self, *args, **kwargs):
        # Se importa aquí para la lógica de negocio, no afecta a las migraciones
        from Configuracion.models import ConfiguracionSistema
        is_new = not self.pk
        if is_new:
            config = ConfiguracionSistema.obtener_configuracion()
            self.tasa_interes_mensual = config.tasa_interes_mensual_credito
            self.fecha_ultimo_calculo_interes = self.fecha_otorgamiento
            self.deuda_del_cupo = self.cupo_aprobado
        else:
            if self.estado == 'Activo':
                if self.deuda_del_cupo <= Decimal('0.00') and self.intereses_acumulados <= Decimal('0.00'):
                    self.estado = 'Pagado'
                    logger.info(f"Crédito #{self.id} ha sido completamente pagado. Cambiando estado a 'Pagado'.")
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Cuenta de Crédito"
        verbose_name_plural = "Cuentas de Crédito"
        ordering = ['-fecha_otorgamiento', '-id']

class AbonoCredito(models.Model):
    ESTADO_ABONO_CHOICES = [
        ('Pendiente', 'Pendiente de Verificación'),
        ('Verificado', 'Verificado'),
        ('Rechazado', 'Rechazado'),
    ]
    # La relación con Credito es intra-app, no es necesario cambiarla, pero se mantiene por consistencia
    credito = models.ForeignKey('Creditos.Credito', on_delete=models.PROTECT, related_name='abonos', verbose_name="Cuenta de Crédito")
    fecha_abono = models.DateField(default=timezone.now, verbose_name="Fecha del Abono")
    monto = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto del Abono")
    metodo_pago = models.CharField(max_length=50, blank=True, null=True, verbose_name="Método de Pago")
    comprobante = models.FileField(upload_to='comprobantes_abonos/', blank=True, null=True, verbose_name="Comprobante de Pago")
    estado = models.CharField(max_length=20, choices=ESTADO_ABONO_CHOICES, default='Pendiente', verbose_name="Estado del Abono")
    motivo_rechazo = models.TextField(blank=True, null=True, verbose_name="Motivo del Rechazo", help_text="Razón por la cual el abono fue rechazado.")
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Registro")

    def __str__(self):
        return f"Abono de ${self.monto:,.2f} a Crédito #{self.credito.id} ({self.get_estado_display()})"

    class Meta:
        verbose_name = "Abono a Crédito"
        verbose_name_plural = "Abonos a Créditos"
        ordering = ['-fecha_abono', '-id']

class SolicitudCredito(models.Model):
    ESTADO_SOLICITUD_CHOICES = [
        ('Pendiente', 'Pendiente de Revisión'),
        ('Aprobada', 'Aprobada'),
        ('Rechazada', 'Rechazada'),
    ]

    # Se usa un string para la relación
    cliente = models.ForeignKey('Clientes.Cliente', on_delete=models.PROTECT, related_name='solicitudes_credito', verbose_name="Cliente")
    monto_solicitado = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Monto Solicitado")
    plazo_dias_solicitado = models.PositiveIntegerField(default=30, verbose_name="Plazo Solicitado (días)")
    estado = models.CharField(max_length=20, choices=ESTADO_SOLICITUD_CHOICES, default='Pendiente', verbose_name="Estado de la Solicitud")
    fecha_solicitud = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de Solicitud")
    fecha_decision = models.DateTimeField(null=True, blank=True, verbose_name="Fecha de Decisión")
    motivo_decision = models.TextField(blank=True, help_text="Razón para aprobar o rechazar la solicitud.", verbose_name="Notas del Administrador")
    monto_aprobado = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Monto Aprobado", help_text="Monto final aprobado por el administrador. Puede ser diferente al solicitado.")
    
    credito_generado = models.OneToOneField(
        'Creditos.Credito', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='solicitud_origen',
        verbose_name="Crédito Generado"
    )

    def __str__(self):
        return f"Solicitud de {self.cliente} por ${self.monto_solicitado:,.0f} ({self.get_estado_display()})"
    
    class Meta:
        verbose_name = "Solicitud de Crédito"
        verbose_name_plural = "Solicitudes de Crédito"
        ordering = ['-fecha_solicitud']