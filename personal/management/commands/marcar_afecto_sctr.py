"""
Management command: marcar_afecto_sctr

Marca (o desmarca) trabajadores como afectos a SCTR — el aporte de riesgo del
empleador que solo aplica a actividades de alto riesgo (Anexo 5 DS 009-97-SA).

Ejemplos:
    # Ver a quiénes afectaría, sin guardar
    python manage.py marcar_afecto_sctr --area "Operaciones" --dry-run

    # Marcar a todo el personal de un área
    python manage.py marcar_afecto_sctr --area "Producción"

    # Marcar por cargo (coincidencia parcial, case-insensitive)
    python manage.py marcar_afecto_sctr --cargo "obrero"

    # Marcar a TODOS los activos (úsalo solo si toda la empresa es de riesgo)
    python manage.py marcar_afecto_sctr --todos

    # Desmarcar (quitar afecto_sctr)
    python manage.py marcar_afecto_sctr --area "Administración" --desmarcar
"""
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from personal.models import Personal


class Command(BaseCommand):
    help = 'Marca/desmarca trabajadores como afectos a SCTR (actividad de riesgo).'

    def add_arguments(self, parser):
        parser.add_argument('--area', help='Nombre (parcial) del área/subárea.')
        parser.add_argument('--cargo', help='Cargo (parcial, case-insensitive).')
        parser.add_argument('--todos', action='store_true',
                            help='Aplica a todos los trabajadores activos.')
        parser.add_argument('--desmarcar', action='store_true',
                            help='Quita el flag en lugar de ponerlo.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Muestra a quiénes afectaría sin guardar.')

    def handle(self, *args, **opts):
        if not (opts['area'] or opts['cargo'] or opts['todos']):
            raise CommandError('Indica --area, --cargo o --todos.')

        qs = Personal.objects.filter(estado='Activo')
        if opts['area']:
            qs = qs.filter(
                Q(subarea__nombre__icontains=opts['area'])
                | Q(subarea__area__nombre__icontains=opts['area'])
            )
        if opts['cargo']:
            qs = qs.filter(
                Q(cargo__icontains=opts['cargo'])
                | Q(cargo_obj__nombre__icontains=opts['cargo'])
            )

        valor = not opts['desmarcar']
        total = qs.count()
        accion = 'desmarcar' if opts['desmarcar'] else 'marcar'

        if opts['dry_run']:
            self.stdout.write(self.style.WARNING(
                f'[DRY-RUN] Se {accion}ían {total} trabajador(es) como afecto_sctr={valor}:'))
            for p in qs[:50]:
                self.stdout.write(f'  - {p.apellidos_nombres} ({p.cargo or "?"})')
            if total > 50:
                self.stdout.write(f'  ... y {total - 50} más.')
            return

        actualizados = qs.update(afecto_sctr=valor)
        self.stdout.write(self.style.SUCCESS(
            f'{actualizados} trabajador(es) actualizados a afecto_sctr={valor}.'))
