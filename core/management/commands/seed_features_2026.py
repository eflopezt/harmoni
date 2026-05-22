"""
Seed unificado de TODAS las features 2026.

Ejecuta seeds en orden correcto para inicializar un demo con todas las
funcionalidades nuevas. Idempotente: cada sub-comando es safe to re-run.

Uso:
    python manage.py seed_features_2026
    python manage.py seed_features_2026 --skip-existing
    python manage.py seed_features_2026 --only=pipeline,gastro
"""
from django.core.management.base import BaseCommand
from django.core.management import call_command


# Orden importa: dependencias arriba primero
SEEDS_2026 = [
    # Reclutamiento
    ('seed_etapas_pipeline',         'Etapas Pipeline Reclutamiento'),
    ('seed_postulaciones_demo',      'Postulaciones demo con CV parsing'),
    # Gastronomía
    # (BPM/HACCP las certificaciones se siembran inline en script de gastro)
    # Onboarding
    ('seed_checklists_demo',         'Onboarding Gastro checklists 30/60/90'),
    # Evaluaciones
    ('seed_competencias',            'Competencias evaluaciones'),
    ('seed_evaluacion_360_demo',     'Evaluación 360 demo'),
    # Disciplinaria
    ('seed_tipos_falta',             'Tipos de falta disciplinaria'),
    ('seed_disciplinaria_demo',      'Medidas disciplinarias demo'),
    # Salarios
    ('seed_bandas_demo',             'Bandas salariales gastronomía'),
    # Encuestas Pulse (si existe)
    ('seed_pulse_demo',              'Encuestas Pulse semanales'),
    # Préstamos (si existe)
    ('seed_prestamos_demo',          'Préstamos y adelantos'),
    # Vacaciones (si existe)
    ('seed_vacaciones_demo',         'Solicitudes de vacaciones'),
    # Documentos / Legajo
    ('seed_legajo_demo',             'Legajo digital trabajadores'),
    # Templates email
    ('sync_plantillas_email',        'Plantillas email reclutamiento'),
]


class Command(BaseCommand):
    help = (
        'Ejecuta TODOS los seeds 2026 en orden correcto. '
        'Idempotente. Imprime tabla resumen al final.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--only',
            type=str,
            default='',
            help='Lista coma-separada de keywords para filtrar (ej: pipeline,gastro,360)',
        )
        parser.add_argument(
            '--skip-on-error',
            action='store_true',
            help='Continuar aunque algun seed falle (default: True)',
            default=True,
        )

    def handle(self, *args, **options):
        only_filter = options['only'].lower().split(',') if options['only'] else []
        skip_on_error = options['skip_on_error']

        results = []

        self.stdout.write(self.style.MIGRATE_HEADING(
            '\n🚀 Sembrando features 2026...\n'
        ))

        for cmd_name, desc in SEEDS_2026:
            # Aplicar filtro --only
            if only_filter and not any(k in cmd_name.lower() or k in desc.lower() for k in only_filter):
                continue

            self.stdout.write(f'  → {desc:.<55s}', ending='')
            try:
                call_command(cmd_name, verbosity=0)
                self.stdout.write(self.style.SUCCESS('  ✓ OK'))
                results.append((cmd_name, desc, 'OK', None))
            except Exception as e:
                err_msg = str(e)[:80]
                if skip_on_error:
                    self.stdout.write(self.style.WARNING(f'  ⚠ SKIP'))
                    self.stdout.write(self.style.WARNING(f'      ({err_msg})'))
                    results.append((cmd_name, desc, 'SKIP', err_msg))
                else:
                    self.stdout.write(self.style.ERROR(f'  ✗ FAIL'))
                    raise

        # Resumen final
        ok = sum(1 for _, _, status, _ in results if status == 'OK')
        skipped = sum(1 for _, _, status, _ in results if status == 'SKIP')

        self.stdout.write(self.style.MIGRATE_HEADING('\n📊 Resumen:\n'))
        self.stdout.write(f'  ✓ Exitosos: {ok}')
        if skipped:
            self.stdout.write(self.style.WARNING(f'  ⚠ Saltados:  {skipped}'))

        self.stdout.write(
            self.style.SUCCESS('\n🎉 Demo 2026 listo. Visita /sistema/dashboard/ejecutivo/\n')
        )
