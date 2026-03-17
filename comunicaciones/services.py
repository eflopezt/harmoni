"""
Servicio de notificaciones — capa de servicio reutilizable.

Uso desde cualquier módulo:
    from comunicaciones.services import NotificacionService

    # Envío directo
    NotificacionService.enviar(personal, "Asunto", "<p>Cuerpo</p>", tipo='IN_APP')

    # Envío desde plantilla
    NotificacionService.enviar_desde_plantilla(
        personal, 'vacaciones_aprobadas',
        {'nombre': personal.apellidos_nombres, 'fecha_inicio': '01/02/2026'}
    )

    # Envío masivo desde un ComunicadoMasivo
    NotificacionService.enviar_masivo(comunicado)
"""
import logging

from django.core.mail import EmailMessage
from django.template import Template, Context
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger('comunicaciones')

# Mapping from PlantillaNotificacion.codigo to HTML email template paths.
# When an EMAIL notification matches one of these codes, the branded
# HTML template is used instead of sending the raw cuerpo string.
EMAIL_TEMPLATE_MAP = {
    'bienvenida':             'emails/bienvenida.html',
    'bienvenida_onboarding':  'emails/bienvenida.html',
    'vacaciones_aprobadas':   'emails/vacaciones_aprobadas.html',
    'boleta_disponible':      'emails/boleta_disponible.html',
    'boleta_pago':            'emails/boleta_disponible.html',
    'recordatorio':           'emails/recordatorio.html',
    'recordatorio_general':   'emails/recordatorio.html',
    'comunicado':             'emails/comunicado.html',
    'comunicado_masivo':      'emails/comunicado.html',
}


