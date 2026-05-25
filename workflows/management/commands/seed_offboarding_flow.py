"""
Siembra el FlujoTrabajo "Offboarding Trabajador" — 5 etapas estándar
disparadas automáticamente cuando una `LiquidacionLaboral` pasa a
`estado='CALCULADA'`.

Idempotente: si el flujo ya existe (match por nombre), no lo recrea
ni vuelve a crear las etapas. Crea el grupo "Tesorería" si no existe.

Uso:
    python manage.py seed_offboarding_flow
    python manage.py seed_offboarding_flow --dry-run

Documentación: docs/internal/WORKFLOW_OFFBOARDING.md
"""
from __future__ import annotations

from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction


FLUJO_NOMBRE = 'Offboarding Trabajador'
GRUPO_TESORERIA = 'Tesorería'


def _etapas_config(grupo_tesoreria):
    """Devuelve la configuración de las 5 etapas en orden."""
    return [
        # 1. Encuesta de salida (la responde el trabajador cesado)
        {
            'orden':                              1,
            'nombre':                             'Encuesta de salida',
            'descripcion': (
                'El trabajador cesado responde una encuesta de salida '
                'breve sobre su experiencia en la empresa. Plazo 72h.'
            ),
            'tipo_aprobador':                     'USUARIO',
            'aprobador_usuario':                  None,  # se resuelve en runtime
            'tiempo_limite_horas':                72,
            'accion_vencimiento':                 'ESPERAR',
            'requiere_comentario':                False,
            'notificar_solicitante_al_decidir':   True,
        },
        # 2. Devolución de activos (jefe del área valida)
        {
            'orden':                              2,
            'nombre':                             'Devolución de activos',
            'descripcion': (
                'El jefe del área confirma la devolución de laptop, '
                'credencial, uniformes, EPP y demás activos asignados. '
                'Plazo 120h; si vence, se escala.'
            ),
            'tipo_aprobador':                     'JEFE_AREA',
            'tiempo_limite_horas':                120,
            'accion_vencimiento':                 'ESCALAR',
            'requiere_comentario':                True,
            'notificar_solicitante_al_decidir':   True,
        },
        # 3. Liquidación pagada (Tesorería confirma transferencia)
        {
            'orden':                              3,
            'nombre':                             'Liquidación pagada',
            'descripcion': (
                'Tesorería confirma el pago efectivo de la liquidación '
                'al trabajador. Requiere comentario con el N° de '
                'operación bancaria. Plazo 168h (7 días).'
            ),
            'tipo_aprobador':                     'GRUPO_DJANGO',
            'aprobador_grupo':                    grupo_tesoreria,
            'tiempo_limite_horas':                168,
            'accion_vencimiento':                 'ESPERAR',
            'requiere_comentario':                True,
            'notificar_solicitante_al_decidir':   True,
        },
        # 4. Carta de no adeudo (RRHH emite, auto-aprueba si vence)
        {
            'orden':                              4,
            'nombre':                             'Carta de no adeudo',
            'descripcion': (
                'RRHH emite y entrega la carta de no adeudo al '
                'trabajador. Plazo 72h; si vence se auto-aprueba.'
            ),
            'tipo_aprobador':                     'SUPERUSER',
            'tiempo_limite_horas':                72,
            'accion_vencimiento':                 'AUTO_APROBAR',
            'requiere_comentario':                False,
            'notificar_solicitante_al_decidir':   True,
        },
        # 5. Cierre administrativo (RRHH cierra el expediente)
        {
            'orden':                              5,
            'nombre':                             'Cierre administrativo',
            'descripcion': (
                'RRHH cierra el expediente del trabajador en el '
                'sistema. Plazo 48h; si vence se auto-aprueba y la '
                'liquidación pasa a estado CERRADA.'
            ),
            'tipo_aprobador':                     'SUPERUSER',
            'tiempo_limite_horas':                48,
            'accion_vencimiento':                 'AUTO_APROBAR',
            'requiere_comentario':                False,
            'notificar_solicitante_al_decidir':   True,
        },
    ]


