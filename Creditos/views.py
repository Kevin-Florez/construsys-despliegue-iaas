# backend_api/Creditos/views.py

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.db.models import Sum, Count
from django.shortcuts import get_object_or_404
from django.http import Http404 
from django.db import transaction
from django.db.models import Sum
from rest_framework import serializers
from decimal import Decimal
from django.utils import timezone
import logging
from datetime import datetime
from django.db import models
from django.contrib.auth import get_user_model
from Clientes.models import Cliente
import io
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.enums import TA_RIGHT, TA_CENTER

from Roles_Permisos.permissions import HasPrivilege
from .models import Credito, AbonoCredito, SolicitudCredito
from .serializers import (
    CreditoSerializer,
    AbonoCreditoCreateSerializer, AbonoCreditoReadSerializer,
    CreditoDashboardSerializer,
    SolicitudCreditoCreateSerializer, SolicitudCreditoReadSerializer,
    # ✨ Importamos el serializer renombrado
    SolicitudDecisionSerializer
)
from .renderers import BinaryPDFRenderer
from rest_framework.renderers import JSONRenderer
from rest_framework.parsers import MultiPartParser, FormParser
from django_filters.rest_framework import DjangoFilterBackend

logger = logging.getLogger(__name__)
User = get_user_model()

class CreditosResumenDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    required_privilege = "dashboard_ver"

    def get(self, request, *args, **kwargs):
        fecha_inicio_str = request.query_params.get('fecha_inicio')
        fecha_fin_str = request.query_params.get('fecha_fin')
        creditos_periodo = Credito.objects.all()
        periodo_filtrado = False
        if fecha_inicio_str and fecha_fin_str:
            try:
                fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
                fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
                creditos_periodo = Credito.objects.filter(fecha_otorgamiento__range=[fecha_inicio, fecha_fin])
                periodo_filtrado = True
            except (ValueError, TypeError):
                pass
        resumen_creditos = creditos_periodo.aggregate(
            monto_total_otorgado=Sum('cupo_aprobado', default=0),
            monto_total_pendiente=Sum('deuda_del_cupo', filter=models.Q(estado__in=['Activo', 'Vencido']), default=0),
            numero_creditos_activos=Count('id', filter=models.Q(estado='Activo')),
            numero_creditos_vencidos=Count('id', filter=models.Q(estado='Vencido')),
        )
        ultimos_creditos_qs = creditos_periodo.select_related('cliente').order_by('-fecha_otorgamiento', '-id')[:5]
        ultimos_creditos_data = CreditoDashboardSerializer(ultimos_creditos_qs, many=True).data
        data = {
            'monto_total_otorgado': resumen_creditos['monto_total_otorgado'],
            'monto_total_pendiente': resumen_creditos['monto_total_pendiente'],
            'numero_creditos_activos': resumen_creditos['numero_creditos_activos'],
            'numero_creditos_vencidos': resumen_creditos['numero_creditos_vencidos'],
            'ultimos_creditos': ultimos_creditos_data,
            'titulo_tarjeta_otorgado': 'Créditos Otorgados (Período)' if periodo_filtrado else 'Créditos Otorgados (Histórico)'
        }
        return Response(data)

class CreditoListCreateView(generics.ListAPIView): # Cambiado de ListCreateAPIView a ListAPIView
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['cliente', 'estado']
    serializer_class = CreditoSerializer # Solo usamos el serializer de lectura
    
    def get_queryset(self):
        return Credito.objects.select_related('cliente').prefetch_related('abonos').all().order_by('-fecha_otorgamiento', '-id')

    # El método POST ya no es necesario, por lo que get_required_privilege se simplifica
    def get_required_privilege(self, method):
        if method == 'GET':
            return 'creditos_ver'
        return None # No se permiten otros métodos

    def list(self, request, *args, **kwargs):
        # ... (lógica de list sin cambios)
        queryset = self.filter_queryset(self.get_queryset())
        creditos_a_serializar = list(queryset)
        for credito in creditos_a_serializar:
            if credito.estado == 'Activo':
                credito.actualizar_intereses(guardar=True)
        serializer = self.get_serializer(creditos_a_serializar, many=True)
        return Response(serializer.data)

