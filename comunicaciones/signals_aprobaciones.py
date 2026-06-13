"""
Dispara el mensaje de Telegram con botones cuando nace una solicitud
PENDIENTE (vacaciones, préstamo/adelanto). Best-effort: si Telegram no
está configurado o falla, el flujo normal de aprobación no se afecta.

Registrado en ComunicacionesConfig.ready().
"""
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _enviar(tipo, instance):
    try:
        from .telegram_aprobaciones import enviar_solicitud_aprobacion
        enviar_solicitud_aprobacion(tipo, instance)
    except Exception:
        logger.warning('Telegram aprobaciones: envío falló (%s %s)',
                       tipo, instance.pk, exc_info=True)


@receiver(post_save, sender='vacaciones.SolicitudVacacion',
          dispatch_uid='tg_aprob_vacacion')
def solicitud_vacacion_creada(sender, instance, created, **kwargs):
    if created and instance.estado == 'PENDIENTE':
        _enviar('vac', instance)


@receiver(post_save, sender='prestamos.Prestamo',
          dispatch_uid='tg_aprob_prestamo')
def prestamo_creado(sender, instance, created, **kwargs):
    if created and instance.estado == 'PENDIENTE':
        _enviar('pre', instance)
