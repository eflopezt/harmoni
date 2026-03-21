"""
Management command: actualizar fecha_fin_contrato desde empleados_activos.json.

Si ultima_prorroga > fecha_fin_contrato actual, actualiza.
"""
import json
from datetime import date, datetime
from pathlib import Path

from django.core.management.base import BaseCommand

from personal.models import Personal


class Command(BaseCommand):
    help = 'Actualiza fecha_fin_contrato desde deploy/empleados_activos.json (ultima_prorroga)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Solo muestra cambios sin aplicar',
        )
        parser.add_argument(
            '--json-path', type=str,
            default='deploy/empleados_activos.json',
            help='Ruta al JSON de empleados',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        json_path = Path(options['json_path'])

        if not json_path.exists():
            self.stderr.write(f'Archivo no encontrado: {json_path}')
            return

        with open(json_path, 'r', encoding='utf-8') as f:
            empleados = json.load(f)

        updated = 0
        skipped = 0
        not_found = 0

        for emp in empleados:
            dni = emp.get('dni', '').strip()
            ultima_prorroga_str = emp.get('ultima_prorroga', '')

            if not dni or not ultima_prorroga_str:
                skipped += 1
                continue

            try:
                ultima_prorroga = datetime.strptime(ultima_prorroga_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                skipped += 1
                continue

            try:
                personal = Personal.objects.get(nro_doc=dni, estado='Activo')
            except Personal.DoesNotExist:
                not_found += 1
                continue
            except Personal.MultipleObjectsReturned:
                personal = Personal.objects.filter(nro_doc=dni, estado='Activo').first()

            current_fin = personal.fecha_fin_contrato
            needs_update = False

            if current_fin is None:
                needs_update = True
            elif ultima_prorroga > current_fin:
                needs_update = True

            if needs_update:
                if dry_run:
                    self.stdout.write(
                        f'  [DRY] {dni} {personal.apellidos_nombres}: '
                        f'{current_fin} -> {ultima_prorroga}'
                    )
                else:
                    personal.fecha_fin_contrato = ultima_prorroga
                    personal.save(update_fields=['fecha_fin_contrato'])
                    self.stdout.write(
                        f'  [UPD] {dni} {personal.apellidos_nombres}: '
                        f'{current_fin} -> {ultima_prorroga}'
                    )
                updated += 1

        action = 'Would update' if dry_run else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f'\n{action}: {updated} | Skipped: {skipped} | Not found: {not_found}'
        ))
