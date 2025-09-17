# Ventas/renderers.py
from rest_framework.renderers import BaseRenderer

class BinaryPDFRenderer(BaseRenderer):
    media_type = 'application/pdf'
    format = 'pdf'
    charset = None  # El PDF es binario
    render_style = 'binary'

    def render(self, data, media_type=None, renderer_context=None):
        # 'data' debe ser los bytes del PDF que la vista preparó.
        # El renderer simplemente los devuelve.
        return data