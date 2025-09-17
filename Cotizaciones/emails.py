# Cotizaciones/emails.py

from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string

def enviar_correo_cotizacion_invitado(cotizacion):
    """
    Envía un correo electrónico a un usuario invitado con el enlace para acceder a su cotización.
    """
    if not cotizacion.email_invitado:
        print(f"ERROR: Se intentó enviar correo para la cotización #{cotizacion.id} pero no tiene email de invitado.")
        return

    # Construimos el enlace de acceso. 
    
    frontend_url = 'http://localhost:5173' 
    enlace_acceso = f"{frontend_url}/cotizacion/ver/{cotizacion.token_acceso}"

    subject = f'Tu Cotización #{cotizacion.id} de ConstruSys está lista'
    
    
    message_body = f"""
Hola {cotizacion.nombre_invitado},

¡Gracias por cotizar con nosotros!

Hemos guardado tu cotización #{cotizacion.id} con los precios actuales. Esta cotización es válida por 15 días, hasta el {cotizacion.fecha_vencimiento.strftime('%d de %B de %Y')}.

Puedes ver y convertir tu cotización en un pedido en cualquier momento a través del siguiente enlace:
{enlace_acceso}

Si tienes alguna pregunta, no dudes en contactarnos.

Saludos cordiales,
El equipo de ConstruSys
"""

    try:
        send_mail(
            subject,
            message_body,
            settings.DEFAULT_FROM_EMAIL,
            [cotizacion.email_invitado],
            fail_silently=False,
        )
        print(f"Correo de cotización enviado exitosamente a {cotizacion.email_invitado}")
    except Exception as e:
        # Es importante registrar el error si el correo no se puede enviar
        print(f"ERROR: No se pudo enviar el correo de cotización a {cotizacion.email_invitado}. Causa: {str(e)}")