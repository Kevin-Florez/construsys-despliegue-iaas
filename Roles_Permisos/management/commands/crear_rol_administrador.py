from django.core.management.base import BaseCommand
from Roles_Permisos.models import Rol, Permiso

class Command(BaseCommand):
    """
    Este comando de gestión asegura la existencia y correcta configuración
    del rol de 'Administrador'. Es seguro ejecutarlo múltiples veces.
    - Si el rol no existe, lo crea con estado protegido y activo.
    - Si ya existe, verifica que esté activo y protegido.
    - En ambos casos, sincroniza sus permisos para que tenga acceso a todo lo
      disponible en la tabla de Permisos.
    """
    help = 'Crea o actualiza el rol de Administrador, asignándole todos los permisos disponibles en el sistema.'

    def handle(self, *args, **options):
        try:
            # Usamos get_or_create. Si el rol 'Administrador' no existe, lo crea
            # usando los valores en 'defaults'. Si ya existe, simplemente lo obtiene.
            admin_rol, creado = Rol.objects.get_or_create(
                nombre='Administrador',
                defaults={
                    'descripcion': 'Rol con acceso total a todos los módulos del sistema.',
                    'es_protegido': True,
                    'activo': True
                }
            )

            if creado:
                self.stdout.write(self.style.SUCCESS('Rol "Administrador" creado exitosamente.'))
            else:
                # Si el rol ya existía, nos aseguramos de que sus propiedades importantes no hayan sido alteradas.
                admin_rol.es_protegido = True
                admin_rol.activo = True
                admin_rol.save()
                self.stdout.write(self.style.WARNING('Rol "Administrador" ya existe. Verificando y actualizando permisos...'))

            # Antes de asignar, verificamos que haya permisos para asignar.
            todos_los_permisos = Permiso.objects.all()
            if not todos_los_permisos.exists():
                self.stdout.write(self.style.ERROR(
                    'No se encontraron permisos en la base de datos. '
                    'Por favor, ejecute "python manage.py populate_permissions" primero.'
                ))
                return # Detenemos la ejecución si no hay permisos.

            # Asignamos el conjunto completo de permisos.
            # El método .set() limpia los permisos actuales y añade los nuevos.
            # Es perfecto para sincronizar.
            admin_rol.permisos.set(todos_los_permisos)

            self.stdout.write(self.style.SUCCESS(
                f'¡Éxito! {todos_los_permisos.count()} permisos han sido asignados al rol "Administrador".'
            ))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Ocurrió un error inesperado al procesar el rol de Administrador: {e}'))