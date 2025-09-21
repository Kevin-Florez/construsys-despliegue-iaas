# backend/backend_api/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from django.core.mail import send_mail
from django.conf import settings

class ContactoView(APIView):
    """
    Recibe los datos de un formulario de contacto y los envía por correo.
    """
    permission_classes = [AllowAny] # Permite que cualquiera use este formulario

    def post(self, request, *args, **kwargs):
        nombre = request.data.get('nombre')
        email_origen = request.data.get('email')
        asunto_cliente = request.data.get('asunto')
        mensaje = request.data.get('mensaje')

        # Validación simple de que los campos no estén vacíos
        if not all([nombre, email_origen, asunto_cliente, mensaje]):
            return Response(
                {"detail": "Todos los campos son requeridos."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Preparamos el correo que recibirá la empresa
        asunto_empresa = f"Nuevo Mensaje de Contacto: {asunto_cliente}"
        cuerpo_mensaje = (
            f"Has recibido un nuevo mensaje desde el formulario de contacto de tu sitio web.\n\n"
            f"--------------------------------------------------\n"
            f"De: {nombre}\n"
            f"Correo: {email_origen}\n"
            f"Asunto: {asunto_cliente}\n"
            f"--------------------------------------------------\n\n"
            f"Mensaje:\n{mensaje}\n"
        )
        
        try:
            send_mail(
                asunto_empresa,
                cuerpo_mensaje,
                settings.EMAIL_HOST_USER,  # El correo configurado en settings.py
                [settings.EMAIL_HOST_USER], # El correo de la empresa se envía a sí mismo
                fail_silently=False,
            )
            return Response({"detail": "Mensaje enviado con éxito."}, status=status.HTTP_200_OK)
        except Exception as e:
            print(f"Error al enviar correo de contacto: {e}") # Para depuración
            return Response(
                {"detail": "Hubo un error al enviar el mensaje. Por favor, inténtalo más tarde."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        

