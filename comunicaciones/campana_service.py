"""
Servicio de envío de CampanaComunicacion.

Resuelve destinatarios via segmentacion.resolver_destinatarios y crea
Notificaciones por cada canal seleccionado, actualizando estadísticas
y estado del modelo. Usa NotificacionService y WhatsAppService como
dependencias (no duplica lógica).
"""
import logging

from django.utils import timezone

from comunicaciones.segmentacion import resolver_destinatarios

logger = logging.getLogger('comunicaciones.campana')


# Mapeo: canal de campaña -> lista de tipos de Notificacion a crear
CANAL_TO_TIPOS = {
    'EMAIL':    ['EMAIL'],
    'WHATSAPP': ['WHATSAPP'],
    'IN_APP':   ['IN_APP'],
    'MULTI':    ['IN_APP', 'EMAIL', 'WHATSAPP'],
}


def _resolver_email(personal):
    return (personal.correo_corporativo or personal.correo_personal or '').strip()


def _resolver_telefono(personal):
    return (getattr(personal, 'celular', '') or '').strip()


def enviar_campana(campana, request_user=None):
    """
    Envía la campaña a todos los destinatarios resueltos por sus filtros.

    Flujo:
        1. Resuelve destinatarios (QuerySet de Personal).
        2. Por cada destinatario y por cada tipo de canal (según campana.canal):
           crea una Notificacion (bulk_create para IN_APP, individuales para
           EMAIL/WHATSAPP que requieren llamadas externas).
        3. Actualiza destinatarios_count, enviados_ok, enviados_fallidos.
        4. Marca estado=ENVIADA y enviada_en=now.

    Returns:
        dict {'total': N, 'ok': N, 'fallidos': N, 'notificaciones_ids': [...]}.
    """
    from comunicaciones.models import CampanaComunicacion, Notificacion
    from comunicaciones.services import NotificacionService

    if campana.estado in ('ENVIADA', 'CANCELADA'):
        logger.warning(f"Campaña {campana.pk} en estado {campana.estado}, no se reenvía")
        return {'total': 0, 'ok': 0, 'fallidos': 0, 'notificaciones_ids': []}

    # Marcar como enviando
    campana.estado = 'ENVIANDO'
    campana.save(update_fields=['estado'])

    destinatarios = list(resolver_destinatarios(campana))
    total = len(destinatarios)
    campana.destinatarios_count = total

    tipos = CANAL_TO_TIPOS.get(campana.canal, ['IN_APP'])
    ahora = timezone.now()

    ok = 0
    fallidos = 0
    notif_ids = []

    # IN_APP: bulk_create eficiente
    if 'IN_APP' in tipos:
        bulk = []
        for p in destinatarios:
            bulk.append(Notificacion(
                destinatario=p,
                destinatario_email=_resolver_email(p),
                destinatario_telefono=_resolver_telefono(p),
                asunto=campana.asunto,
                cuerpo=campana.cuerpo,
                tipo='IN_APP',
                estado='ENVIADA',
                enviada_en=ahora,
                metadata={
                    'campana_id': campana.pk,
                    'campana_nombre': campana.nombre,
                    'tipo_notificacion': 'INFO',
                    'icono': 'fa-bullhorn',
                    'color': '#0f766e',
                },
            ))
        if bulk:
            creadas = Notificacion.objects.bulk_create(bulk)
            ok += len(creadas)
            # bulk_create en algunos backends no devuelve PKs; volvemos a consultar
            notif_ids.extend([n.pk for n in creadas if n.pk])

    # EMAIL: requiere envío real → delegar a NotificacionService.enviar()
    if 'EMAIL' in tipos:
        for p in destinatarios:
            email = _resolver_email(p)
            if not email:
                # No email → crear notif fallida explícita
                n = Notificacion.objects.create(
                    destinatario=p,
                    asunto=campana.asunto,
                    cuerpo=campana.cuerpo,
                    tipo='EMAIL',
                    estado='FALLIDA',
                    error_detalle='Destinatario sin email',
                    metadata={'campana_id': campana.pk},
                )
                fallidos += 1
                notif_ids.append(n.pk)
                continue
            try:
                n = NotificacionService.enviar(
                    destinatario=p,
                    asunto=campana.asunto,
                    cuerpo=campana.cuerpo,
                    tipo='EMAIL',
                    contexto={'campana_id': campana.pk,
                              'campana_nombre': campana.nombre},
                )
                if n and n.estado == 'ENVIADA':
                    ok += 1
                else:
                    fallidos += 1
                if n:
                    notif_ids.append(n.pk)
            except Exception as exc:
                logger.error(f"Email campaña {campana.pk} → {p}: {exc}")
                fallidos += 1

    # WHATSAPP: envía via NotificacionService que usa WhatsAppService
    if 'WHATSAPP' in tipos:
        for p in destinatarios:
            telefono = _resolver_telefono(p)
            if not telefono:
                n = Notificacion.objects.create(
                    destinatario=p,
                    asunto=campana.asunto,
                    cuerpo=campana.cuerpo,
                    tipo='WHATSAPP',
                    estado='FALLIDA',
                    error_detalle='Destinatario sin celular',
                    metadata={'campana_id': campana.pk},
                )
                fallidos += 1
                notif_ids.append(n.pk)
                continue
            try:
                n = NotificacionService.enviar(
                    destinatario=p,
                    asunto=campana.asunto,
                    cuerpo=campana.cuerpo,
                    tipo='WHATSAPP',
                    contexto={'campana_id': campana.pk,
                              'campana_nombre': campana.nombre},
                )
                if n and n.estado == 'ENVIADA':
                    ok += 1
                else:
                    fallidos += 1
                if n:
                    notif_ids.append(n.pk)
            except Exception as exc:
                logger.error(f"WhatsApp campaña {campana.pk} → {p}: {exc}")
                fallidos += 1

    # Actualizar campaña
    campana.enviados_ok = ok
    campana.enviados_fallidos = fallidos
    campana.estado = 'ENVIADA'
    campana.enviada_en = ahora
    campana.save(update_fields=['destinatarios_count', 'enviados_ok',
                                 'enviados_fallidos', 'estado', 'enviada_en'])

    logger.info(
        f"Campaña '{campana.nombre}' enviada: total={total} "
        f"ok={ok} fallidos={fallidos} canal={campana.canal}"
    )

    return {
        'total': total,
        'ok': ok,
        'fallidos': fallidos,
        'notificaciones_ids': notif_ids,
    }


