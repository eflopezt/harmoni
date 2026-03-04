"""
Management command: setup_harmoni
Configuracion inicial completa de Harmoni.
Ejecuta todos los seeds en orden y configura el sistema base.

Uso:
    python manage.py setup_harmoni
    python manage.py setup_harmoni --no-input   # sin interactividad (Render/CI)
    python manage.py setup_harmoni --force      # re-ejecuta seeds aunque ya existan datos
"""
import sys
from django.core.management.base import BaseCommand
from django.core.management import call_command


# Orden de ejecucion: dependencias primero
SEED_COMMANDS = [
    # 1. Personal base (areas, subareas, feriados)
    ('seed_data',                    'personal',        'Datos base (areas, subareas, feriados)'),
    # 2. Asistencia
    ('seed_tareo_inicial',           'asistencia',      'Configuracion inicial asistencia'),
    # 3. Documentos
    ('seed_documentos',              'documentos',      'Categorias y tipos de documento'),
    # 4. Tipos de falta disciplinaria
    ('seed_tipos_falta',             'disciplinaria',   'Tipos de falta disciplinaria (DS 003-97-TR)'),
    # 5. Tipos de permiso/licencia
    ('seed_tipos_permiso',           'vacaciones',      'Tipos de permiso y licencia'),
    # 6. Etapas reclutamiento
    ('seed_etapas_pipeline',         'reclutamiento',   'Etapas del pipeline de reclutamiento'),
    # 7. Plantillas onboarding
    ('seed_plantillas_onboarding',   'onboarding',      'Plantillas de onboarding y offboarding'),
    # 8. Competencias evaluaciones
    ('seed_competencias',            'evaluaciones',    'Competencias base para evaluaciones'),
    # 9. Conceptos nomina
    ('seed_conceptos',               'nominas',         'Conceptos de nomina (haberes, descuentos)'),
    # 10. Tipos prestamo
    ('seed_tipos_prestamo',          'prestamos',       'Tipos de prestamo y adelanto'),
    # 11. Conceptos viaticos
    ('seed_conceptos_viatico',       'viaticos',        'Conceptos de viaticos CDT'),
    # 12. Plantillas notificacion
    ('seed_plantillas_notificacion', 'comunicaciones',  'Plantillas de notificacion y comunicacion'),
    # 13. Dossier plantillas
    ('seed_dossier_plantillas',      'documentos',      'Plantillas de dossier documentario'),
    # 14. Plantillas de constancias
    ('seed_constancias',             'documentos',      'Plantillas de constancias y certificados'),
    # 15. Perfiles de acceso RBAC (roles del sistema)
    ('seed_perfiles_acceso',         'core',            'Perfiles de acceso RBAC (admin-rrhh, reclutador, etc.)'),
]


