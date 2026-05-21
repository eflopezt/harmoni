"""
Servicio de emails transaccionales del módulo de Reclutamiento.

Envía emails al candidato en los hitos clave de su proceso:
- confirmación al postular
- avance de etapa (screening → entrevista → prueba → oferta → contratado)
- descarte (con motivo)

Usa el NotificacionService existente (capa unificada). Si SMTP no está
configurado, la notificación queda en estado FALLIDA pero no rompe el flujo.

Para deshabilitar emails durante seeds/tests:
    settings.RECLUTAMIENTO_DISABLE_EMAILS = True
"""
import logging

from django.conf import settings

logger = logging.getLogger('reclutamiento.emails')


# ── Templates por evento ──────────────────────────────────────
TEMPLATES = {
    'postulado': {
        'asunto': '¡Recibimos tu postulación para {vacante}!',
        'cuerpo': """
<p>Hola <strong>{nombre}</strong>,</p>

<p>¡Gracias por postular a la vacante <strong>{vacante}</strong> en {empresa}!
Hemos recibido tu CV correctamente y nuestro equipo de reclutamiento
lo revisará en los próximos días.</p>

<p>Aquí los próximos pasos:</p>
<ol>
  <li>Nuestro equipo revisará tu CV (3-5 días hábiles)</li>
  <li>Si tu perfil encaja, te contactaremos para coordinar una entrevista</li>
  <li>Recibirás updates por este mismo email</li>
</ol>

<p>Si tienes alguna pregunta, responde directamente a este correo.</p>

<p>Mucho éxito,<br>
<strong>Equipo de Reclutamiento</strong></p>
""",
    },
    'screening': {
        'asunto': 'Avanzaste a la etapa de Screening — {vacante}',
        'cuerpo': """
<p>Hola <strong>{nombre}</strong>,</p>

<p>¡Buenas noticias! Tu postulación para <strong>{vacante}</strong> ha pasado
el filtro inicial y ahora está en revisión de screening.</p>

<p>En los próximos días un reclutador podría contactarte por teléfono o WhatsApp
para una breve conversación inicial. Por favor mantente disponible al
<strong>{telefono_propio}</strong>.</p>

<p>Saludos,<br>
<strong>Equipo de Reclutamiento</strong></p>
""",
    },
    'entrevista': {
        'asunto': 'Te invitamos a entrevista — {vacante}',
        'cuerpo': """
<p>Hola <strong>{nombre}</strong>,</p>

<p>¡Felicidades! Pasaste a la etapa de <strong>entrevista</strong> para
la vacante <strong>{vacante}</strong>.</p>

<p>En las próximas horas recibirás un email separado con la coordinación
de fecha, hora y modalidad (presencial / virtual).</p>

<p>Mientras tanto, te recomendamos:</p>
<ul>
  <li>Repasar tu experiencia más relevante para el puesto</li>
  <li>Tener listas 1-2 preguntas sobre el rol o la empresa</li>
  <li>Si es presencial, considerar el tiempo de traslado</li>
</ul>

<p>Éxitos,<br>
<strong>Equipo de Reclutamiento</strong></p>
""",
    },
    'prueba': {
        'asunto': 'Prueba técnica / práctica — {vacante}',
        'cuerpo': """
<p>Hola <strong>{nombre}</strong>,</p>

<p>Avanzaste a la etapa de <strong>prueba</strong> para la vacante
<strong>{vacante}</strong>. ¡Felicidades!</p>

<p>En breve recibirás los detalles de la prueba (descripción, plazo, formato
de entrega).</p>

<p>Saludos,<br>
<strong>Equipo de Reclutamiento</strong></p>
""",
    },
    'oferta': {
        'asunto': '¡Tenemos una oferta para ti! — {vacante}',
        'cuerpo': """
<p>Hola <strong>{nombre}</strong>,</p>

<p>¡Excelentes noticias! Después de evaluar tu perfil para
<strong>{vacante}</strong>, queremos hacerte llegar una oferta formal.</p>

<p>Nuestro equipo te contactará en las próximas 24 horas con los detalles
económicos, beneficios y fecha tentativa de inicio.</p>

<p>Estamos muy entusiasmados con la posibilidad de tenerte en el equipo.</p>

<p>Saludos,<br>
<strong>Equipo de Reclutamiento</strong></p>
""",
    },
    'contratado': {
        'asunto': '¡Bienvenido al equipo de {empresa}!',
        'cuerpo': """
<p>Hola <strong>{nombre}</strong>,</p>

<p>¡Felicidades! Hemos formalizado tu contratación para el puesto
de <strong>{vacante}</strong>.</p>

<p>En las próximas horas recibirás:</p>
<ul>
  <li>Confirmación de fecha y lugar de inicio</li>
  <li>Lista de documentos para presentar</li>
  <li>Información sobre el proceso de onboarding</li>
</ul>

<p>Bienvenido a <strong>{empresa}</strong>. Estamos muy contentos de tenerte.</p>

<p>Saludos cordiales,<br>
<strong>Equipo de Recursos Humanos</strong></p>
""",
    },
    'descartado': {
        'asunto': 'Sobre tu postulación a {vacante}',
        'cuerpo': """
<p>Hola <strong>{nombre}</strong>,</p>

<p>Te agradecemos sinceramente por haber postulado a la vacante
<strong>{vacante}</strong> y por el tiempo invertido en nuestro proceso de selección.</p>

<p>Después de evaluar varios candidatos, hemos decidido continuar con otros
perfiles que se ajustan más a los requisitos actuales del puesto.</p>

<p>Tu información quedará en nuestra base de datos para futuras oportunidades
que puedan encajar mejor con tu experiencia.</p>

<p>Te deseamos mucho éxito en tu búsqueda profesional.</p>

<p>Saludos,<br>
<strong>Equipo de Reclutamiento</strong></p>
""",
    },
}