class NotificacionService:
    """Motor central de notificaciones de Harmoni."""

    # ── Envío directo ────────────────────────────────────────

    @staticmethod
    def enviar(destinatario, asunto, cuerpo, tipo='IN_APP',
               plantilla_codigo=None, contexto=None, destinatario_email=''):
        """
        Crea una Notificacion y, si es EMAIL, intenta enviarla.
        Si tipo es AMBOS, crea dos notificaciones (una IN_APP y una EMAIL).

        Args:
            destinatario: instancia de Personal (puede ser None)
            asunto: str
            cuerpo: str (HTML)
            tipo: 'EMAIL' | 'IN_APP' | 'AMBOS'
            plantilla_codigo: slug de PlantillaNotificacion (opcional)
            contexto: dict extra para metadata (opcional)
            destinatario_email: str, email para envío sin Personal
        Returns:
            Notificacion | list[Notificacion]
        """
        from comunicaciones.models import Notificacion, PlantillaNotificacion

        plantilla = None
        if plantilla_codigo:
            plantilla = PlantillaNotificacion.objects.filter(
                codigo=plantilla_codigo, activa=True
            ).first()

        # Resolver email del destinatario
        email = destinatario_email
        if not email and destinatario:
            email = (destinatario.correo_corporativo
                     or destinatario.correo_personal
                     or '')

        # Resolver telefono del destinatario (para WhatsApp)
        telefono = ''
        if destinatario:
            telefono = getattr(destinatario, 'celular', '') or ''

        if tipo == 'AMBOS':
            notif_app = Notificacion.objects.create(
                destinatario=destinatario,
                destinatario_email=email,
                asunto=asunto,
                cuerpo=cuerpo,
                tipo='IN_APP',
                estado='ENVIADA',
                plantilla=plantilla,
                enviada_en=timezone.now(),
                metadata=contexto or {},
            )
            notif_email = Notificacion.objects.create(
                destinatario=destinatario,
                destinatario_email=email,
                asunto=asunto,
                cuerpo=cuerpo,
                tipo='EMAIL',
                estado='PENDIENTE',
                plantilla=plantilla,
                metadata=contexto or {},
            )
            NotificacionService._enviar_email(notif_email)
            return [notif_app, notif_email]

        estado_inicial = 'PENDIENTE'
        enviada_en = None
        if tipo == 'IN_APP':
            # In-app se marca como ENVIADA de inmediato (disponible al instante)
            estado_inicial = 'ENVIADA'
            enviada_en = timezone.now()

        notif = Notificacion.objects.create(
            destinatario=destinatario,
            destinatario_email=email,
            destinatario_telefono=telefono,
            asunto=asunto,
            cuerpo=cuerpo,
            tipo=tipo,
            estado=estado_inicial,
            plantilla=plantilla,
            enviada_en=enviada_en,
            metadata=contexto or {},
        )

        if tipo == 'EMAIL':
            NotificacionService._enviar_email(notif)
        elif tipo == 'WHATSAPP':
            NotificacionService._enviar_whatsapp(notif)

        return notif

    # ── Envío desde plantilla ────────────────────────────────

    @staticmethod
    def enviar_desde_plantilla(destinatario, plantilla_codigo, contexto_dict):
        """
        Carga una PlantillaNotificacion, renderiza asunto/cuerpo con el
        contexto dado y envía la notificación.

        Args:
            destinatario: instancia de Personal
            plantilla_codigo: slug de la plantilla
            contexto_dict: dict con las variables para el template
        Returns:
            Notificacion | list[Notificacion] | None
        """
        from comunicaciones.models import PlantillaNotificacion

        try:
            plantilla = PlantillaNotificacion.objects.get(
                codigo=plantilla_codigo, activa=True
            )
        except PlantillaNotificacion.DoesNotExist:
            logger.warning(
                f"Plantilla '{plantilla_codigo}' no encontrada o inactiva. "
                f"Notificación no enviada a {destinatario}."
            )
            return None

        # Renderizar templates
        ctx = Context(contexto_dict)
        asunto = Template(plantilla.asunto_template).render(ctx)
        cuerpo = Template(plantilla.cuerpo_template).render(ctx)

        return NotificacionService.enviar(
            destinatario=destinatario,
            asunto=asunto,
            cuerpo=cuerpo,
            tipo=plantilla.tipo,
            plantilla_codigo=plantilla_codigo,
            contexto=contexto_dict,
        )

    # ── Envío masivo ─────────────────────────────────────────

    @staticmethod
    def enviar_masivo(comunicado):
        """
        Resuelve destinatarios del ComunicadoMasivo y crea una
        Notificacion IN_APP para cada uno.

        Args:
            comunicado: instancia de ComunicadoMasivo
        Returns:
            int: cantidad de notificaciones creadas
        """
        from comunicaciones.models import Notificacion

        destinatarios = comunicado._resolver_destinatarios()
        ahora = timezone.now()
        notificaciones = []

        for personal in destinatarios:
            notificaciones.append(Notificacion(
                destinatario=personal,
                destinatario_email=(personal.correo_corporativo
                                    or personal.correo_personal
                                    or ''),
                asunto=comunicado.titulo,
                cuerpo=comunicado.cuerpo,
                tipo='IN_APP',
                estado='ENVIADA',
                enviada_en=ahora,
                metadata={
                    'comunicado_id': comunicado.pk,
                    'tipo_comunicado': comunicado.tipo,
                },
            ))

        if notificaciones:
            Notificacion.objects.bulk_create(notificaciones)

        # Actualizar estado del comunicado
        comunicado.estado = 'ENVIADO'
        comunicado.enviado_en = ahora
        comunicado.save(update_fields=['estado', 'enviado_en'])

        logger.info(
            f"Comunicado '{comunicado.titulo}' enviado a "
            f"{len(notificaciones)} destinatarios."
        )
        return len(notificaciones)

    # ── Helpers ────────────────────────────────────────────────

    @staticmethod
    def _build_empresa_context(personal):
        """
        Build template context dict with empresa branding fields.
        Returns a dict suitable for merging into email template context.
        """
        ctx = {}
        empresa = None
        if personal:
            empresa = getattr(personal, 'empresa', None)

        if empresa:
            ctx['empresa_nombre'] = (
                empresa.nombre_comercial or empresa.razon_social
            )
            ctx['empresa_direccion'] = empresa.direccion or ''
            ctx['empresa_telefono'] = empresa.telefono or ''
            ctx['empresa_email'] = empresa.email_rrhh or ''
            ctx['empresa_web'] = empresa.web or ''
            # If the empresa model gains a logo field in the future,
            # populate empresa_logo_url here.
            ctx['empresa_logo_url'] = ''
        else:
            ctx['empresa_nombre'] = 'Harmoni'
            ctx['empresa_logo_url'] = ''

        return ctx

    @staticmethod
    def _render_branded_email(notificacion):
        """
        If the notification has a matching branded HTML template,
        render it with empresa branding and return the HTML string.
        Otherwise return None (caller falls back to raw cuerpo).
        """
        # Determine template code
        template_code = None
        if notificacion.plantilla:
            template_code = notificacion.plantilla.codigo
        elif notificacion.metadata and isinstance(notificacion.metadata, dict):
            template_code = notificacion.metadata.get('plantilla_codigo')

        template_path = EMAIL_TEMPLATE_MAP.get(template_code) if template_code else None
        if not template_path:
            return None

        # Build context from metadata + empresa branding
        ctx = {}
        if notificacion.metadata and isinstance(notificacion.metadata, dict):
            ctx.update(notificacion.metadata)

        ctx['asunto'] = notificacion.asunto
        ctx.update(
            NotificacionService._build_empresa_context(notificacion.destinatario)
        )

        try:
            return render_to_string(template_path, ctx)
        except Exception as exc:
            logger.warning(
                f"Error rendering branded template '{template_path}': {exc}. "
                f"Falling back to raw cuerpo."
            )
            return None

    # ── Email interno ────────────────────────────────────────

    @staticmethod
    def _enviar_email(notificacion):
        """
        Envía un email usando ConfiguracionSMTP.
        Uses branded HTML templates when a matching template code is found.
        Actualiza el estado de la notificación a ENVIADA o FALLIDA.
        """
        from comunicaciones.models import ConfiguracionSMTP

        config = ConfiguracionSMTP.get()
        if not config.activa:
            notificacion.estado = 'FALLIDA'
            notificacion.error_detalle = 'Configuración SMTP no está activa'
            notificacion.save(update_fields=['estado', 'error_detalle'])
            return

        email_to = notificacion.destinatario_email
        if not email_to and notificacion.destinatario:
            email_to = (notificacion.destinatario.correo_corporativo
                        or notificacion.destinatario.correo_personal)

        if not email_to:
            notificacion.estado = 'FALLIDA'
            notificacion.error_detalle = 'Destinatario sin dirección de email'
            notificacion.save(update_fields=['estado', 'error_detalle'])
            return

        try:
            # Try branded template first, fall back to raw cuerpo
            cuerpo_completo = NotificacionService._render_branded_email(notificacion)
            if not cuerpo_completo:
                # No branded template matched — use raw cuerpo with firma
                cuerpo_completo = notificacion.cuerpo
                if config.firma_html:
                    cuerpo_completo += f"\n<hr>\n{config.firma_html}"

            from django.core.mail import get_connection
            connection = get_connection(
                host=config.smtp_host,
                port=config.smtp_port,
                username=config.smtp_user,
                password=config.smtp_password,
                use_tls=config.smtp_use_tls,
                fail_silently=False,
            )

            email = EmailMessage(
                subject=notificacion.asunto,
                body=cuerpo_completo,
                from_email=config.email_from or config.smtp_user,
                to=[email_to],
                reply_to=[config.email_reply_to] if config.email_reply_to else None,
                connection=connection,
            )
            email.content_subtype = 'html'
            email.send()

            notificacion.estado = 'ENVIADA'
            notificacion.enviada_en = timezone.now()
            notificacion.save(update_fields=['estado', 'enviada_en'])

            logger.info(f"Email enviado: {notificacion.asunto} → {email_to}")

        except Exception as e:
            notificacion.estado = 'FALLIDA'
            notificacion.error_detalle = str(e)[:500]
            notificacion.save(update_fields=['estado', 'error_detalle'])
            logger.error(f"Error enviando email a {email_to}: {e}")

    # ── WhatsApp interno ─────────────────────────────────────

    @staticmethod
    def _enviar_whatsapp(notificacion):
        """
        Envía un mensaje de WhatsApp usando WhatsAppService.
        Actualiza el estado de la notificación a ENVIADA o FALLIDA.
        """
        from comunicaciones.whatsapp_service import WhatsAppService

        # Resolver telefono
        telefono = notificacion.destinatario_telefono
        if not telefono and notificacion.destinatario:
            telefono = getattr(notificacion.destinatario, 'celular', '')

        if not telefono:
            notificacion.estado = 'FALLIDA'
            notificacion.error_detalle = 'Destinatario sin numero de telefono/celular'
            notificacion.save(update_fields=['estado', 'error_detalle'])
            return

        # Resolve empresa for per-company WhatsApp config
        empresa = None
        if notificacion.destinatario:
            empresa = getattr(notificacion.destinatario, 'empresa', None)

        # Strip HTML tags for WhatsApp (plain text)
        import re
        texto = re.sub(r'<[^>]+>', '', notificacion.cuerpo)
        texto = texto.strip()

        # Prepend asunto if meaningful
        if notificacion.asunto:
            texto = f"*{notificacion.asunto}*\n\n{texto}"

        try:
            result = WhatsAppService.send_message(telefono, texto, empresa=empresa)

            if result.get('ok'):
                notificacion.estado = 'ENVIADA'
                notificacion.enviada_en = timezone.now()
                notificacion.metadata = notificacion.metadata or {}
                notificacion.metadata['whatsapp_message_id'] = result.get('message_id')
                notificacion.metadata['whatsapp_provider'] = result.get('provider')
                notificacion.save(update_fields=['estado', 'enviada_en', 'metadata'])
                logger.info(
                    f"WhatsApp enviado: {notificacion.asunto} -> {telefono} "
                    f"via {result.get('provider')}"
                )
            else:
                notificacion.estado = 'FALLIDA'
                notificacion.error_detalle = result.get('detail', 'Error desconocido')[:500]
                notificacion.save(update_fields=['estado', 'error_detalle'])
                logger.error(
                    f"Error enviando WhatsApp a {telefono}: {result.get('detail')}"
                )

        except Exception as e:
            notificacion.estado = 'FALLIDA'
            notificacion.error_detalle = str(e)[:500]
            notificacion.save(update_fields=['estado', 'error_detalle'])
            logger.error(f"Error enviando WhatsApp a {telefono}: {e}")

    # ── Alias crear() ────────────────────────────────────────

    @staticmethod
    def crear(usuario, tipo, titulo, mensaje, url='#', icono='fa-bell', color='#0f766e'):
        """
        Alias conveniente para crear notificaciones IN_APP.

        Acepta un User de Django (no un Personal) o un Personal directamente.
        El parámetro `tipo` puede ser cualquier string descriptivo (SISTEMA, ALERTA, INFO…)
        — se almacena en metadata para filtrar/agrupar en la bandeja.

        Args:
            usuario: User de Django o Personal.
            tipo: str descriptivo del tipo (SISTEMA, ALERTA, INFO, etc.)
            titulo: str — asunto de la notificación.
            mensaje: str — cuerpo (puede ser texto plano o HTML).
            url: str — enlace de acción (opcional).
            icono: str — clase Font Awesome (opcional).
            color: str — color hex (opcional).
        Returns:
            Notificacion creada.
        """
        from personal.models import Personal as PersonalModel

        # Resolver el Personal vinculado al User si es necesario
        destinatario = None
        if isinstance(usuario, PersonalModel):
            destinatario = usuario
        else:
            # Asumir que es un User de Django
            destinatario = getattr(usuario, 'personal_data', None)

        return NotificacionService.enviar(
            destinatario=destinatario,
            asunto=titulo,
            cuerpo=f'<p>{mensaje}</p>',
            tipo='IN_APP',
            contexto={
                'tipo_notificacion': tipo,
                'icono': icono,
                'color': color,
                'url': url,
            },
        )

    # ── Marcar como leída ────────────────────────────────────

    @staticmethod
    def marcar_leida(notificacion_id):
        """Marca una notificación IN_APP como LEIDA."""
        from comunicaciones.models import Notificacion

        try:
            notif = Notificacion.objects.get(pk=notificacion_id)
            if notif.estado in ('ENVIADA', 'PENDIENTE'):
                notif.estado = 'LEIDA'
                notif.leida_en = timezone.now()
                notif.save(update_fields=['estado', 'leida_en'])
                return True
        except Notificacion.DoesNotExist:
            pass
        return False

    # ── Conteo de pendientes ─────────────────────────────────

    @staticmethod
    def notificaciones_pendientes(personal):
        """Retorna el conteo de notificaciones IN_APP no leídas."""
        from comunicaciones.models import Notificacion

        return Notificacion.objects.filter(
            destinatario=personal,
            tipo='IN_APP',
            estado='ENVIADA',
        ).count()
