"""
Management command: cruzar_tareo_roster

Puebla CruceTareoRoster (Fase 2) comparando la asistencia real (Tareo) con la
programación proyectada (Roster) en un rango de fechas, y valida topes de
jornada acumulativa.

Uso:
  python manage.py cruzar_tareo_roster --desde 2026-01-01 --hasta 2026-01-28
  python manage.py cruzar_tareo_roster --desde 2026-01-01 --hasta 2026-01-28 --dry-run
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError


def _parse(s):
    try:
        y, m, d = (int(x) for x in s.split('-'))
        return date(y, m, d)
    except Exception:
        raise CommandError(f'Fecha inválida: {s} (usa YYYY-MM-DD).')


class Command(BaseCommand):
    help = 'Cruza Tareo vs Roster (CruceTareoRoster) y reporta variaciones.'

    def add_arguments(self, parser):
        parser.add_argument('--desde', required=True, help='Fecha inicio (YYYY-MM-DD).')
        parser.add_argument('--hasta', required=True, help='Fecha fin (YYYY-MM-DD).')
        parser.add_argument('--dry-run', action='store_true', help='No guarda; solo cuenta.')

    def handle(self, *args, **opts):
        from asistencia.services.cruce_roster import poblar_cruce

        desde, hasta = _parse(opts['desde']), _parse(opts['hasta'])
        if hasta < desde:
            raise CommandError('--hasta no puede ser anterior a --desde.')

        conteo = poblar_cruce(desde, hasta, guardar=not opts['dry_run'])
        total = sum(conteo.values())
        pref = '[DRY RUN] ' if opts['dry_run'] else ''
        self.stdout.write(self.style.SUCCESS(f'{pref}Cruce {desde} → {hasta}: {total} registros.'))
        for variacion, n in sorted(conteo.items(), key=lambda kv: -kv[1]):
            self.stdout.write(f'  {variacion}: {n}')
