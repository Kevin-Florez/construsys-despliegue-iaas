# backend_api/Compras/views.py

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.utils import timezone
import logging
from rest_framework.exceptions import ValidationError
# Imports para PDF
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle, Spacer, SimpleDocTemplate
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

from .models import Compra
from .serializers import CompraReadSerializer, CompraCreateSerializer

from Roles_Permisos.permissions import HasPrivilege
from .renderers import BinaryPDFRenderer 
from rest_framework.renderers import JSONRenderer

logger = logging.getLogger(__name__)

class CompraListCreateView(generics.ListCreateAPIView):
    queryset = Compra.objects.select_related('proveedor').prefetch_related('items', 'items__producto').all().order_by('-fecha_compra', '-id')
   
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CompraCreateSerializer
        return CompraReadSerializer

    
    def get_required_privilege(self, method):
        if method == 'GET':
            return 'compras_ver'
        if method == 'POST':
            return 'compras_crear'
        return None

class CompraRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Compra.objects.select_related('proveedor').prefetch_related('items', 'items__producto').all()
    serializer_class = CompraReadSerializer 
   
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]

    
    def get_required_privilege(self, method):
        if method == 'GET':
            return 'compras_ver'
        if method in ['PUT', 'PATCH']:
            return 'compras_editar'
        
        return 'compras_editar'

    def perform_destroy(self, instance):
       
        if instance.estado == 'confirmada':
            raise ValidationError("No se pueden eliminar compras confirmadas que ya afectaron el inventario. Anule la compra primero.")

        # Solo permite eliminar si no está confirmada (ej. en estado 'pendiente')
        instance.delete()


class GenerarCompraPDFView(APIView):
   
    permission_classes = [permissions.IsAuthenticated, HasPrivilege]
    
    required_privilege = "compras_ver"
    renderer_classes = [BinaryPDFRenderer, JSONRenderer]

    current_compra_for_pdf = None 

    def _encabezado_pie_pagina(self, canv, doc):
        canv.saveState()
        page_width, page_height = doc.pagesize
        left_margin, right_margin = doc.leftMargin, doc.rightMargin
        header_y_start = page_height - 0.5 * inch
        canv.setFont('Helvetica-Bold', 12)
        canv.drawString(left_margin, header_y_start, "Depósito y Ferretería del Sur")
        canv.setFont('Helvetica', 9)
        if self.current_compra_for_pdf:
            canv.drawRightString(page_width - right_margin, header_y_start, f"Comprobante Compra #{self.current_compra_for_pdf.id}")
        header_y_line2 = header_y_start - 0.2 * inch
        canv.drawString(left_margin, header_y_line2, "NIT: 900.123.456-7")
        if self.current_compra_for_pdf:
            fecha_compra_str = self.current_compra_for_pdf.fecha.strftime('%d/%m/%Y')
            canv.drawRightString(page_width - right_margin, header_y_line2, f"Fecha Compra: {fecha_compra_str}")
        line_y_pos = header_y_line2 - 0.15 * inch
        canv.setStrokeColor(colors.grey)
        canv.line(left_margin, line_y_pos, page_width - right_margin, line_y_pos)
        canv.setFont('Helvetica-Oblique', 8)
        footer_text = f"Página {doc.page} | Documento generado el {timezone.now().strftime('%d/%m/%Y %H:%M')}"
        canv.drawCentredString((left_margin + doc.width) / 2.0, 0.5 * inch, footer_text)
        canv.restoreState()

    def get(self, request, compra_id, *args, **kwargs):
        compra = get_object_or_404(
            Compra.objects.select_related('proveedor').prefetch_related('items', 'items__producto'),
            pk=compra_id
        )
        self.current_compra_for_pdf = compra

        buffer = io.BytesIO()
        styles = getSampleStyleSheet()
        style_normal = ParagraphStyle('Normal_custom_compra', parent=styles['Normal'], fontSize=10, leading=12)
        style_normal_right = ParagraphStyle(name='NormalRight_compra', parent=style_normal, alignment=TA_RIGHT)
        style_bold = ParagraphStyle(name='BoldText_compra', parent=style_normal, fontName='Helvetica-Bold')
        style_heading_main_text = "ORDEN DE COMPRA"
        if compra.estado == 'confirmada': style_heading_main_text = "COMPROBANTE DE COMPRA RECIBIDA"
        elif compra.estado == 'anulada': style_heading_main_text = "COMPRA ANULADA"
        style_heading_main = ParagraphStyle(name='HeadingMain_compra', parent=styles['h1'], alignment=TA_CENTER, fontSize=16, spaceAfter=0.2*inch, textColor=colors.HexColor("#333333"))
        style_section_title = ParagraphStyle(name='SectionTitle_compra', parent=styles['h2'], alignment=TA_LEFT, fontSize=12, spaceBefore=0.15*inch, spaceAfter=0.05*inch, textColor=colors.HexColor("#2c5282"), fontName='Helvetica-Bold')
        
        story = []
        
        # Lógica para construir el PDF
        
        doc_margin = 0.75 * inch
        doc_top_margin, doc_bottom_margin = 1.2 * inch, 1.0 * inch
        doc = SimpleDocTemplate(buffer, pagesize=letter, leftMargin=doc_margin, rightMargin=doc_margin, topMargin=doc_top_margin, bottomMargin=doc_bottom_margin)
        doc.build(story, onFirstPage=self._encabezado_pie_pagina, onLaterPages=self._encabezado_pie_pagina)

        pdf_bytes = buffer.getvalue()
        buffer.close()
        response = Response(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Compra_{compra.id}_{compra.fecha.strftime("%Y%m%d")}.pdf"'
        return response