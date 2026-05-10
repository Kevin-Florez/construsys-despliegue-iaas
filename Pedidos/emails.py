# Pedidos/emails.py

from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings

def enviar_correo_confirmacion_pedido(pedido):
    asunto = f"Confirmación de tu pedido #{pedido.id} en Depósito y Ferretería del Sur"
    
    destinatario = pedido.cliente.correo if pedido.cliente else pedido.email_invitado
    
    contexto = {
        'pedido': pedido,
        'frontend_url': settings.FRONTEND_URL 
    }
    html_mensaje = render_to_string('emails/pedido_confirmacion.html', contexto)
    texto_plano = strip_tags(html_mensaje)

    send_mail(
        asunto,
        texto_plano,
        'noreply@ferreteriadelsur.com',
        [destinatario],
        html_message=html_mensaje
    )

def enviar_correo_actualizacion_estado(pedido):
    estado_amigable = pedido.get_estado_display()
    asunto = f"Actualización de tu pedido #{pedido.id}: ¡Ahora está {estado_amigable}!"
    
    destinatario = pedido.cliente.correo if pedido.cliente else pedido.email_invitado
    
    contexto = {
        'pedido': pedido,
        'estado_amigable': estado_amigable,
        'frontend_url': settings.FRONTEND_URL
    }
    html_mensaje = render_to_string('emails/pedido_actualizacion.html', contexto)
    texto_plano = strip_tags(html_mensaje)

    send_mail(
        asunto,
        texto_plano,
        'noreply@ferreteriadelsur.com',
        [destinatario],
        html_message=html_mensaje
    )
