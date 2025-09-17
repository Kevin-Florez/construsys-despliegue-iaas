# Productos/management/commands/importar_imagenes_adicionales.py

from django.core.management.base import BaseCommand
from django.db import transaction
from Productos.models import Producto, ImagenProducto
import csv

class Command(BaseCommand):
    help = 'Importa imágenes adicionales para productos desde un archivo CSV.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='La ruta completa al archivo CSV de imágenes adicionales.')

    @transaction.atomic
    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        self.stdout.write(self.style.SUCCESS(f'Iniciando la importación de imágenes desde: {csv_file_path}'))

        try:
            with open(csv_file_path, mode='r', encoding='utf-8') as file:
                reader = csv.DictReader(file)

                for row in reader:
                    producto_nombre = row.get('producto_nombre')
                    imagen_url = row.get('imagen_url')

                    if not producto_nombre or not imagen_url:
                        self.stdout.write(self.style.WARNING(f"~ Fila omitida. Faltan datos: {row}"))
                        continue

                    try:
                        # 1. Encontrar el producto al que pertenece la imagen
                        producto = Producto.objects.get(nombre__iexact=producto_nombre.strip())

                        # 2. Crear o verificar la imagen adicional para evitar duplicados
                        imagen, creado = ImagenProducto.objects.get_or_create(
                            producto=producto,
                            imagen_url=imagen_url.strip()
                        )

                        if creado:
                            self.stdout.write(self.style.SUCCESS(f"✔ Imagen añadida a '{producto.nombre}'."))
                        else:
                            self.stdout.write(self.style.WARNING(f"~ Imagen para '{producto.nombre}' ya existía."))

                    except Producto.DoesNotExist:
                        self.stdout.write(self.style.ERROR(f"❌ Producto '{producto_nombre}' no encontrado. No se pudo añadir la imagen."))
                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"❌ Error procesando la imagen para '{producto_nombre}': {e}"))
        
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"El archivo en la ruta '{csv_file_path}' no fue encontrado."))

        self.stdout.write(self.style.SUCCESS('¡Proceso de importación de imágenes finalizado!'))