# Map ETAPA codigo (lowercase) → template key
ETAPA_TO_TEMPLATE = {
    'recibido':    'postulado',
    'postulados':  'postulado',
    'screening':   'screening',
    'filtrados':   'screening',
    'entrevista':  'entrevista',
    'prueba':      'prueba',
    'oferta':      'oferta',
    'contratado':  'contratado',
}


def _render(template_key, context):
    """Renderiza asunto y cuerpo.

    1. Intenta cargar desde PlantillaNotificacion (DB, editable desde admin)
       usando código `reclutamiento_<template_key>` o `<template_key>` directo.
    2. Si no existe en BD o falla, cae a hardcoded TEMPLATES.

    Esto permite que el admin edite los emails sin redeploy.
    """
    safe_ctx = {
        'nombre':          context.get('nombre', 'candidato/a'),
        'vacante':         context.get('vacante', 'la vacante'),
        'empresa':         context.get('empresa', 'la empresa'),
        'telefono_propio': context.get('telefono_propio', '—'),
        'motivo':          context.get('motivo', ''),
    }

    # 1. Probar desde BD (PlantillaNotificacion)
    try:
        from comunicaciones.models import PlantillaNotificacion
        from django.template import Context, Template as DjangoTemplate
        codigos = [
            f'reclutamiento_{template_key}',
            f'reclutamiento_email_{template_key}',
            template_key,
        ]
        plantilla = (
            PlantillaNotificacion.objects
            .filter(codigo__in=codigos, activa=True)
            .first()
        )
        if plantilla:
            ctx = Context(safe_ctx)
            asunto = DjangoTemplate(plantilla.asunto_template).render(ctx)
            cuerpo = DjangoTemplate(plantilla.cuerpo_template).render(ctx)
            return asunto, cuerpo
    except Exception as e:
        logger.warning(
            f"PlantillaNotificacion lookup falló para '{template_key}': {e}. "
            f"Fallback a hardcoded."
        )

    # 2. Fallback a hardcoded TEMPLATES (format strings)
    tpl = TEMPLATES.get(template_key)
    if not tpl:
        return None, None
    try:
        asunto = tpl['asunto'].format(**safe_ctx)
        cuerpo = tpl['cuerpo'].format(**safe_ctx)
        return asunto, cuerpo
    except Exception as e:
        logger.error(f"Error renderizando email '{template_key}': {e}")
        return None, None


