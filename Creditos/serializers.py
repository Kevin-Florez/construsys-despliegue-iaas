# backend_api/Creditos/serializers.py

from rest_framework import serializers
from decimal import Decimal
# --- MODIFICADO: Importar el nuevo modelo ---
from .models import Credito, AbonoCredito, SolicitudCredito
from Clientes.models import Cliente


class CreditoDashboardSerializer(serializers.ModelSerializer):
    # ... (código sin cambios)
    cliente_nombre_completo = serializers.CharField(source='cliente.__str__', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    monto_otorgado = serializers.DecimalField(source='cupo_aprobado', max_digits=12, decimal_places=2, read_only=True)
    class Meta:
        model = Credito
        fields = ['id', 'fecha_otorgamiento', 'cliente_nombre_completo', 'estado_display', 'monto_otorgado']


class AbonoCreditoReadSerializer(serializers.ModelSerializer):
    # ... (código sin cambios)
    comprobante_url = serializers.FileField(source='comprobante', read_only=True, use_url=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    class Meta:
        model = AbonoCredito
        fields = [
            'id', 'fecha_abono', 'monto', 'metodo_pago', 'comprobante_url', 
            'fecha_registro', 'estado', 'estado_display', 'motivo_rechazo'
        ]


class AbonoCreditoCreateSerializer(serializers.ModelSerializer):
    # ... (código sin cambios)
    class Meta:
        model = AbonoCredito
        fields = ['monto', 'fecha_abono', 'metodo_pago', 'comprobante']
        extra_kwargs = {'comprobante': {'required': False, 'allow_null': True}}
    def validate_monto(self, value):
        if value <= Decimal('0.00'):
            raise serializers.ValidationError("El monto del abono debe ser un número positivo.")
        return value


class CreditoSerializer(serializers.ModelSerializer):
    # ... (código sin cambios)
    cliente_info = serializers.CharField(source='get_cliente_info_display', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    deuda_del_cupo = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    saldo_disponible_para_ventas = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    fecha_vencimiento = serializers.DateField(read_only=True)
    deuda_total_con_intereses = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    abonos = AbonoCreditoReadSerializer(many=True, read_only=True)
    class Meta:
        model = Credito
        fields = [
            'id', 'cliente', 'cliente_info', 'estado', 'estado_display',
            'cupo_aprobado', 'capital_utilizado', 'deuda_del_cupo', 
            'intereses_acumulados', 'deuda_total_con_intereses',
            'saldo_disponible_para_ventas', 'tasa_interes_mensual',
            'fecha_otorgamiento', 'fecha_vencimiento', 'plazo_dias',
            'fecha_ultimo_calculo_interes', 'abonos',
            'fecha_creacion_registro', 'fecha_actualizacion_registro'
        ]

# --- El antiguo `CreditoCreateSerializer` ahora está obsoleto ---
# Ya no crearemos créditos directamente, sino a través de solicitudes.
# Lo renombramos y adaptamos para crear Solicitudes.

# --- INICIO DE NUEVOS SERIALIZERS ---

class SolicitudCreditoCreateSerializer(serializers.ModelSerializer):
    """
    Serializer para que un administrador cree una nueva solicitud de crédito para un cliente.
    """
    cliente = serializers.PrimaryKeyRelatedField(queryset=Cliente.objects.filter(activo=True))

    class Meta:
        model = SolicitudCredito
        fields = ['cliente', 'monto_solicitado', 'plazo_dias_solicitado']

    def validate_monto_solicitado(self, value):
        if value <= Decimal('0.00'):
            raise serializers.ValidationError("El monto solicitado debe ser un valor positivo.")
        return value

    def validate_cliente(self, cliente_instance):
        # Un cliente no puede tener más de una solicitud PENDIENTE a la vez.
        if SolicitudCredito.objects.filter(cliente=cliente_instance, estado='Pendiente').exists():
            raise serializers.ValidationError(f"El cliente '{cliente_instance}' ya tiene una solicitud de crédito pendiente de revisión.")
        # Tampoco puede solicitar si ya tiene un crédito ACTIVO.
        if Credito.objects.filter(cliente=cliente_instance, estado='Activo').exists():
            raise serializers.ValidationError(f"El cliente '{cliente_instance}' ya tiene una cuenta de crédito activa.")
        return cliente_instance


class SolicitudCreditoReadSerializer(serializers.ModelSerializer):
    cliente_info = serializers.CharField(source='cliente.get_full_info_display', read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    credito_generado_id = serializers.IntegerField(source='credito_generado.id', read_only=True, allow_null=True)

    class Meta:
        model = SolicitudCredito
        fields = [
            'id', 'cliente', 'cliente_info', 'monto_solicitado', 
            # ✨ Se añade el nuevo campo a la respuesta
            'monto_aprobado',
            'plazo_dias_solicitado',
            'estado', 'estado_display', 'fecha_solicitud', 'fecha_decision', 'motivo_decision',
            'credito_generado_id'
        ]


# --- SERIALIZER MODIFICADO Y RENOMBRADO ---
# Renombrado de SolicitudUpdateStatusSerializer a SolicitudDecisionSerializer para ser más claro.
class SolicitudDecisionSerializer(serializers.ModelSerializer):
    """
    Serializer para que el administrador apruebe o rechace una solicitud,
    permitiendo especificar un monto de aprobación.
    """
    # ✨ Se añade el campo para recibir el monto aprobado desde el frontend.
    monto_aprobado = serializers.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        required=False, # No es requerido para rechazar
        min_value=Decimal('0.01')
    )
    
    class Meta:
        model = SolicitudCredito
        fields = ['estado', 'motivo_decision', 'monto_aprobado']
      
    def validate_estado(self, value):
        if self.instance and self.instance.estado != 'Pendiente':
            raise serializers.ValidationError(f"Solo se puede modificar una solicitud que esté en estado 'Pendiente'. Estado actual: {self.instance.get_estado_display()}")
        if value not in ['Aprobada', 'Rechazada']:
            raise serializers.ValidationError("La acción solo puede ser 'Aprobada' o 'Rechazada'.")
        return value

    # ✨ Se añade validación cruzada de campos.
    def validate(self, data):
        """
        Valida que si el estado es 'Aprobada', se proporcione un monto_aprobado.
        """
        estado = data.get('estado')
        monto_aprobado = data.get('monto_aprobado')

        if estado == 'Aprobada' and not monto_aprobado:
            raise serializers.ValidationError({
                'monto_aprobado': 'Debe especificar un monto para aprobar la solicitud.'
            })
        
        return data

# --- FIN DE NUEVOS SERIALIZERS ---