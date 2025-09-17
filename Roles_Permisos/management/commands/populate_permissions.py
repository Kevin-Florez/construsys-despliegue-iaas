# Roles_Permisos/management/commands/populate_permissions.py

from django.core.management.base import BaseCommand
from Roles_Permisos.models import Permiso
from django.db import transaction

class Command(BaseCommand):
    help = 'Crea y sincroniza los permisos granulares (privilegios) para cada módulo del sistema.'

    # ✨ --- MAPA CENTRAL DE PRIVILEGIOS --- ✨
    PERMISSIONS_MAP = {
        'Dashboard': ['ver'],
        'Ventas': ['ver', 'crear', 'editar', 'anular', 'devolucion'],
        'Compras': ['ver', 'crear', 'editar', 'anular'],
        'Productos': ['ver', 'crear', 'editar', 'eliminar'],
        'Categorias': ['ver', 'crear', 'editar', 'eliminar'],
        'Clientes': ['ver', 'crear', 'editar', 'eliminar'],
        'Pedidos': ['ver', 'gestionar_estado'],
        'Usuarios': ['ver', 'crear', 'editar', 'eliminar'], 
        'Roles': ['ver', 'crear', 'editar', 'eliminar'],
        'Marcas': ['ver', 'crear', 'editar', 'eliminar'],
        'Cotizaciones': ['ver', 'crear', 'editar', 'eliminar'],
        'Proveedores': ['ver', 'crear', 'editar', 'eliminar'],
        'Creditos': ['ver', 'editar', 'anular', 'abonar', 'verificar_abonos'],
        'Solicitudes': ['ver', 'crear', 'gestionar'],
        
        # --- INICIO DE CAMBIOS ---
        # Se renombra 'Inventario' a 'Stock' y se ajustan privilegios
        'Stock': ['ver_bajas', 'registrar_baja'],
        
        # Se añaden privilegios para el nuevo módulo unificado de Devoluciones
        'Devoluciones': [
            'ver_devolucion_proveedor', 
            'crear_devolucion_proveedor', 
            'editar_devolucion_proveedor'
        ]
        # --- FIN DE CAMBIOS ---
    }

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("--- Iniciando sincronización de privilegios ---"))
        
        codenames_actuales = set()
        for modulo, privilegios in self.PERMISSIONS_MAP.items():
            for privilegio in privilegios:
                codename = f"{modulo.lower().replace(' ', '_')}_{privilegio.lower().replace(' ', '_')}"
                codenames_actuales.add(codename)

        permisos_obsoletos = Permiso.objects.exclude(codename__in=codenames_actuales)
        if permisos_obsoletos.exists():
            count = permisos_obsoletos.count()
            self.stdout.write(self.style.WARNING(f'-> Se eliminarán {count} permisos obsoletos...'))
            for p_obsoleto in permisos_obsoletos:
                self.stdout.write(f'   - {p_obsoleto.codename}')
            permisos_obsoletos.delete()
            self.stdout.write(self.style.WARNING('-> Permisos obsoletos eliminados.'))

        nuevos_creados = 0
        for modulo, privilegios in self.PERMISSIONS_MAP.items():
            for privilegio in privilegios:
                codename = f"{modulo.lower().replace(' ', '_')}_{privilegio.lower().replace(' ', '_')}"
                nombre_legible = f"{privilegio.capitalize()} {modulo}"

                permiso, creado = Permiso.objects.update_or_create(
                    codename=codename,
                    defaults={
                        'nombre': nombre_legible,
                        'modulo': modulo
                    }
                )
                if creado:
                    nuevos_creados += 1
        
        if nuevos_creados > 0:
            self.stdout.write(f'-> Se crearon {nuevos_creados} nuevos permisos.')
        
        total_permisos = Permiso.objects.count()
        self.stdout.write(self.style.SUCCESS(f"--- Sincronización completada. Total de permisos en el sistema: {total_permisos} ---"))