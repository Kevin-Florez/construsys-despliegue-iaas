from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.renderers import JSONRenderer
from django.http import HttpResponse 
from django.db import transaction, models
from collections import defaultdict
from django.db.models import Sum, Count, F, Q
from django.db.models.expressions import RawSQL
from django.db.models.functions import TruncDay, TruncWeek, TruncMonth
from django.shortcuts import get_object_or_404
from django.utils import timezone 
from decimal import Decimal
import logging
from datetime import datetime, timedelta
import io
from datetime import datetime, timedelta, date # ✨ ASEGÚRATE DE QUE 'date' ESTÉ AQUÍ
from rest_framework.permissions import IsAdminUser

# Imports de ReportLab para PDF
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle, Spacer, SimpleDocTemplate
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

from Clientes.models import Cliente
from Creditos.models import Credito
from Productos.models import Producto
from .models import Venta, DetalleVenta
from Pedidos.models import Pedido, DetallePedido

from .serializers import (
    VentaReadSerializer, VentaCreateSerializer, VentaUpdateSerializer,
    VentaDashboardSerializer
)
from Productos.serializers import ProductoDashboardStockSerializer
from Roles_Permisos.permissions import HasPrivilege
from .renderers import BinaryPDFRenderer 

from django.db.models import F, ExpressionWrapper, fields

logger = logging.getLogger(__name__)

# --- VISTA PARA EL DASHBOARD ---
class ResumenGeneralDashboardView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    required_privilege = "dashboard_ver"

    def get(self, request, *args, **kwargs):
        hoy = timezone.now().date()
        fecha_inicio_str = request.query_params.get('fecha_inicio', None)
        fecha_fin_str = request.query_params.get('fecha_fin', None)

        try:
            fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date() if fecha_fin_str else hoy
            fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date() if fecha_inicio_str else fecha_fin - timedelta(days=29)
        except (ValueError, TypeError):
            fecha_fin = hoy
            fecha_inicio = hoy - timedelta(days=29)
        
        periodo_filtrado = bool(fecha_inicio_str and fecha_fin_str)

        # a) Datos de Ventas (Se filtra por ventas y pedidos confirmados)
        ventas_base = Venta.objects.all()
        ventas_hoy_total = ventas_base.filter(fecha=hoy, estado='Completada').aggregate(total=Sum('total', default=Decimal('0.00')))['total']
        ventas_periodo_total = ventas_base.filter(fecha__range=[fecha_inicio, fecha_fin], estado='Completada').aggregate(total=Sum('total', default=Decimal('0.00')))['total']
        
        # b) Datos de Créditos (sin cambios)
        creditos_activos_qs = Credito.objects.filter(estado='Activo')
        cartera_total_agg = creditos_activos_qs.aggregate(
            total_cartera=Sum(F('deuda_del_cupo') + F('intereses_acumulados'), default=Decimal('0.00'))
        )
        cartera_total = cartera_total_agg['total_cartera']
        creditos_activos_count = creditos_activos_qs.count()
        creditos_vencidos_count = creditos_activos_qs.annotate(
            vencimiento_calculado=ExpressionWrapper(
                F('fecha_otorgamiento') + F('plazo_dias') * timedelta(days=1),
                output_field=fields.DateField()
            )
        ).filter(vencimiento_calculado__lt=hoy).count()

        # c) Datos de Productos para Reponer (sin cambios)
        productos_para_reponer_qs = Producto.objects.filter(activo=True, stock_actual__lte=F('stock_minimo')).order_by('stock_actual')[:10]
        
        # d) Ranking de Productos (Ventas + Pedidos)
        detalles_ventas = DetalleVenta.objects.filter(
            venta__fecha__range=[fecha_inicio, fecha_fin], 
            venta__estado='Completada'
        ).values('producto_id', 'producto__nombre').annotate(unidades=Sum('cantidad'))

        detalles_pedidos = DetallePedido.objects.filter(
            pedido__fecha_creacion__date__range=[fecha_inicio, fecha_fin],
            pedido__estado__in=['confirmado', 'en_camino', 'entregado']
        ).values('producto_id', 'producto__nombre').annotate(unidades=Sum('cantidad'))

        unidades_combinadas = defaultdict(int)
        nombres_productos = {}
        for item in list(detalles_ventas) + list(detalles_pedidos):
            if item['producto_id']:
                unidades_combinadas[item['producto_id']] += item['unidades']
                nombres_productos[item['producto_id']] = item['producto__nombre']
        
        ranking_productos = [
            {'producto__nombre': nombres_productos[pid], 'unidades_vendidas': unidades}
            for pid, unidades in unidades_combinadas.items()
        ]
        
        ranking_ordenado = sorted(ranking_productos, key=lambda x: x['unidades_vendidas'], reverse=True)
        
        productos_mas_vendidos = ranking_ordenado[:5]
        productos_menos_vendidos = sorted(ranking_productos, key=lambda x: x['unidades_vendidas'])[:5]

        # e) Tendencia de Ventas (sin cambios)
        delta_dias = (fecha_fin - fecha_inicio).days
        if delta_dias <= 45:
            trunc_kind, date_format = TruncDay('fecha'), "%d %b"
        elif delta_dias <= 365 * 2:
            trunc_kind, date_format = TruncWeek('fecha'), "Sem %W, %y"
        else:
            trunc_kind, date_format = TruncMonth('fecha'), "%b %Y"
        
        tendencia_ventas_qs = ventas_base.filter(fecha__range=[fecha_inicio, fecha_fin], estado='Completada').annotate(periodo=trunc_kind).values('periodo').annotate(total_ventas=Sum('total')).order_by('periodo')
        tendencia_ventas = [{'name': item['periodo'].strftime(date_format), 'ventas': item['total_ventas'] or 0} for item in tendencia_ventas_qs]

        # Ensamblaje de la Respuesta (sin cambios)
        data = {
            "stats_generales": {
                "ventas_hoy": ventas_hoy_total,
                "ventas_periodo": ventas_periodo_total,
                "titulo_ventas_periodo": f'Ventas ({fecha_inicio.strftime("%d %b")} - {fecha_fin.strftime("%d %b")})' if periodo_filtrado else 'Ventas (Últimos 30 días)',
                "cartera_total": cartera_total,
                "creditos_activos": creditos_activos_count,
                "creditos_vencidos": creditos_vencidos_count,
            },
            "productos_para_reponer": ProductoDashboardStockSerializer(productos_para_reponer_qs, many=True).data,
            "productos_mas_vendidos": productos_mas_vendidos,
            "productos_menos_vendidos": productos_menos_vendidos,
            "tendencia_ventas": tendencia_ventas,
        }
        return Response(data)

