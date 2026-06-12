"""
Tareas Celery de comunicaciones.

Digest diario del Centro de Acción (patrón Workday: UN email a hora fija
con TODOS los pendientes, en vez de un email por evento).
"""
import logging

from celery import shared_task

logger = logging.getLogger(__name__)

# Etiquetas humanas para los bloques del tool consolidado de aprobaciones
_ETIQUETAS = {
    'papeletas': 'Papeletas de permiso',
    'solicitudes_he': 'Solicitudes de horas extra',
    'justificaciones_no_marcaje': 'Justificaciones de no marcaje',
    'roster': 'Roster',
    'prestamos_y_adelantos': 'Préstamos y adelantos',
    'descuentos_planilla': 'Descuentos de planilla',
    'vacaciones': 'Vacaciones',
    'reintegros_agente': 'Reintegros propuestos por el agente IA',
}


def _base_url():
    """URL base para los deep-links del email."""
    import os
    return (os.environ.get('SITE_URL') or 'https://harmoni.pe').rstrip('/')


@shared_task
def enviar_digest_diario_admins():
    """
    Envía a cada superuser activo (con email) UN resumen de todo lo que
    espera aprobación, con link directo a cada pantalla. Si no hay nada
    pendiente, no envía (anti-spam).
    """
    from django.contrib.auth.models import User

    from comunicaciones.services import NotificacionService
    from nominas.agente_ia.tools import tool_listar_aprobaciones_pendientes

    resultado_tool = tool_listar_aprobaciones_pendientes()
    bloques = [
        (nombre, data)
        for nombre, data in (resultado_tool.get('bloques') or {}).items()
        if isinstance(data, dict) and data.get('total')
    ]
    total = sum(d['total'] for _, d in bloques)
    if not total:
        logger.info('Digest diario: sin pendientes, no se envía.')
        return {'enviados': 0, 'total_pendientes': 0}

    base = _base_url()
    filas = []
    for nombre, data in sorted(bloques, key=lambda b: -b[1]['total']):
        etiqueta = _ETIQUETAS.get(nombre, nombre.replace('_', ' ').title())
        link = base + data.get('donde_aprobar', '/')
        filas.append(
            f'<tr>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;">{etiqueta}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;text-align:center;'
            f'font-weight:700;">{data["total"]}</td>'
            f'<td style="padding:8px 12px;border-bottom:1px solid #e2e8f0;">'
            f'<a href="{link}" style="color:#0f766e;">Revisar →</a></td>'
            f'</tr>'
        )

    asunto = f'Harmoni — {total} pendiente(s) de aprobación hoy'
    cuerpo = (
        '<p>Buenos días,</p>'
        f'<p>Tienes <strong>{total}</strong> ítem(s) esperando tu aprobación:</p>'
        '<table style="border-collapse:collapse;min-width:380px;">'
        '<tr style="background:#f0fdfa;">'
        '<th style="padding:8px 12px;text-align:left;">Módulo</th>'
        '<th style="padding:8px 12px;">Pendientes</th>'
        '<th style="padding:8px 12px;"></th></tr>'
        + ''.join(filas) +
        '</table>'
        f'<p style="margin-top:14px;"><a href="{base}/" style="color:#0f766e;">'
        'Abrir el Centro de Acción</a></p>'
        '<p style="color:#94a3b8;font-size:12px;">Recibes este resumen una vez al día '
        'solo cuando hay pendientes.</p>'
    )

    enviados = 0
    admins = User.objects.filter(
        is_active=True, is_superuser=True
    ).exclude(email='')
    for admin in admins:
        try:
            NotificacionService.enviar(
                destinatario=None,
                asunto=asunto,
                cuerpo=cuerpo,
                tipo='EMAIL',
                destinatario_email=admin.email,
                contexto={'tipo_evento': 'digest_diario_admin', 'total': total},
            )
            enviados += 1
        except Exception:
            logger.warning('Digest diario: fallo enviando a %s', admin.email, exc_info=True)

    logger.info('Digest diario: %s pendientes, %s email(s).', total, enviados)
    return {'enviados': enviados, 'total_pendientes': total}