class Command(BaseCommand):
    help = (
        'Crea el FlujoTrabajo "Offboarding Trabajador" con 5 etapas '
        '(idempotente — match por nombre).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Solo muestra qué crearía, sin tocar la BD.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options['dry_run']
        prefix  = '[DRY-RUN] ' if dry_run else ''

        # Import diferido — LiquidacionLaboral vive en nominas
        try:
            from nominas.models import LiquidacionLaboral
        except Exception as exc:
            self.stderr.write(self.style.ERROR(
                f'No se pudo importar nominas.LiquidacionLaboral: {exc}'
            ))
            return

        from workflows.models import EtapaFlujo, FlujoTrabajo

        # ── Grupo Tesorería ───────────────────────────────────────────
        if dry_run:
            grupo_existe = Group.objects.filter(name=GRUPO_TESORERIA).exists()
            self.stdout.write(
                f'{prefix}Grupo "{GRUPO_TESORERIA}": '
                f'{"YA EXISTE" if grupo_existe else "se crearía"}'
            )
            grupo_tesoreria = Group.objects.filter(name=GRUPO_TESORERIA).first()
        else:
            grupo_tesoreria, grp_created = Group.objects.get_or_create(
                name=GRUPO_TESORERIA,
            )
            marker = '[+]' if grp_created else '[=]'
            self.stdout.write(f'  {marker} Grupo: {GRUPO_TESORERIA}')

        # ── FlujoTrabajo principal ────────────────────────────────────
        ct = ContentType.objects.get_for_model(LiquidacionLaboral)

        flujo_existente = FlujoTrabajo.objects.filter(
            nombre=FLUJO_NOMBRE,
        ).first()

        if flujo_existente:
            self.stdout.write(
                f'  [=] Flujo: {FLUJO_NOMBRE} (ya existe — no se recrea)'
            )
            etapas_count = flujo_existente.etapas.count()
            self.stdout.write(
                f'      └─ {etapas_count} etapas existentes preservadas'
            )
            self.stdout.write(self.style.SUCCESS(
                f'{prefix}seed_offboarding_flow: idempotente — OK'
            ))
            return

        if dry_run:
            self.stdout.write(
                f'{prefix}Flujo "{FLUJO_NOMBRE}" + 5 etapas se crearían'
            )
            for et in _etapas_config(grupo_tesoreria):
                self.stdout.write(
                    f'    [etapa {et["orden"]}] {et["nombre"]} '
                    f'— {et["tipo_aprobador"]} '
                    f'({et["tiempo_limite_horas"]}h, '
                    f'vencimiento={et["accion_vencimiento"]})'
                )
            return

        flujo = FlujoTrabajo.objects.create(
            nombre            = FLUJO_NOMBRE,
            descripcion       = (
                'Workflow estándar de offboarding al cese de un '
                'trabajador. 5 etapas: encuesta de salida → '
                'devolución de activos → liquidación pagada → '
                'carta de no adeudo → cierre administrativo. '
                'Se dispara automáticamente cuando la '
                'LiquidacionLaboral pasa a estado CALCULADA y se '
                'cierra (estado CERRADA) al completarse.'
            ),
            icono             = 'fa-door-open',
            content_type      = ct,
            campo_trigger     = 'estado',
            valor_trigger     = 'CALCULADA',
            campo_resultado   = 'estado',
            valor_aprobado    = 'CERRADA',
            valor_rechazado   = 'CANCELADO',
            activo            = True,
            notificar_email   = True,
        )
        self.stdout.write(f'  [+] Flujo: {flujo.nombre}')

        for et_cfg in _etapas_config(grupo_tesoreria):
            EtapaFlujo.objects.create(flujo=flujo, **et_cfg)
            self.stdout.write(
                f'      [+] Etapa {et_cfg["orden"]}: {et_cfg["nombre"]}'
            )

        self.stdout.write(self.style.SUCCESS(
            f'{prefix}seed_offboarding_flow: flujo creado con 5 etapas — OK'
        ))