def reenviar_fallidos(campana, request_user=None):
    """
    Reintenta enviar las notificaciones de la campaña que quedaron FALLIDAS
    (solo EMAIL y WHATSAPP — IN_APP no tiene reintentos).
    """
    from comunicaciones.models import Notificacion
    from comunicaciones.services import NotificacionService

    fallidas = Notificacion.objects.filter(
        metadata__campana_id=campana.pk,
        estado='FALLIDA',
        tipo__in=['EMAIL', 'WHATSAPP'],
    )

    reintentadas = 0
    nuevos_ok = 0
    nuevos_fallidos = 0

    for notif in fallidas:
        # Crear NUEVA notificación (no mutamos la histórica)
        try:
            nueva = NotificacionService.enviar(
                destinatario=notif.destinatario,
                asunto=notif.asunto,
                cuerpo=notif.cuerpo,
                tipo=notif.tipo,
                contexto={'campana_id': campana.pk, 'reintento_de': notif.pk},
            )
            reintentadas += 1
            if nueva and nueva.estado == 'ENVIADA':
                nuevos_ok += 1
            else:
                nuevos_fallidos += 1
        except Exception as exc:
            logger.error(f"Reintento {notif.pk}: {exc}")
            nuevos_fallidos += 1

    # Refrescar stats
    campana.enviados_ok += nuevos_ok
    campana.enviados_fallidos = max(0, campana.enviados_fallidos - nuevos_ok)
    campana.save(update_fields=['enviados_ok', 'enviados_fallidos'])

    return {
        'reintentadas': reintentadas,
        'ok': nuevos_ok,
        'fallidos': nuevos_fallidos,
    }