# --- VISTAS DEL MÓDULO DE VENTAS (SIN CAMBIOS) ---

class VentaListCreateView(generics.ListCreateAPIView):
    queryset = Venta.objects.select_related('cliente', 'devolucion').prefetch_related('detalles__producto').all().order_by('-id')
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return VentaCreateSerializer
        return VentaReadSerializer 

    def get_required_privilege(self, method):
        if method == 'GET':
            return 'ventas_ver'
        if method == 'POST':
            return 'ventas_crear'
        return None

    def perform_create(self, serializer):
        try:
            serializer.save()
        except ValidationError as e:
            raise ValidationError(e.message_dict if hasattr(e, 'message_dict') else e.messages)

class VentaRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Venta.objects.select_related(
    'cliente', 'credito_usado', 'devolucion' # <-- Corregido
).prefetch_related(
    'detalles__producto', 
    'devolucion__items_devueltos__producto', # <-- Corregido
    'devolucion__items_cambio__producto'      # <-- Corregido
).all()
    
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return VentaUpdateSerializer
        return VentaReadSerializer

    def get_required_privilege(self, method):
        if method == 'GET':
            return 'ventas_ver'
        if method in ['PUT', 'PATCH']:
            return 'ventas_anular' 
        return None

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.pop('partial', False))
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
        except (ValidationError, serializers.ValidationError):
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": "Ocurrió un error inesperado.", "detalle": str(e)}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        read_serializer = VentaReadSerializer(instance)
        return Response(read_serializer.data)

    def perform_destroy(self, instance):
        if instance.estado == 'Completada':
            raise ValidationError("No se pueden eliminar ventas completadas. Debe anular la venta primero.")
        super().perform_destroy(instance)

