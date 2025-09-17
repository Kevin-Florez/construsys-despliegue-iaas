# backend_api/Configuracion/models.py

from django.db import models
from decimal import Decimal

class ConfiguracionSistema(models.Model):
    """
    Un modelo para guardar configuraciones globales. Se usará como un 'singleton',
    es decir, solo existirá una única fila en esta tabla.
    """
    tasa_interes_mensual_credito = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('2.0'), # Ejemplo: 2.0 que representa 2%
        verbose_name="Tasa de Interés Mensual para Créditos (%)",
        help_text="Valor en porcentaje. Por ejemplo, para 2.5% ingrese 2.5"
    )

    def __str__(self):
        return f"Configuración General del Sistema (Tasa de Interés: {self.tasa_interes_mensual_credito}%)"

    def save(self, *args, **kwargs):
        # Asegura que solo exista una instancia de configuración
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def obtener_configuracion(cls):
        # Método para obtener fácilmente la configuración única
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    class Meta:
        verbose_name_plural = "Configuración del Sistema"