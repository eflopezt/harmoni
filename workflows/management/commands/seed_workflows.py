"""
Siembra las configuraciones base de FlujoTrabajo para los módulos principales.

Ejecutar una sola vez (idempotente — usa get_or_create):
    manage.py seed_workflows
    manage.py seed_workflows --dry-run   # muestra qué crearía

Flujos configurados:
  1. Aprobación de Vacaciones (SolicitudVacacion)
  2. Aprobación de Permiso (SolicitudPermiso)
  3. Autorización de Horas Extra (SolicitudHE)

NOTA: Cada FlujoTrabajo necesita al menos una EtapaFlujo para funcionar.
      Este comando crea 1 etapa por flujo (supervisor inmediato vía JEFE_AREA).
      Puedes agregar etapas adicionales desde el admin Django: /admin/workflows/
"""

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Siembra configuraciones base de workflows para módulos de Harmoni.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Solo muestra los flujos que crearía.')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        prefix  = '[DRY-RUN] ' if dry_run else ''

        configs = self._build_configs()
        creados = rechazados = 0

        for cfg in configs:
            modelo_label = cfg.pop('_modelo_label')
            etapas_cfg   = cfg.pop('_etapas', [])

            try:
                ct = self._get_ct(cfg.pop('_app_label'), cfg.pop('_model_name'))
            except Exception as exc:
                self.stderr.write(f'  SKIP {modelo_label}: {exc}')
                rechazados += 1
                continue

            cfg['content_type'] = ct

            if dry_run:
                self.stdout.write(f'  [flujo] {cfg["nombre"]} ({modelo_label})')
                for et in etapas_cfg:
                    self.stdout.write(f'    [etapa] {et["nombre"]} — {et["tipo_aprobador"]}')
                creados += 1
                continue

            from workflows.models import EtapaFlujo, FlujoTrabajo
            flujo, fl_created = FlujoTrabajo.objects.get_or_create(
                nombre=cfg['nombre'],
                defaults=cfg,
            )
            marker = '[+]' if fl_created else '[=]'
            self.stdout.write(f'  {marker} Flujo: {flujo.nombre}')

            if fl_created:
                # Crear etapas solo para flujos nuevos
                for i, et_cfg in enumerate(etapas_cfg, start=1):
                    et_cfg['flujo'] = flujo
                    et_cfg['orden'] = i
                    EtapaFlujo.objects.get_or_create(
                        flujo=flujo,
                        orden=i,
                        defaults=et_cfg,
                    )
                    self.stdout.write(f'    [+] Etapa {i}: {et_cfg["nombre"]}')

            creados += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'{prefix}seed_workflows: {creados} flujos procesados, {rechazados} omitidos.'
            )
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Configuraciones de flujos
    # ─────────────────────────────────────────────────────────────────────────

    def _build_configs(self) -> list:
        return [
            # ── 1. Aprobación de Vacaciones ──────────────────────────────
            {
                '_modelo_label':  'SolicitudVacacion',
                '_app_label':     'vacaciones',
                '_model_name':    'solicitudvacacion',
                'nombre':         'Aprobación de Vacaciones',
                'descripcion':    (
                    'Flujo estándar de aprobación de solicitudes de vacaciones. '
                    'Etapa 1: jefe de área. '
                    'Plazo de 72 horas; si vence se auto-aprueba.'
                ),
                'campo_trigger':    'estado',
                'valor_trigger':    'PENDIENTE',
                'campo_resultado':  'estado',
                'valor_aprobado':   'APROBADA',
                'valor_rechazado':  'RECHAZADA',
                'activo':           True,
                'notificar_email':  True,
                '_etapas': [
                    {
                        'nombre':                    'Aprobación Jefe de Área',
                        'tipo_aprobador':                  'JEFE_AREA',
                        'tiempo_limite_horas':             72,
                        'accion_vencimiento':              'AUTO_APROBAR',
                        'requiere_comentario':             False,
                        'notificar_solicitante_al_decidir': True,
                    },
                ],
            },

            # ── 2. Aprobación de Permiso ─────────────────────────────────
            {
                '_modelo_label':  'SolicitudPermiso',
                '_app_label':     'vacaciones',
                '_model_name':    'solicitudpermiso',
                'nombre':         'Aprobación de Permisos y Licencias',
                'descripcion':    (
                    'Flujo de aprobación de permisos/licencias (12 tipos Perú). '
                    'Etapa 1: jefe de área (48h). '
                    'Etapa 2: RRHH (24h, solo para permisos especiales).'
                ),
                'campo_trigger':    'estado',
                'valor_trigger':    'PENDIENTE',
                'campo_resultado':  'estado',
                'valor_aprobado':   'APROBADA',
                'valor_rechazado':  'RECHAZADA',
                'activo':           True,
                'notificar_email':  True,
                '_etapas': [
                    {
                        'nombre':                    'Aprobación Jefe de Área',
                        'tipo_aprobador':                  'JEFE_AREA',
                        'tiempo_limite_horas':             48,
                        'accion_vencimiento':              'ESPERAR',
                        'requiere_comentario':             False,
                        'notificar_solicitante_al_decidir': True,
                    },
                ],
            },

            # ── 3. Autorización de Horas Extra ───────────────────────────
            {
                '_modelo_label':  'SolicitudHE',
                '_app_label':     'tareo',
                '_model_name':    'solicitudhe',
                'nombre':         'Autorización de Horas Extra',
                'descripcion':    (
                    'Flujo de autorización de solicitudes de horas extra (DL 713). '
                    'Etapa 1: jefe de área (24h, requiere comentario). '
                    'Si se rechaza, la HE no se computa en planilla.'
                ),
                'campo_trigger':    'estado',
                'valor_trigger':    'PENDIENTE',
                'campo_resultado':  'estado',
                'valor_aprobado':   'APROBADA',
                'valor_rechazado':  'RECHAZADA',
                'activo':           True,
                'notificar_email':  False,
                '_etapas': [
                    {
                        'nombre':                    'Autorización Jefe de Área',
                        'tipo_aprobador':                  'JEFE_AREA',
                        'tiempo_limite_horas':             24,
                        'accion_vencimiento':              'ESPERAR',
                        'requiere_comentario':             True,
                        'notificar_solicitante_al_decidir': True,
                    },
                ],
            },
        ]

    def _get_ct(self, app_label: str, model_name: str):
        try:
            return ContentType.objects.get(app_label=app_label, model=model_name)
        except ContentType.DoesNotExist:
            raise Exception(f'ContentType no encontrado: {app_label}.{model_name}')
