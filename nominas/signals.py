"""
Signals de la app `nominas` — disparadores automáticos.

post_save en Personal:
  Cuando un trabajador pasa a `estado='Cesado'` con `fecha_cese` poblada,
  genera automáticamente su `LiquidacionLaboral` y la calcula.

  Idempotente: si la liquidación ya existe, no la regenera.
  Diseño documentado en docs/internal/DISEÑO_LIQUIDACIONES_PROPINAS_ISC.md
  sección 1.2 "Diseño propuesto".

post_save en LiquidacionLaboral:
  Cuando la liquidación pasa a `estado='CALCULADA'` y aún no tiene
  `instancia_flujo`, dispara el workflow "Offboarding Trabajador"
  (5 etapas: encuesta de salida → devolución activos → liquidación
  pagada → carta no adeudo → cierre admin). Idempotente.

  Documentación: docs/internal/WORKFLOW_OFFBOARDING.md
"""
from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from personal.models import Personal


logger = logging.getLogger('nominas.signals')

OFFBOARDING_FLUJO_NOMBRE = 'Offboarding Trabajador'


_MAP_MOTIVO_PERSONAL_A_LIQ = {
    'RENUNCIA':         'RENUNCIA',
    'MUTUO_ACUERDO':    'MUTUO',
    'JUBILACION':       'JUBILACION',
    'VENCIMIENTO':      'CADUCIDAD',
    'TERMINO_CONTRATO': 'CADUCIDAD',
    'NO_RENOVACION':    'CADUCIDAD',
    'DESPIDO_CAUSA':    'DESPIDO',
    'CESE_COLECTIVO':   'CADUCIDAD',
    'LIQUIDACION':      'CADUCIDAD',
    'FALLECIMIENTO':    'FALLECIMIENTO',
    'INVALIDEZ':        'JUBILACION',
    'ABANDONO':         'DESPIDO',
    'OTRO':             'RENUNCIA',
}


@receiver(post_save, sender=Personal)
def crear_liquidacion_al_cesar(sender, instance, created, **kwargs):
    """
    Cuando `Personal.estado` queda en 'Cesado' con `fecha_cese`, generar
    la `LiquidacionLaboral` automáticamente.

    El cálculo se ejecuta solo en la creación de la liquidación
    (idempotente). Si la liquidación ya existe, se respetan ediciones
    manuales que pueda haber hecho RRHH.
    """
    # Filtro rápido: solo cesados con fecha
    if instance.estado != 'Cesado' or not instance.fecha_cese:
        return

    # Import diferido para evitar circularidad en app loading
    from .models import LiquidacionLaboral

    motivo_liq = _MAP_MOTIVO_PERSONAL_A_LIQ.get(
        (instance.motivo_cese or '').upper(),
        'RENUNCIA',
    )

    try:
        liquidacion, created_liq = LiquidacionLaboral.objects.get_or_create(
            personal=instance,
            defaults={
                'fecha_cese':  instance.fecha_cese,
                'motivo_cese': motivo_liq,
            },
        )
    except Exception as exc:
        logger.error(
            '[Liquidacion] Error get_or_create para DNI %s: %s',
            instance.nro_doc, exc,
        )
        return

    if created_liq:
        try:
            liquidacion.calcular()
            logger.info(
                '[Liquidacion] Generada para %s — motivo=%s neto=S/%s',
                instance.nro_doc, motivo_liq, liquidacion.total_neto,
            )
        except Exception as exc:
            logger.error(
                '[Liquidacion] Falló cálculo para DNI %s: %s',
                instance.nro_doc, exc,
            )


# ────────────────────────────────────────────────────────────────────────────
# Signal: post_save LiquidacionLaboral → disparar Workflow "Offboarding"
# ────────────────────────────────────────────────────────────────────────────

def _resolver_usuario_admin_default():
    """Devuelve un User válido para usar como `solicitante` del workflow.

    Estrategia:
      1) Cualquier superuser activo (orden por pk para estabilidad).
      2) Cualquier user is_staff activo.
      3) None — el engine acepta solicitante=None.
    """
    User = get_user_model()
    user = User.objects.filter(is_superuser=True, is_active=True).order_by('pk').first()
    if user:
        return user
    return User.objects.filter(is_staff=True, is_active=True).order_by('pk').first()


@receiver(post_save, sender='nominas.LiquidacionLaboral')
def disparar_workflow_offboarding(sender, instance, created, **kwargs):
    """
    Cuando `LiquidacionLaboral.estado == 'CALCULADA'` y aún no hay
    `instancia_flujo`, dispara el workflow "Offboarding Trabajador".

    Es idempotente:
      - Si la LL ya tiene `instancia_flujo`, no hace nada.
      - Si el flujo "Offboarding Trabajador" no existe en BD (ej. seed
        aún no corrió), solo emite un warning — NO levanta excepción
        para evitar romper el cálculo de la liquidación.

    Notas:
      - Usa el primer superuser activo como `solicitante`. Si el cliente
        prefiere otro, puede sobre-escribir esta lógica vía settings.
      - Vincula la `InstanciaFlujo` creada de regreso en
        `LiquidacionLaboral.instancia_flujo` con `update_fields` para
        evitar disparar el signal en bucle.
    """
    # Filtros rápidos para evitar trabajo innecesario
    if instance.estado != 'CALCULADA':
        return
    if instance.instancia_flujo_id:
        # Ya hay instancia — no duplicar
        return

    logger.info(
        '[Offboarding] LL #%s en CALCULADA — intentando disparar workflow',
        instance.pk,
    )

    try:
        from workflows.engine import crear_instancia
    except Exception as exc:
        logger.warning(
            '[Offboarding] No se pudo importar workflows.engine: %s', exc,
        )
        return

    solicitante = _resolver_usuario_admin_default()

    try:
        nueva_instancia = crear_instancia(
            flujo_codigo=OFFBOARDING_FLUJO_NOMBRE,
            solicitante=solicitante,
            objeto=instance,
            titulo=f'Offboarding de {instance.personal}',
            descripcion=(
                f'Liquidación #{instance.pk} — motivo '
                f'{instance.get_motivo_cese_display()}'
            ),
            metadata={
                'liquidacion_id':  instance.pk,
                'personal_doc':    getattr(instance.personal, 'nro_doc', ''),
                'fecha_cese':      str(instance.fecha_cese),
            },
        )
    except Exception as exc:
        # Falla silenciosa: el cálculo de la liquidación ya quedó OK,
        # el workflow se puede arrancar manualmente más tarde.
        logger.warning(
            '[Offboarding] crear_instancia falló para LL #%s: %s',
            instance.pk, exc,
        )
        return

    if nueva_instancia is None:
        logger.warning(
            '[Offboarding] Flujo "%s" no existe (¿corrió seed_offboarding_flow?). '
            'LL #%s quedará sin workflow asociado.',
            OFFBOARDING_FLUJO_NOMBRE, instance.pk,
        )
        return

    # Vincular la instancia de regreso a la liquidación
    try:
        instance.instancia_flujo = nueva_instancia
        instance.save(update_fields=['instancia_flujo'])
        logger.info(
            '[Offboarding] LL #%s vinculada a InstanciaFlujo #%s',
            instance.pk, nueva_instancia.pk,
        )
    except Exception as exc:
        logger.error(
            '[Offboarding] No se pudo vincular InstanciaFlujo #%s a LL #%s: %s',
            nueva_instancia.pk, instance.pk, exc,
        )
