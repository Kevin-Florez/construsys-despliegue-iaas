# Cotizaciones/pdf_generator.py

from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_CENTER
from django.conf import settings
from decimal import Decimal
import os 

def format_currency(value):
    # Formato numérico para Colombia
    return f"${int(value):,}".replace(",", ".")

def generate_cotizacion_pdf(cotizacion):
    buffer = BytesIO()
    # Margenes ajustados
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=0.75*inch, leftMargin=0.75*inch, topMargin=0.75*inch, bottomMargin=0.75*inch)
    
    styles = getSampleStyleSheet()
    
    
    title_style = styles['Title']
    title_style.fontSize = 22
    title_style.alignment = TA_RIGHT
    title_style.textColor = colors.HexColor('#2d3748')

    
    styles.add(ParagraphStyle(name='RightAlign', alignment=TA_RIGHT))
    styles.add(ParagraphStyle(name='CenterAlign', alignment=TA_CENTER))
    styles.add(ParagraphStyle(name='CompanyInfo', alignment=TA_RIGHT, leading=14))
    

    story = []

    
    header_data = [
       
        ['', Paragraph("<b>Depósito y Ferretería del Sur</b><br/>NIT: 900.123.456-7<br/>Contacto: (4)3735252", styles['CompanyInfo'])]
    ]
    
    header_table = Table(header_data, colWidths=[4.5*inch, 2.5*inch])
    header_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP')]))
    
    
    story.append(Paragraph("COTIZACIÓN", styles['Title']))
    story.append(Paragraph("<b>Depósito y Ferretería del Sur</b><br/>NIT: 900.123.456-7<br/>Contacto: (4)3735252", styles['CompanyInfo']))
    story.append(Spacer(1, 0.25*inch))


    # --- SECCIÓN 2: Información de Cotización y Cliente 
    
    # Lógica para el color del estado
    estado_texto = cotizacion.get_estado_display()
    estado_color = colors.lightgrey
    if cotizacion.estado == 'vigente':
        estado_color = colors.HexColor('#c6f6d5') # Verde claro
    elif cotizacion.estado == 'convertida':
        estado_color = colors.HexColor('#bee3f8') # Azul claro

    # Usamos Paragraph para interpretar la negrita
    cliente_nombre = Paragraph(f"<b>{cotizacion.cliente.nombre} {cotizacion.cliente.apellido}</b>" if cotizacion.cliente else f"<b>{cotizacion.nombre_invitado} (Invitado)</b>", styles['Normal'])
    cliente_email = cotizacion.cliente.correo if cotizacion.cliente else cotizacion.email_invitado

    info_data = [
        [Paragraph("<b>N° Cotización:</b>", styles['Normal']), cotizacion.id, Paragraph("<b>Fecha de Creación:</b>", styles['Normal']), cotizacion.fecha_creacion.strftime('%d/%m/%Y')],
        [Paragraph("<b>Cliente:</b>", styles['Normal']), cliente_nombre, Paragraph("<b>Válida hasta:</b>", styles['Normal']), cotizacion.fecha_vencimiento.strftime('%d/%m/%Y')],
        [Paragraph("<b>Email:</b>", styles['Normal']), cliente_email, Paragraph("<b>Estado:</b>", styles['Normal']), Paragraph(f"<b>{estado_texto}</b>", styles['Normal'])],
    ]

    info_table = Table(info_data, colWidths=[1.2*inch, 2.5*inch, 1.2*inch, 2.1*inch], hAlign='LEFT')
    info_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('SPAN', (1,1), (1,1)), # El nombre del cliente ocupa una celda
        ('BACKGROUND', (3,2), (3,2), estado_color), # Color para el estado
        ('GRID', (0,0), (-1,-1), 0.5, colors.grey)
    ]))
    story.append(info_table)
    story.append(Spacer(1, 0.25*inch))

    # --- SECCIÓN 3: Tabla de Detalles ---
    detalles_header = [Paragraph("<b>Cant.</b>", styles['CenterAlign']), Paragraph("<b>Descripción</b>", styles['Normal']), Paragraph("<b>Precio Unitario</b>", styles['RightAlign']), Paragraph("<b>Subtotal</b>", styles['RightAlign'])]
    detalles_data = [detalles_header]

    for detalle in cotizacion.detalles.all():
        detalles_data.append([
            detalle.cantidad,
            Paragraph(detalle.producto_nombre_historico, styles['Normal']),
            format_currency(detalle.precio_unitario_cotizado),
            format_currency(detalle.subtotal)
        ])
    
    detalles_table = Table(detalles_data, colWidths=[0.6*inch, 3.8*inch, 1.3*inch, 1.3*inch])
    detalles_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#AAACAF")),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (0,-1), 'CENTER'),
        ('ALIGN', (2,0), (-1,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 10),
        ('TOPPADDING', (0,0), (-1,-1), 10),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    story.append(detalles_table)


    # --- SECCIÓN 4: Totales ---
    tasa_iva_str = f"IVA ({int(Decimal(settings.TASA_IVA))}%)"
    
    totals_data = [
        ["Subtotal:", format_currency(cotizacion.subtotal)],
        [tasa_iva_str, format_currency(cotizacion.iva)],
        [Paragraph("<b>Total:</b>", styles['RightAlign']), Paragraph(f"<b>{format_currency(cotizacion.total)}</b>", styles['RightAlign'])],
    ]
    
    totals_table = Table(totals_data, colWidths=[1.5*inch, 1.3*inch], hAlign='RIGHT')
    totals_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'RIGHT'),
        ('LINEBELOW', (0, 1), (1, 1), 1, colors.black),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(totals_table)
    story.append(Spacer(1, 0.4*inch))
    
    # --- SECCIÓN 5: Pie de página ---
    story.append(Paragraph(f"<i>Esta cotización es válida por 15 días a partir de su fecha de creación.</i>", styles['Normal']))

    doc.build(story)
    buffer.seek(0)
    return buffer