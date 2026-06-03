"""
Rellena Personal.fecha_alta cuando está vacía, con una fecha PLAUSIBLE.
Pensado para limpiar data de DEMO/seed (un trabajador sin fecha de alta no puede
calcular antigüedad ni vacaciones). En PRODUCCIÓN la fecha de alta es un dato real
del trabajador → NO usar este comando en prod (úsalo solo en demo/seed).

Regla: si tiene fecha_cese → fecha_alta = cese − 2 años; si no → fecha base
variada por pk (entre 2022 y ~2024). Idempotente (solo toca los que están vacíos).

Uso (demo):
    python manage.py backfill_fecha_alta
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Rellena Personal.fecha_alta vacía con fecha plausible (solo DEMO/seed)"

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        from personal.models import Personal
        dry = opts['dry_run']
        base = date(2022, 3, 1)
        n = 0
        for p in Personal.objects.filter(fecha_alta__isnull=True):
            nueva = (p.fecha_cese - timedelta(days=730)) if p.fecha_cese \
                else base + timedelta(days=(p.pk * 37) % 900)
            n += 1
            if not dry:
                p.fecha_alta = nueva
                p.save(update_fields=['fecha_alta'])
        pre = '[DRY-RUN] ' if dry else ''
        self.stdout.write(self.style.SUCCESS(
            f'{pre}fecha_alta asignada a {n} trabajador(es) sin ella.'))
