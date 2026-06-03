"""
Rellena ConceptoRemunerativo.codigo_plame (cuando está vacío) usando el mapa
AUDITADO CONCEPTO_PLAME (Tabla 22 SUNAT) de nominas/exports_plame.py.

Conceptos cuyo código NO está en el mapa (o el mapa da None) se REPORTAN y se
dejan intactos — no inventamos códigos SUNAT. Idempotente.

Uso:
    python manage.py backfill_codigo_plame --dry-run
    python manage.py backfill_codigo_plame
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Rellena codigo_plame de conceptos desde el mapa auditado CONCEPTO_PLAME"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Solo muestra qué haría, sin guardar.')

    def handle(self, *args, **opts):
        from nominas.models import ConceptoRemunerativo
        from nominas.exports_plame import CONCEPTO_PLAME

        dry = opts['dry_run']
        sin_plame = ConceptoRemunerativo.objects.filter(
            activo=True, codigo_plame='')
        asignados, sin_mapa = [], []
        with transaction.atomic():
            for c in sin_plame:
                plame = CONCEPTO_PLAME.get(c.codigo)
                if plame:
                    asignados.append((c.codigo, plame))
                    if not dry:
                        c.codigo_plame = plame
                        c.save(update_fields=['codigo_plame'])
                else:
                    sin_mapa.append(c.codigo)

        pre = '[DRY-RUN] ' if dry else ''
        self.stdout.write(self.style.SUCCESS(
            f'{pre}{len(asignados)} concepto(s) con código PLAME asignado:'))
        for cod, plame in asignados:
            self.stdout.write(f'  {cod} → {plame}')
        if sin_mapa:
            self.stdout.write(self.style.WARNING(
                f'{len(sin_mapa)} sin mapeo en CONCEPTO_PLAME (revisar manualmente): '
                + ', '.join(sin_mapa)))