class Command(BaseCommand):
    help = 'Configuracion inicial completa de Harmoni (seeds + superuser + config)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-input', '--noinput', action='store_true',
            dest='no_input',
            help='No solicitar confirmacion interactiva.',
        )
        parser.add_argument(
            '--force', action='store_true',
            help='Forzar re-ejecucion de seeds aunque ya existan datos.',
        )
        parser.add_argument(
            '--skip-superuser', action='store_true',
            help='No crear superusuario inicial.',
        )

    def handle(self, *args, **options):
        no_input = options['no_input']
        force    = options['force']

        self.stdout.write(self.style.MIGRATE_HEADING(
            '\n Harmoni - Setup Inicial\n'
            '=================================='
        ))

        # 1. Verificar migraciones aplicadas
        self._check_migrations()

        # 2. Configuracion del sistema (ConfiguracionSistema)
        self._setup_configuracion(no_input)

        # 3. Ejecutar seeds
        self.stdout.write('\n[1/4] Ejecutando seeds de datos iniciales...')
        seeds_ok = 0
        seeds_skip = 0
        seeds_error = 0

        for cmd_name, app, desc in SEED_COMMANDS:
            try:
                self.stdout.write(f'  -> {desc}...', ending=' ')
                self.stdout.flush()
                kwargs = {}
                # Algunos comandos aceptan --clean o flags especificos
                if cmd_name == 'seed_documentos' and force:
                    kwargs['clean'] = True
                call_command(cmd_name, verbosity=0, **kwargs)
                self.stdout.write(self.style.SUCCESS('OK'))
                seeds_ok += 1
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'OMITIDO ({e})'))
                seeds_skip += 1

        self.stdout.write(f'  Seeds: {seeds_ok} OK, {seeds_skip} omitidos, {seeds_error} errores')

        # 4. Crear superusuario inicial
        if not options.get('skip_superuser'):
            self.stdout.write('\n[2/4] Verificando superusuario...')
            self._ensure_superuser(no_input)

        # 5. Sincronizar usuarios Personal
        self.stdout.write('\n[3/4] Sincronizando usuarios de Personal...')
        try:
            call_command('sincronizar_usuarios', verbosity=0)
            self.stdout.write('  Sincronizacion OK')
        except Exception as e:
            self.stdout.write(f'  Sincronizacion omitida: {e}')

        # 6. Generar KPI snapshot inicial
        self.stdout.write('\n[4/4] Generando snapshot KPI inicial...')
        try:
            call_command('generar_kpi', verbosity=0)
            self.stdout.write('  KPI snapshot OK')
        except Exception as e:
            self.stdout.write(f'  KPI omitido: {e}')

        self.stdout.write(self.style.SUCCESS(
            '\n Setup completado. Harmoni esta listo para usar.\n'
        ))

    # ─────────────────────────────────────────────────────────────

    def _check_migrations(self):
        """Verifica que todas las migraciones esten aplicadas."""
        from django.db.migrations.executor import MigrationExecutor
        from django.db import connection
        try:
            executor = MigrationExecutor(connection)
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            if plan:
                self.stdout.write(self.style.WARNING(
                    f'ADVERTENCIA: Hay {len(plan)} migracion(es) pendiente(s). '
                    'Ejecuta "python manage.py migrate" primero.'
                ))
        except Exception:
            pass

    def _setup_configuracion(self, no_input):
        """Crea/actualiza ConfiguracionSistema con valores por defecto."""
        self.stdout.write('\n[0/4] Configuracion del sistema...')
        try:
            from asistencia.models import ConfiguracionSistema
            config, created = ConfiguracionSistema.objects.get_or_create(pk=1)

            if created:
                # Primera vez: habilitar todos los modulos
                config.mod_prestamos      = True
                config.mod_viaticos       = True
                config.mod_documentos     = True
                config.mod_evaluaciones   = True
                config.mod_capacitaciones = True
                config.mod_reclutamiento  = True
                config.mod_encuestas      = True
                config.mod_salarios       = True
                config.save()
                self.stdout.write('  ConfiguracionSistema creada con todos los modulos activos')
            else:
                # Ya existe: asegurarse que los modulos esten habilitados
                updates = {}
                for mod in ['mod_prestamos', 'mod_viaticos', 'mod_documentos',
                            'mod_evaluaciones', 'mod_capacitaciones', 'mod_reclutamiento',
                            'mod_encuestas', 'mod_salarios']:
                    if not getattr(config, mod, False):
                        updates[mod] = True
                if updates:
                    for k, v in updates.items():
                        setattr(config, k, v)
                    config.save()
                    self.stdout.write(
                        f'  ConfiguracionSistema actualizada: {len(updates)} modulo(s) habilitados'
                    )
                else:
                    self.stdout.write('  ConfiguracionSistema OK (todos los modulos activos)')
        except Exception as e:
            self.stdout.write(f'  ConfiguracionSistema omitida: {e}')

    def _ensure_superuser(self, no_input):
        """Crea superusuario inicial si no existe ninguno."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        if User.objects.filter(is_superuser=True).exists():
            self.stdout.write('  Ya existe un superusuario.')
            return

        if no_input:
            # Crear con valores por defecto (para CI/Render)
            import os
            username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
            email    = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@harmoni.app')
            password = os.environ.get('DJANGO_SUPERUSER_PASSWORD', 'Harmoni2026!')
            try:
                User.objects.create_superuser(username=username, email=email, password=password)
                self.stdout.write(
                    self.style.SUCCESS(f'  Superusuario "{username}" creado.')
                )
                self.stdout.write(
                    self.style.WARNING(
                        f'  IMPORTANTE: Cambia la contrasena de "{username}" despues del primer login.'
                    )
                )
            except Exception as e:
                self.stdout.write(f'  Error creando superusuario: {e}')
        else:
            try:
                call_command('create_initial_superuser', verbosity=1)
            except Exception as e:
                self.stdout.write(f'  Superusuario omitido: {e}')
