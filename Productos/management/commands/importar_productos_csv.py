# backend/Productos/management/commands/importar_productos_csv.py

from django.core.management.base import BaseCommand
from django.db import transaction
from Productos.models import Producto, CategoriaProducto, Marca
import csv

class Command(BaseCommand):
    help = 'Importa productos desde un archivo CSV especificado.'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='La ruta completa al archivo CSV a importar.')

    @transaction.atomic
    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        self.stdout.write(self.style.SUCCESS(f'Iniciando la importación de productos desde: {csv_file_path}'))

        try:
            with open(csv_file_path, mode='r', encoding='utf-8') as file:
                reader = csv.DictReader(file)

                for row in reader:
                    try:
                        # --- Marca ---
                        marca_nombre = row.get('marca_nombre', 'Generico').strip()
                        marca, _ = Marca.objects.get_or_create(
                            nombre__iexact=marca_nombre,
                            defaults={'nombre': marca_nombre}
                        )

                        # --- Categoría ---
                        categoria_nombre = row.get('categoria_nombre', 'Sin Categoría').strip()
                        categoria, _ = CategoriaProducto.objects.get_or_create(
                            nombre__iexact=categoria_nombre,
                            defaults={'nombre': categoria_nombre, 'descripcion': 'Categoría creada automáticamente.'}
                        )

                        # --- Crear/Actualizar Producto ---
                        producto, creado = Producto.objects.update_or_create(
                            nombre=row['nombre'],
                            defaults={
                                'marca': marca,
                                'categoria': categoria,
                                'descripcion': row.get('descripcion', ''),
                                'imagen_url': row.get('imagen_url', ''),
                                'peso': row.get('peso', ''),
                                'dimensiones': row.get('dimensiones', ''),
                                'material': row.get('material', ''),
                                'otros_detalles': row.get('otros_detalles', ''),
                                'ultimo_costo_compra': float(row.get('ultimo_costo_compra', 0.00) or 0.00),
                                'stock_actual': int(row.get('stock_actual', 0) or 0),
                                'stock_minimo': int(row.get('stock_minimo', 0) or 0),
                                'stock_maximo': int(row.get('stock_maximo', 0) or 0),
                                'stock_defectuoso': int(row.get('stock_defectuoso', 0) or 0),
                                'activo': row.get('activo', 'True').lower() in ['true', '1', 'yes', 'si'],
                                'precio_venta': float(row.get('precio_venta', 0.00) or 0.00),
                                'ultimo_margen_aplicado': float(row.get('ultimo_margen_aplicado', 0.00) or 0.00),
                            }
                        )

                        if creado:
                            self.stdout.write(self.style.SUCCESS(f"✔ Producto '{producto.nombre}' CREADO exitosamente."))
                        else:
                            self.stdout.write(self.style.WARNING(f"~ Producto '{producto.nombre}' ACTUALIZADO."))

                    except Exception as e:
                        self.stdout.write(self.style.ERROR(f"❌ Error en la fila para '{row.get('nombre', 'Nombre no encontrado')}': {e}"))

        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f"El archivo en la ruta '{csv_file_path}' no fue encontrado."))

        self.stdout.write(self.style.SUCCESS('¡Proceso de importación finalizado!'))