class VentasCompletadasPorClienteView(generics.ListAPIView):
    serializer_class = VentaReadSerializer
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    required_privilege = "ventas_ver" 

    def get_queryset(self):
        cliente_pk = self.kwargs.get('cliente_pk')
        if not cliente_pk: return Venta.objects.none()
        cliente = get_object_or_404(Cliente, pk=cliente_pk)
        return Venta.objects.filter(cliente=cliente, estado='Completada').order_by('-fecha', '-id')

class VentaNoCompletadaError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = "Solo se pueden generar PDFs de ventas en estado 'Completada'."
    default_code = 'venta_no_completada'

class GenerarVentaPDFView(APIView):
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    required_privilege = "ventas_ver"
    renderer_classes = [BinaryPDFRenderer, JSONRenderer]

    def get(self, request, venta_id, *args, **kwargs):
        venta = get_object_or_404(VentaRetrieveUpdateDestroyView.queryset, pk=venta_id)

        tiene_devolucion = hasattr(venta, 'devolucion') and venta.devolucion is not None

        if venta.estado != 'Completada' and not tiene_devolucion:
            raise VentaNoCompletadaError("Solo se pueden generar PDFs de ventas completadas o con devolución.")

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter,
                                rightMargin=inch/2, leftMargin=inch/2,
                                topMargin=inch*1.5, bottomMargin=inch/2)
        story = []
        styles = getSampleStyleSheet()

        # --- Estilos personalizados para el PDF ---
        style_normal = ParagraphStyle('Normal', parent=styles['Normal'], fontSize=9, leading=11)
        style_normal_right = ParagraphStyle(name='NormalRight', parent=style_normal, alignment=TA_RIGHT)
        style_normal_center = ParagraphStyle(name='NormalCenter', parent=style_normal, alignment=TA_CENTER)
        style_bold = ParagraphStyle(name='BoldText', parent=style_normal, fontName='Helvetica-Bold')
        style_bold_right = ParagraphStyle(name='BoldRight', parent=style_bold, alignment=TA_RIGHT)
        style_h2_center = ParagraphStyle(name='H2Center', parent=styles['h2'], alignment=TA_CENTER, fontSize=12, spaceBefore=12, spaceAfter=8)

        # --- Sección 1: Encabezado de la Venta ---
        cliente_info_str = f"<b>CLIENTE:</b> {venta.cliente.nombre} {venta.cliente.apellido or ''}".strip()
        doc_info_str = f"<b>DOC:</b> {venta.cliente.get_tipo_documento_display()} {venta.cliente.documento}"
        
        header_data = [
            [Paragraph(cliente_info_str, style_normal), Paragraph(f"<b>FACTURA N°: {venta.id}</b>", style_normal_right)],
            [Paragraph(doc_info_str, style_normal), Paragraph(f"<b>FECHA VENTA:</b> {venta.fecha.strftime('%d/%m/%Y')}", style_normal_right)],
        ]
        header_table = Table(header_data, colWidths=[4*inch, 3.5*inch])
        header_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 6)]))
        story.append(header_table)
        story.append(Spacer(1, 0.25 * inch))

        # --- Sección 2: Tabla de Productos Vendidos ---
        items_data = [[
            Paragraph("<b>Cant.</b>", style_bold), Paragraph("<b>Descripción</b>", style_bold),
            Paragraph("<b>P. Unit.</b>", style_bold_right), Paragraph("<b>Total</b>", style_bold_right)
        ]]
        for item in venta.detalles.all():
            items_data.append([
                Paragraph(str(item.cantidad), style_normal_center),
                Paragraph(item.producto_nombre_historico, style_normal),
                Paragraph(f"${item.precio_unitario_venta:,.0f}", style_normal_right),
                Paragraph(f"${item.subtotal:,.0f}", style_normal_right)
            ])
        
        items_table = Table(items_data, colWidths=[0.6*inch, 4.4*inch, 1.25*inch, 1.25*inch])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey), 
            ('ALIGN', (0,0), (-1,-1), 'CENTER'), 
            ('ALIGN', (1,1), (1,-1), 'LEFT'),
            ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(items_table)
        
        # --- Sección 3: Totales de la Venta ---
        totals_data = [
            ["", Paragraph("Subtotal:", style_normal_right), Paragraph(f"${venta.subtotal:,.0f}", style_normal_right)],
            ["", Paragraph("IVA (19%):", style_normal_right), Paragraph(f"${venta.iva:,.0f}", style_normal_right)],
            ["", Paragraph("<b>TOTAL VENTA:</b>", style_bold_right), Paragraph(f"<b>${venta.total:,.0f}</b>", style_bold_right)],
        ]
        totals_table = Table(totals_data, colWidths=[4.75*inch, 1.5*inch, 1.25*inch])
        story.append(totals_table)
        story.append(Spacer(1, 0.2*inch))
        
        pago_resumen_str = VentaReadSerializer().get_resumen_pago(venta)
        story.append(Paragraph(f"<b>Forma de Pago:</b> {pago_resumen_str}", style_normal))

        # --- Sección de Devolución (MEJORADA) ---
        if tiene_devolucion:
            devolucion = venta.devolucion
            story.append(Spacer(1, 0.3 * inch))
            story.append(Paragraph("DETALLE DE LA DEVOLUCIÓN", style_h2_center))
            
            info_devolucion_data = [
                [
                    Paragraph(f"<b>Fecha:</b> {devolucion.fecha_devolucion.strftime('%d/%m/%Y')}", style_normal),
                    Paragraph(f"<b>Reembolso:</b> {devolucion.get_tipo_reembolso_display()}", style_normal),
                ],
                [
                    Paragraph(f"<b>Motivo General:</b> {devolucion.motivo_general or 'No especificado'}", style_normal), ""
                ]
            ]
            info_devolucion_table = Table(info_devolucion_data, colWidths=[3.75*inch, 3.75*inch])
            story.append(info_devolucion_table)
            story.append(Spacer(1, 0.1 * inch))

            # Tabla de Productos Devueltos
            if devolucion.items_devueltos.exists():
                story.append(Paragraph("<b>Productos Devueltos</b>", style_bold))
                items_devueltos_data = [[
                    Paragraph("<b>Cant.</b>", style_bold), Paragraph("<b>Producto</b>", style_bold),
                    Paragraph("<b>Motivo</b>", style_bold), Paragraph("<b>Subtotal</b>", style_bold_right)
                ]]
                for item in devolucion.items_devueltos.all():
                    items_devueltos_data.append([
                        Paragraph(str(item.cantidad), style_normal_center),
                        # --- CORRECCIÓN 1 AQUÍ ---
                        Paragraph(item.producto.nombre, style_normal),
                        Paragraph(item.get_motivo_display(), style_normal),
                        Paragraph(f"${item.subtotal:,.0f}", style_normal_right)
                    ])
                
                tabla_devueltos = Table(items_devueltos_data, colWidths=[0.6*inch, 4.15*inch, 1.5*inch, 1.25*inch])
                tabla_devueltos.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('ALIGN', (1,1), (2,-1), 'LEFT'),
                    ('ALIGN', (3,0), (3,-1), 'RIGHT'),
                ]))
                story.append(tabla_devueltos)
                story.append(Spacer(1, 0.2 * inch))

            # Tabla de Productos de Cambio Entregados
            if devolucion.items_cambio.exists():
                story.append(Paragraph("<b>Productos de Cambio Entregados</b>", style_bold))
                items_cambio_data = [[
                    Paragraph("<b>Cant.</b>", style_bold), Paragraph("<b>Producto</b>", style_bold),
                    Paragraph("<b>P. Unit.</b>", style_bold_right), Paragraph("<b>Subtotal</b>", style_bold_right)
                ]]
                for item in devolucion.items_cambio.all():
                    items_cambio_data.append([
                        Paragraph(str(item.cantidad), style_normal_center),
                        # --- CORRECCIÓN 2 AQUÍ ---
                        Paragraph(item.producto.nombre, style_normal),
                        Paragraph(f"${item.precio_unitario_actual:,.0f}", style_normal_right),
                        Paragraph(f"${item.subtotal:,.0f}", style_normal_right)
                    ])
                
                tabla_cambio = Table(items_cambio_data, colWidths=[0.6*inch, 4.65*inch, 1*inch, 1.25*inch])
                tabla_cambio.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
                    ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                    ('ALIGN', (1,1), (1,-1), 'LEFT'),
                    ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
                ]))
                story.append(tabla_cambio)
                story.append(Spacer(1, 0.2 * inch))

            # Totales del Balance de la Devolución
            balance_data = [
                ["", Paragraph("Total Devolución:", style_normal_right), Paragraph(f"${devolucion.total_productos_devueltos:,.0f}", style_normal_right)],
                ["", Paragraph("Total Cambio:", style_normal_right), Paragraph(f"${devolucion.total_productos_cambio:,.0f}", style_normal_right)],
                ["", Paragraph("<b>BALANCE DEVOLUCIÓN:</b>", style_bold_right), Paragraph(f"<b>${devolucion.balance_final:,.0f}</b>", style_bold_right)],
            ]
            balance_table = Table(balance_data, colWidths=[4.25*inch, 2*inch, 1.25*inch])
            story.append(balance_table)
        
        def add_header_footer(canv, doc):
            canv.saveState()
            canv.setFont('Helvetica-Bold', 12)
            canv.drawString(inch/2, letter[1] - inch, "Depósito y Ferretería del Sur")
            canv.setFont('Helvetica', 9)
            canv.drawString(inch/2, letter[1] - inch - 15, "NIT: 900.123.456-7")
            canv.setFont('Helvetica-Oblique', 8)
            canv.drawCentredString(letter[0]/2, inch/2 - 10, f"Página {doc.page} | Generado el {timezone.now().strftime('%d/%m/%Y %H:%M')}")
            canv.restoreState()
        
        doc.build(story, onFirstPage=add_header_footer, onLaterPages=add_header_footer)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()

        response = Response(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="Factura_Venta_{venta.id}.pdf"'
        
        return response
    


class MobileDashboardView(APIView):
    """
    Vista mejorada para devolver las estadísticas clave
    para el dashboard de la aplicación móvil.
    """
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    required_privilege = "dashboard_ver" # Asegúrate de que los admins tengan este privilegio

    def get(self, request):
        hoy = timezone.now().date()
        hace_30_dias = hoy - timedelta(days=30)

        # 1. Ventas de Hoy (Formateadas como texto sin decimales si no son necesarios)
        ventas_hoy = Venta.objects.filter(
            fecha=hoy,
            estado='Completada'
        ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')

        # ✨ NUEVO: Cálculo de ventas de los últimos 30 días
        ventas_30_dias = Venta.objects.filter(
            fecha__range=[hace_30_dias, hoy],
            estado='Completada'
        ).aggregate(total=Sum('total'))['total'] or Decimal('0.00')

        # 2. Pedidos por Verificar (estado 'en_verificacion')
        pedidos_por_verificar = Pedido.objects.filter(estado='en_verificacion').count()
        
        # 3. Productos con bajo stock (sin cambios, ya estaba bien)
        productos_bajo_stock = Producto.objects.filter(
            activo=True, 
            stock_actual__lte=F('stock_minimo')
        ).count()

        # 4. ✨ ENSAMBLAJE DE LA RESPUESTA CON LAS CLAVES CORRECTAS
        #    Estas claves deben coincidir con tu AdminDashboardData.fromJson en Flutter.
        data = {
            'ventas_hoy': f"{ventas_hoy:.0f}",
            'ventas_ultimos_30_dias': f"{ventas_30_dias:.0f}",
            'pedidos_por_verificar': pedidos_por_verificar,
            'productos_bajo_stock': productos_bajo_stock,
        }

        return Response(data)