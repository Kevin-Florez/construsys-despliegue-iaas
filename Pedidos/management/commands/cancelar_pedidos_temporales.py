# Pedidos/management/commands/cancelar_pedidos_temporales.py

from django.core.management.base import BaseCommand
from django.utils import timezone
from Pedidos.models import Pedido
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Cancela los pedidos temporales que han excedido su tiempo límite de pago de 60 minutos.'

    def handle(self, *args, **options):
        ahora = timezone.now()

        # Buscamos pedidos que están en estado temporal y cuya fecha límite ya pasó
        pedidos_a_cancelar = Pedido.objects.filter(
            estado='pendiente_pago_temporal',
            fecha_limite_pago__lte=ahora
        )

        if not pedidos_a_cancelar.exists():
            self.stdout.write(self.style.SUCCESS('No hay pedidos temporales para cancelar.'))
            return

        count = 0
        for pedido in pedidos_a_cancelar:
            pedido.estado = 'cancelado_por_inactividad'
            pedido.motivo_cancelacion = 'El pago no fue confirmado dentro de la hora límite.'
            pedido.save()
            count += 1
            logger.info(f'Pedido #{pedido.id} cancelado por inactividad.')

        self.stdout.write(self.style.SUCCESS(f'Se cancelaron exitosamente {count} pedidos.'))