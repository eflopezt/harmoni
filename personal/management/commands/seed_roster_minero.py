"""
Siembra un roster 14x7 REAL para los trabajadores de MINERIA (demo).

Objetivo demo: evidenciar el flujo Roster (proyección) -> Nómina (días
automáticos). Un trabajador (Raúl Quispe) lleva excepciones reales
(descanso médico + faltas) para mostrar que lo REAL puede diferir de lo
PROYECTADO, y que la planilla ajusta los días sola.

Uso:
    python manage.py seed_roster_minero            # mes actual
    python manage.py seed_roster_minero --mes 7 --anio 2026
"""
import calendar
from datetime import date

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Siembra roster 14x7 para trabajadores de MINERIA (demo, idempotente).'

    def add_arguments(self, parser):
        parser.add_argument('--anio', type=int, default=None)
        parser.add_argument('--mes', type=int, default=None)

    def handle(self, *args, **opts):
        from django.utils import timezone
        from personal.models import Personal, Roster

        hoy = timezone.localdate()
        anio = opts['anio'] or hoy.year
        mes = opts['mes'] or hoy.month
        ndias = calendar.monthrange(anio, mes)[1]

        mineros = list(
            Personal.objects.filter(regimen_laboral='MINERIA', estado='Activo')
            .order_by('apellidos_nombres')
        )
        if not mineros:
            self.stdout.write(self.style.WARNING('No hay trabajadores de MINERIA activos.'))
            return

        creados = actualizados = 0
        con_excep = None
        for p in mineros:
            # Un trabajador con excepciones reales (proyectado != real).
            excep = {}
            if 'QUISPE MAMANI' in (p.apellidos_nombres or '').upper():
                excep = {12: 'DM', 13: 'DM', 25: 'F', 26: 'F'}  # 2 dias DM + 2 faltas
                con_excep = p.apellidos_nombres
            for d in range(1, ndias + 1):
                # Ciclo acumulativo 14x7: 14 dias de trabajo (T), 7 de descanso (D).
                pos = (d - 1) % 21
                codigo = 'T' if pos < 14 else 'D'
                codigo = excep.get(d, codigo)
                obs = ''
                if codigo == 'DM':
                    obs = 'Descanso médico'
                elif codigo == 'F':
                    obs = 'Falta injustificada'
                _, created = Roster.objects.update_or_create(
                    personal=p, fecha=date(anio, mes, d),
                    defaults={'codigo': codigo, 'estado': 'aprobado',
                              'observaciones': obs, 'fuente': 'seed_roster_minero'},
                )
                if created:
                    creados += 1
                else:
                    actualizados += 1

        self.stdout.write(self.style.SUCCESS(
            f'Roster minero {mes:02d}/{anio}: {len(mineros)} trabajadores, '
            f'{creados} días creados, {actualizados} actualizados. '
            f'Con excepciones: {con_excep or "ninguno"}.'
        ))
