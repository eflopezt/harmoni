"""
Signals de la app `nominas` — disparadores automáticos.

post_save en Personal:
  Cuando un trabajador pasa a `estado='Cesado'` con `fecha_cese` poblada,
  genera automáticamente su `LiquidacionLaboral` y la calcula.

  Idempotente: si la liquidación ya existe, no la regenera.
  Diseño documentado en docs/internal/DISEÑO_LIQUIDACIONES_PROPINAS_ISC.md
  sección 1.2 "Diseño propuesto".
"""
from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from personal.models import Personal


logger = logging.getLogger('nominas.signals')


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
