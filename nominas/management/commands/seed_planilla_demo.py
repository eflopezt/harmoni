"""
Genera (idempotente) la planilla REGULAR del mes actual para la demo.

Deja una planilla lista para mostrar en Nóminas, incluyendo el efecto del
roster minero (días según proyección vs real: 30 limpio, 28 con faltas/DM).
Se ejecuta en el reset diario tras seed_roster_minero.

Uso:
    python manage.py seed_planilla_demo
    python manage.py seed_planilla_demo --mes 7 --anio 2026
"""
import calendar
from datetime import date

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Genera la planilla REGULAR del mes actual (demo, idempotente).'

    def add_arguments(self, parser):
        parser.add_argument('--anio', type=int, default=None)
        parser.add_argument('--mes', type=int, default=None)

    def handle(self, *args, **opts):
        from django.utils import timezone
        from nominas.models import PeriodoNomina
        from nominas.engine import generar_periodo

        hoy = timezone.localdate()
        anio = opts['anio'] or hoy.year
        mes = opts['mes'] or hoy.month
        ndias = calendar.monthrange(anio, mes)[1]

        per, _ = PeriodoNomina.objects.get_or_create(
            anio=anio, mes=mes, tipo='REGULAR',
            defaults=dict(
                descripcion=f'Planilla {mes:02d}/{anio}',
                fecha_inicio=date(anio, mes, 1),
                fecha_fin=date(anio, mes, ndias),
                observaciones='', contabilizado_formato='', estado='BORRADOR',
            ),
        )
        stats = generar_periodo(per)
        per.estado = 'CALCULADO'
        try:
            per.total_trabajadores = stats.get('generados', 0) + stats.get('actualizados', 0)
        except Exception:
            pass
        per.save()

        self.stdout.write(self.style.SUCCESS(
            f'Planilla {mes:02d}/{anio}: {stats.get("generados")} generados, '
            f'{stats.get("errores")} errores, neto total {stats.get("total_neto")}.'
        ))