def sincronizar_plantillas_default():
    """Crea/actualiza las PlantillaNotificacion en BD desde TEMPLATES hardcoded.

    Convierte format strings {var} a Django template tags {{ var }} para
    que el admin pueda editarlas en la BD usando sintaxis Django familiar.

    Llamar desde una migración o management command.
    """
    try:
        from comunicaciones.models import PlantillaNotificacion
    except ImportError:
        return 0

    creadas = 0
    for key, tpl in TEMPLATES.items():
        codigo = f'reclutamiento_{key}'
        # Convertir {var} → {{ var }} para Django template
        asunto_django = tpl['asunto']
        cuerpo_django = tpl['cuerpo']
        for var in ['nombre', 'vacante', 'empresa', 'telefono_propio', 'motivo']:
            asunto_django = asunto_django.replace(
                '{' + var + '}', '{{ ' + var + ' }}'
            )
            cuerpo_django = cuerpo_django.replace(
                '{' + var + '}', '{{ ' + var + ' }}'
            )
        plantilla, created = PlantillaNotificacion.objects.update_or_create(
            codigo=codigo,
            defaults={
                'nombre':                 f'Reclutamiento — {key.replace("_", " ").title()}',
                'asunto_template':        asunto_django,
                'cuerpo_template':        cuerpo_django,
                'tipo':                   'EMAIL',
                'modulo':                 'RRHH',
                'activa':                 True,
                'variables_disponibles':  '{{ nombre }}, {{ vacante }}, {{ empresa }}, {{ telefono_propio }}, {{ motivo }}',
            },
        )
        if created:
            creadas += 1
    return creadas


def enviar_email_candidato(postulacion, template_key, extra_context=None):
    """
    Envía email al candidato. No rompe el flujo si falla.

    Args:
        postulacion: instancia de Postulacion
        template_key: 'postulado' | 'screening' | 'entrevista' | 'prueba'
                    | 'oferta' | 'contratado' | 'descartado'
        extra_context: dict opcional con variables adicionales (motivo, etc.)

    Returns:
        bool: True si se intentó enviar, False si se saltó (sin email, deshabilitado, etc.)
    """
    if getattr(settings, 'RECLUTAMIENTO_DISABLE_EMAILS', False):
        return False
    if not postulacion.email:
        logger.info(f"Postulacion {postulacion.pk} sin email — skip envío")
        return False

    empresa_nombre = '—'
    try:
        # Empresa del area/vacante si está disponible
        if hasattr(postulacion.vacante, 'area') and postulacion.vacante.area:
            area = postulacion.vacante.area
            if hasattr(area, 'empresa') and area.empresa:
                empresa_nombre = (
                    getattr(area.empresa, 'nombre_comercial', '')
                    or getattr(area.empresa, 'razon_social', '')
                    or '—'
                )
    except Exception:
        pass

    context = {
        'nombre':          postulacion.nombre_completo,
        'vacante':         postulacion.vacante.titulo,
        'empresa':         empresa_nombre,
        'telefono_propio': postulacion.telefono or '—',
    }
    if extra_context:
        context.update(extra_context)

    asunto, cuerpo = _render(template_key, context)
    if not asunto:
        return False

    try:
        from comunicaciones.services import NotificacionService
        NotificacionService.enviar(
            destinatario=None,
            destinatario_email=postulacion.email,
            asunto=asunto,
            cuerpo=cuerpo,
            tipo='EMAIL',
            contexto={
                'modulo':         'reclutamiento',
                'postulacion_id': postulacion.pk,
                'evento':         template_key,
            },
        )
        logger.info(
            f"Email '{template_key}' enviado a {postulacion.email} "
            f"(postulacion {postulacion.pk})"
        )
        return True
    except Exception as e:
        logger.error(
            f"Error enviando email '{template_key}' a {postulacion.email}: {e}"
        )
        return False


def email_por_etapa(postulacion, nueva_etapa):
    """Helper que mapea EtapaPipeline → template y envía."""
    if not nueva_etapa:
        return False
    codigo = (nueva_etapa.codigo or '').lower().strip()
    template_key = ETAPA_TO_TEMPLATE.get(codigo)
    if not template_key:
        return False
    return enviar_email_candidato(postulacion, template_key)


def email_descarte(postulacion, motivo=''):
    return enviar_email_candidato(
        postulacion, 'descartado', extra_context={'motivo': motivo}
    )