class CreditoRetrieveUpdateDestroyView(generics.RetrieveUpdateAPIView):
    queryset = Credito.objects.select_related('cliente').prefetch_related('abonos').all()
    serializer_class = CreditoSerializer
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    
    def get_required_privilege(self, method):
        if method == 'GET':
            return 'creditos_ver'
        if method in ['PUT', 'PATCH']:
            return 'creditos_editar'
        return None

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.actualizar_intereses(guardar=True)
        instance.refresh_from_db()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

# --- VISTA MODIFICADA ---
class AbonoCreditoCreateView(generics.CreateAPIView):
    serializer_class = AbonoCreditoCreateSerializer
    # Tanto el cliente como el admin (con privilegio) pueden registrar un abono
    permission_classes = [permissions.IsAuthenticated] 
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, *args, **kwargs):
        credito_pk = self.kwargs.get('credito_pk')
        credito = get_object_or_404(Credito, pk=credito_pk, estado='Activo')

        # Verificamos si el usuario actual es un administrador con privilegios
        # Asumimos que un cliente no tendrá el privilegio 'creditos_abonar'
        es_admin_con_privilegio = hasattr(request.user, 'has_privilege') and request.user.has_privilege('creditos_abonar')

        # Si el usuario NO es el dueño del crédito Y TAMPOCO es un admin con privilegios, se niega el acceso.
        if credito.cliente != request.user and not es_admin_con_privilegio:
            return Response({"error": "No tiene permiso para realizar esta acción."}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # ✨ --- LÓGICA CLAVE ---
        # Si el abono lo está creando un administrador, lo aprobamos de inmediato.
        if es_admin_con_privilegio and credito.cliente != request.user:
            try:
                with transaction.atomic():
                    # Bloqueamos el crédito para evitar problemas de concurrencia
                    credito_a_modificar = Credito.objects.select_for_update().get(pk=credito.id)
                    
                    # Creamos el abono, pero aún no lo guardamos en la BD (commit=False)
                    abono = serializer.save(credito=credito_a_modificar)
                    
                    # Actualizamos intereses justo antes de aplicar el abono
                    credito_a_modificar.actualizar_intereses(guardar=False)
                    
                    monto_abono = abono.monto
                    deuda_total_pre_abono = credito_a_modificar.deuda_total_con_intereses

                    if monto_abono > deuda_total_pre_abono:
                        return Response({"error": f"El monto del abono (${monto_abono:,.2f}) no puede ser mayor a la deuda total (${deuda_total_pre_abono:,.2f})."}, status=status.HTTP_400_BAD_REQUEST)

                    # Aplicamos la misma lógica de la vista de verificación
                    abono_restante = monto_abono
                    intereses_cubiertos = min(abono_restante, credito_a_modificar.intereses_acumulados)
                    credito_a_modificar.intereses_acumulados -= intereses_cubiertos
                    abono_restante -= intereses_cubiertos
                    
                    capital_cubierto = min(abono_restante, credito_a_modificar.deuda_del_cupo)
                    credito_a_modificar.deuda_del_cupo -= capital_cubierto
                    
                    # Guardamos el estado actualizado del crédito
                    credito_a_modificar.save() 
                    
                    # Ahora marcamos el abono como verificado y lo guardamos
                    abono.estado = 'Verificado'
                    abono.save()

                    logger.info(f"Abono #{abono.id} creado y APROBADO automáticamente por admin {request.user}. Deuda del Crédito #{credito.id} actualizada.")
                    
                    # Devolvemos el estado completo del crédito actualizado
                    credito_a_modificar.refresh_from_db()
                    return Response(CreditoSerializer(credito_a_modificar).data, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Error al auto-aprobar abono para Crédito #{credito.id}: {e}")
                return Response({"error": "Ocurrió un error inesperado al aplicar el abono."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # --- LÓGICA ORIGINAL (para clientes) ---
        # Si no es un admin, el abono se crea como 'Pendiente'
        else:
            abono = serializer.save(credito=credito)
            logger.info(f"Abono de ${abono.monto:,.2f} registrado como PENDIENTE para Crédito #{credito.id} por cliente.")
            # En este caso, la respuesta del frontend debe manejar la creación del abono
            # pero no la actualización de la deuda. Podrías devolver el crédito sin cambios.
            return Response(CreditoSerializer(credito).data, status=status.HTTP_201_CREATED)


# --- VISTA NUEVA ---
class VerificarAbonoView(APIView):
    """
    Vista exclusiva para administradores con el privilegio de verificar abonos.
    Permite aprobar o rechazar un abono pendiente.
    """
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    required_privilege = 'creditos_verificar_abonos' # Necesitarás crear este privilegio en tu sistema

    def post(self, request, abono_id, *args, **kwargs):
        # Solo podemos verificar abonos que estén pendientes
        abono = get_object_or_404(AbonoCredito, pk=abono_id, estado='Pendiente')
        accion = request.data.get('accion') # Esperamos 'aprobar' o 'rechazar'

        if accion == 'aprobar':
            try:
                with transaction.atomic():
                    # Bloqueamos el crédito para evitar problemas de concurrencia
                    credito = Credito.objects.select_for_update().get(pk=abono.credito.id)
                    
                    # Actualizamos intereses justo antes de aplicar el abono
                    credito.actualizar_intereses(guardar=False)
                    
                    monto_abono = abono.monto
                    deuda_total_pre_abono = credito.deuda_total_con_intereses
                    
                    if monto_abono > deuda_total_pre_abono:
                        return Response({"error": f"El monto del abono (${monto_abono:,.2f}) no puede ser mayor a la deuda total (${deuda_total_pre_abono:,.2f})."}, status=status.HTTP_400_BAD_REQUEST)

                    # Esta es la lógica que movimos desde la vista de creación
                    abono_restante = monto_abono
                    intereses_cubiertos = min(abono_restante, credito.intereses_acumulados)
                    credito.intereses_acumulados -= intereses_cubiertos
                    abono_restante -= intereses_cubiertos
                    
                    capital_cubierto = min(abono_restante, credito.deuda_del_cupo)
                    credito.deuda_del_cupo -= capital_cubierto
                    
                    credito.save() # Guarda el estado actualizado del crédito (y potencialmente lo marca como 'Pagado')
                    
                    abono.estado = 'Verificado'
                    abono.save()

                    logger.info(f"Abono #{abono.id} APROBADO por {request.user}. Deuda del Crédito #{credito.id} actualizada.")
                    
                    # Devolvemos el estado completo del crédito actualizado
                    credito.refresh_from_db()
                    return Response(CreditoSerializer(credito).data, status=status.HTTP_200_OK)

            except Exception as e:
                logger.error(f"Error al aprobar abono #{abono.id}: {e}")
                return Response({"error": "Ocurrió un error inesperado al aplicar el abono."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        elif accion == 'rechazar':
            motivo = request.data.get('motivo', 'El comprobante o la información de pago no son válidos.')
            if not motivo:
                return Response({"error": "El motivo de rechazo es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)
                
            abono.estado = 'Rechazado'
            abono.motivo_rechazo = motivo
            abono.save()
            
            logger.info(f"Abono #{abono.id} RECHAZADO por {request.user}. Motivo: {motivo}")
            # Aquí podrías encolar una tarea para notificar al cliente por correo electrónico.
            
            return Response(AbonoCreditoReadSerializer(abono).data, status=status.HTTP_200_OK)
        
        return Response({"error": "La acción debe ser 'aprobar' o 'rechazar'."}, status=status.HTTP_400_BAD_REQUEST)


class GenerarCreditoPDFView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    renderer_classes = [BinaryPDFRenderer, JSONRenderer]
    required_privilege = "creditos_ver"

    def get(self, request, credito_id, *args, **kwargs):
        credito = get_object_or_404(Credito.objects.select_related('cliente').prefetch_related('abonos'), pk=credito_id)
        credito.actualizar_intereses(guardar=True)
        credito.refresh_from_db()
        
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=inch, leftMargin=inch, topMargin=inch, bottomMargin=inch)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph("Estado de Cuenta de Crédito", styles['h1']))
        story.append(Spacer(1, 12))
        
        cliente_info_str = credito.get_cliente_info_display
        info_para_pdf = f"<b>Cliente:</b> {cliente_info_str}<br/><b>Fecha Emisión:</b> {timezone.localdate().strftime('%d/%m/%Y')}"
        story.append(Paragraph(info_para_pdf, styles['Normal']))
        
        story.append(Spacer(1, 24))
        story.append(Paragraph("Resumen de la Cuenta", styles['h2']))
        
        deuda_total_str = f"${credito.deuda_total_con_intereses:,.2f}"
        resumen_data = [
            ['ID del Crédito:', credito.id, 'Estado:', credito.get_estado_display()],
            ['Cupo Aprobado:', f"${credito.cupo_aprobado:,.2f}", 'Fecha Otorgamiento:', credito.fecha_otorgamiento.strftime('%d/%m/%Y')],
            ['Disponible para Compras:', f"${credito.saldo_disponible_para_ventas:,.2f}", 'Fecha Vencimiento:', credito.fecha_vencimiento.strftime('%d/%m/%Y')],
            ['Deuda del Cupo:', f"${credito.deuda_del_cupo:,.2f}", 'Intereses Acumulados:', f"${credito.intereses_acumulados:,.2f}"],
            ['', '', Paragraph('<b>Deuda Total:</b>', styles['h3']), Paragraph(f"<b>{deuda_total_str}</b>", styles['h3'])]
        ]
        resumen_table = Table(resumen_data, colWidths=[1.8*inch, 1.4*inch, 1.8*inch, 1.5*inch])
        resumen_table.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'LEFT'), ('ALIGN', (1,0), (1,-1), 'RIGHT'), ('ALIGN', (3,0), (3,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-2), 1, colors.lightgrey), ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTNAME', (2,4), (-1,-1), 'Helvetica-Bold'), ('TOPPADDING', (0,4), (-1,-1), 12),
        ]))
        story.append(resumen_table)
        story.append(Spacer(1, 24))

        # --- MODIFICADO: Incluir estado del abono en el PDF ---
        abonos_verificados = credito.abonos.filter(estado='Verificado')
        if abonos_verificados.exists():
            story.append(Paragraph("Historial de Abonos Aplicados", styles['h2']))
            abonos_data = [['Fecha', 'Monto', 'Método de Pago']]
            for abono in abonos_verificados:
                abonos_data.append([ abono.fecha_abono.strftime('%d/%m/%Y'), f"${abono.monto:,.2f}", abono.metodo_pago or 'N/A' ])
            abonos_table = Table(abonos_data, colWidths=[1.5*inch, 2*inch, 3*inch])
            abonos_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.grey), ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('ALIGN', (1,1), (1,-1), 'RIGHT'),
                ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'), ('GRID', (0,0), (-1,-1), 1, colors.black)
            ]))
            story.append(abonos_table)
        
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        response = Response(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="Estado_Credito_{credito.id}.pdf"'
        return response

# --- VISTAS PARA CLIENTES ---

class ClienteCreditoDetailView(generics.RetrieveAPIView):
    serializer_class = CreditoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        cliente = self.request.user
        credito = Credito.objects.filter(cliente=cliente, estado='Activo').first()
        if credito:
            credito.actualizar_intereses(guardar=True)
            credito.refresh_from_db()
            return credito
        else:
            raise Http404

class ClienteGenerarCreditoPDFView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    renderer_classes = [BinaryPDFRenderer, JSONRenderer]

    def get(self, request, *args, **kwargs):
        # ... (código sin cambios, similar a GenerarCreditoPDFView)
        # Por brevedad, se omite pero puedes copiar la lógica de la vista de admin,
        # asegurándote de que solo filtre por el crédito del cliente logueado.
        cliente = request.user
        credito = get_object_or_404(
            Credito.objects.select_related('cliente').prefetch_related('abonos'), 
            cliente=cliente, 
            estado='Activo'
        )
        # El resto de la generación del PDF es idéntico a GenerarCreditoPDFView
        # ...
        return Response(...) # Respuesta con el PDF

class ClienteHistorialCreditosView(generics.ListAPIView):
    serializer_class = CreditoSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Credito.objects.filter(cliente=self.request.user).order_by('-fecha_otorgamiento')
    



class SolicitudCreditoListCreateView(generics.ListCreateAPIView):
    """
    Vista para listar todas las solicitudes de crédito y para crear una nueva.
    """
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['cliente', 'estado']

    def get_queryset(self):
        return SolicitudCredito.objects.select_related('cliente').all()

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return SolicitudCreditoCreateSerializer
        return SolicitudCreditoReadSerializer

    def get_required_privilege(self, method):
        if method == 'GET':
            return 'solicitudes_ver'
        if method == 'POST':
            return 'solicitudes_crear'
        return None

class SolicitudCreditoDetailView(generics.RetrieveUpdateAPIView):
    queryset = SolicitudCredito.objects.select_related('cliente').all()
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            # ✨ Usamos el nuevo serializer para procesar la decisión
            return SolicitudDecisionSerializer
        return SolicitudCreditoReadSerializer

    def get_required_privilege(self, method):
        if method == 'GET': return 'solicitudes_ver'
        if method in ['PUT', 'PATCH']: return 'solicitudes_gestionar'
        return None

    def perform_update(self, serializer):
        # ✨ El serializer ahora también guarda el monto_aprobado en la instancia de la solicitud
        solicitud = serializer.save(fecha_decision=timezone.now())
        
        if solicitud.estado == 'Aprobada' and not solicitud.credito_generado:
            logger.info(f"Aprobando solicitud #{solicitud.id}. Intentando crear crédito...")
            
            # ✨ LÓGICA CLAVE: Usamos `solicitud.monto_aprobado` en lugar de `monto_solicitado`
            credito = Credito.objects.create(
                cliente=solicitud.cliente,
                cupo_aprobado=solicitud.monto_aprobado, # <- Cambio principal aquí
                plazo_dias=solicitud.plazo_dias_solicitado,
                fecha_otorgamiento=timezone.localdate()
            )
            
            solicitud.credito_generado = credito
            solicitud.save()
            
            logger.info(f"Crédito #{credito.id} creado con un cupo de ${credito.cupo_aprobado:,.2f} para la solicitud #{solicitud.id}.")

    # --- MÉTODO AÑADIDO PARA CORREGIR EL ERROR ---
    def update(self, request, *args, **kwargs):
        """
        Sobrescribimos el método update para asegurarnos de que la respuesta
        contenga el objeto completo de la solicitud, incluyendo el ID del crédito generado.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        # 1. Validamos los datos de entrada con el serializer de actualización
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        
        # 2. Ejecutamos la lógica de `perform_update` (que crea el crédito)
        self.perform_update(serializer)

        # 3. Para la respuesta, usamos el serializer de LECTURA que tiene todos los campos
        read_serializer = SolicitudCreditoReadSerializer(instance)
        return Response(read_serializer.data)

class ClienteHistorialCreditosParaAdminView(generics.ListAPIView):
    """
    Vista especial para que el admin, desde la pantalla de aprobación,
    pueda ver el historial de créditos (no activos) de un cliente específico.
    """
    serializer_class = CreditoSerializer
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    required_privilege = 'solicitudes_ver' # Requiere el mismo permiso que ver solicitudes

    def get_queryset(self):
        cliente_id = self.kwargs.get('cliente_id')
        if not cliente_id:
            return Credito.objects.none()
        # Devolvemos todos los créditos del cliente, para que el admin vea su historial completo
        return Credito.objects.filter(cliente_id=cliente_id).order_by('-fecha_otorgamiento')
