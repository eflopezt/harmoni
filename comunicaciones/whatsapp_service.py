"""
Servicio de WhatsApp para Harmoni ERP.

Soporta dos proveedores:
  1. Meta Cloud API (WhatsApp Business Platform)
  2. OpenClaw gateway (proxy local HTTP en localhost:19000)

Uso:
    from comunicaciones.whatsapp_service import WhatsAppService

    # Mensaje de texto simple
    WhatsAppService.send_message('51999888777', 'Hola desde Harmoni')

    # Mensaje con plantilla aprobada por Meta
    WhatsAppService.send_template('51999888777', 'boleta_disponible', ['Enero 2026', 'S/ 3,500'])
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger('comunicaciones.whatsapp')

# Meta Graph API base
META_GRAPH_URL = 'https://graph.facebook.com/v21.0'

# Default OpenClaw gateway
DEFAULT_OPENCLAW_URL = 'http://localhost:19000'


class WhatsAppService:
    """Send messages via WhatsApp Cloud API (Meta) or OpenClaw gateway."""

    # ── Public API ────────────────────────────────────────────

    @staticmethod
    def send_message(phone_number: str, message: str, empresa=None) -> dict:
        """
        Send a WhatsApp text message to a phone number.

        Args:
            phone_number: International format without '+' (e.g. '51999888777')
            message: Plain text message body
            empresa: Optional Empresa instance for per-company config

        Returns:
            dict with keys: ok (bool), provider (str), detail (str), message_id (str|None)
        """
        phone_number = WhatsAppService._normalize_phone(phone_number)
        if not phone_number:
            return {'ok': False, 'provider': 'none', 'detail': 'Numero de telefono invalido', 'message_id': None}

        config = WhatsAppService._get_config(empresa)
        provider = config.get('provider', 'NONE')

        if provider == 'META_CLOUD':
            return WhatsAppService._send_meta_text(phone_number, message, config)
        elif provider == 'OPENCLAW':
            return WhatsAppService._send_openclaw_text(phone_number, message, config)
        else:
            # Try OpenClaw as fallback (might be running locally)
            return WhatsAppService._send_openclaw_text(phone_number, message, config)

    @staticmethod
    def send_template(phone_number: str, template_name: str, params: list,
                      language: str = 'es', empresa=None) -> dict:
        """
        Send a WhatsApp template message (pre-approved by Meta).

        Args:
            phone_number: International format without '+' (e.g. '51999888777')
            template_name: Template name as registered in Meta Business Manager
            params: List of string parameters for the template body
            language: Language code (default 'es')
            empresa: Optional Empresa instance

        Returns:
            dict with keys: ok, provider, detail, message_id
        """
        phone_number = WhatsAppService._normalize_phone(phone_number)
        if not phone_number:
            return {'ok': False, 'provider': 'none', 'detail': 'Numero de telefono invalido', 'message_id': None}

        config = WhatsAppService._get_config(empresa)
        provider = config.get('provider', 'NONE')

        if provider == 'META_CLOUD':
            return WhatsAppService._send_meta_template(phone_number, template_name, params, language, config)
        elif provider == 'OPENCLAW':
            # OpenClaw does not support templates — send as plain text with rendered params
            rendered = f"[{template_name}] " + " | ".join(str(p) for p in params)
            return WhatsAppService._send_openclaw_text(phone_number, rendered, config)
        else:
            return {'ok': False, 'provider': 'none',
                    'detail': 'WhatsApp no configurado. Configure META_CLOUD u OPENCLAW.',
                    'message_id': None}

    @staticmethod
    def test_connection(empresa=None) -> dict:
        """
        Test WhatsApp connectivity.

        Returns:
            dict with ok, provider, detail
        """
        config = WhatsAppService._get_config(empresa)
        provider = config.get('provider', 'NONE')

        if provider == 'META_CLOUD':
            return WhatsAppService._test_meta(config)
        elif provider == 'OPENCLAW':
            return WhatsAppService._test_openclaw(config)
        else:
            return {'ok': False, 'provider': 'NONE',
                    'detail': 'WhatsApp no configurado'}

    # ── Meta Cloud API ────────────────────────────────────────

    @staticmethod
    def _send_meta_text(phone: str, message: str, config: dict) -> dict:
        """Send plain text via Meta WhatsApp Cloud API."""
        phone_id = config.get('meta_phone_id', '')
        token = config.get('meta_access_token', '')

        if not phone_id or not token:
            return {'ok': False, 'provider': 'META_CLOUD',
                    'detail': 'Falta phone_number_id o access_token de Meta',
                    'message_id': None}

        url = f"{META_GRAPH_URL}/{phone_id}/messages"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }
        payload = {
            'messaging_product': 'whatsapp',
            'to': phone,
            'type': 'text',
            'text': {'body': message},
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            data = resp.json()

            if resp.status_code in (200, 201):
                msg_id = None
                if 'messages' in data and data['messages']:
                    msg_id = data['messages'][0].get('id')
                logger.info(f"WhatsApp Meta enviado a {phone}: {msg_id}")
                return {'ok': True, 'provider': 'META_CLOUD',
                        'detail': 'Mensaje enviado', 'message_id': msg_id}
            else:
                error_msg = data.get('error', {}).get('message', resp.text[:200])
                logger.error(f"WhatsApp Meta error {resp.status_code}: {error_msg}")
                return {'ok': False, 'provider': 'META_CLOUD',
                        'detail': f"Error Meta API: {error_msg}", 'message_id': None}

        except requests.RequestException as e:
            logger.error(f"WhatsApp Meta request failed: {e}")
            return {'ok': False, 'provider': 'META_CLOUD',
                    'detail': f"Error de conexion: {e}", 'message_id': None}

    @staticmethod
    def _send_meta_template(phone: str, template_name: str, params: list,
                            language: str, config: dict) -> dict:
        """Send a template message via Meta WhatsApp Cloud API."""
        phone_id = config.get('meta_phone_id', '')
        token = config.get('meta_access_token', '')

        if not phone_id or not token:
            return {'ok': False, 'provider': 'META_CLOUD',
                    'detail': 'Falta phone_number_id o access_token de Meta',
                    'message_id': None}

        url = f"{META_GRAPH_URL}/{phone_id}/messages"
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }

        # Build components with parameters
        components = []
        if params:
            components.append({
                'type': 'body',
                'parameters': [
                    {'type': 'text', 'text': str(p)} for p in params
                ],
            })

        payload = {
            'messaging_product': 'whatsapp',
            'to': phone,
            'type': 'template',
            'template': {
                'name': template_name,
                'language': {'code': language},
            },
        }
        if components:
            payload['template']['components'] = components

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=15)
            data = resp.json()

            if resp.status_code in (200, 201):
                msg_id = None
                if 'messages' in data and data['messages']:
                    msg_id = data['messages'][0].get('id')
                logger.info(f"WhatsApp Meta template '{template_name}' enviado a {phone}")
                return {'ok': True, 'provider': 'META_CLOUD',
                        'detail': 'Template enviado', 'message_id': msg_id}
            else:
                error_msg = data.get('error', {}).get('message', resp.text[:200])
                logger.error(f"WhatsApp Meta template error: {error_msg}")
                return {'ok': False, 'provider': 'META_CLOUD',
                        'detail': f"Error Meta API: {error_msg}", 'message_id': None}

        except requests.RequestException as e:
            logger.error(f"WhatsApp Meta template request failed: {e}")
            return {'ok': False, 'provider': 'META_CLOUD',
                    'detail': f"Error de conexion: {e}", 'message_id': None}

    @staticmethod
    def _test_meta(config: dict) -> dict:
        """Test Meta Cloud API connectivity by verifying the token."""
        token = config.get('meta_access_token', '')
        phone_id = config.get('meta_phone_id', '')

        if not token or not phone_id:
            return {'ok': False, 'provider': 'META_CLOUD',
                    'detail': 'Falta access_token o phone_number_id'}

        try:
            url = f"{META_GRAPH_URL}/{phone_id}"
            headers = {'Authorization': f'Bearer {token}'}
            resp = requests.get(url, headers=headers, timeout=10)

            if resp.status_code == 200:
                data = resp.json()
                display = data.get('display_phone_number', phone_id)
                return {'ok': True, 'provider': 'META_CLOUD',
                        'detail': f'Conectado: {display}'}
            else:
                return {'ok': False, 'provider': 'META_CLOUD',
                        'detail': f'Error {resp.status_code}: {resp.text[:200]}'}
        except requests.RequestException as e:
            return {'ok': False, 'provider': 'META_CLOUD',
                    'detail': f'Error de conexion: {e}'}

    # ── OpenClaw Gateway ──────────────────────────────────────

    @staticmethod
    def _send_openclaw_text(phone: str, message: str, config: dict) -> dict:
        """Send plain text via OpenClaw HTTP gateway."""
        base_url = config.get('openclaw_url', DEFAULT_OPENCLAW_URL)
        token = config.get('openclaw_token', '')

        url = f"{base_url.rstrip('/')}/api/sendMessage"
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'

        payload = {
            'phone': phone,
            'message': message,
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=15)

            if resp.status_code in (200, 201):
                data = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}
                msg_id = data.get('id') or data.get('message_id')
                logger.info(f"WhatsApp OpenClaw enviado a {phone}")
                return {'ok': True, 'provider': 'OPENCLAW',
                        'detail': 'Mensaje enviado via OpenClaw', 'message_id': msg_id}
            else:
                detail = resp.text[:200] if resp.text else f'HTTP {resp.status_code}'
                logger.error(f"WhatsApp OpenClaw error: {detail}")
                return {'ok': False, 'provider': 'OPENCLAW',
                        'detail': f"Error OpenClaw: {detail}", 'message_id': None}

        except requests.ConnectionError:
            logger.error(f"WhatsApp OpenClaw no disponible en {base_url}")
            return {'ok': False, 'provider': 'OPENCLAW',
                    'detail': f"No se pudo conectar a OpenClaw en {base_url}. Verifica que el servicio este activo.",
                    'message_id': None}
        except requests.RequestException as e:
            logger.error(f"WhatsApp OpenClaw request failed: {e}")
            return {'ok': False, 'provider': 'OPENCLAW',
                    'detail': f"Error de conexion: {e}", 'message_id': None}

    @staticmethod
    def _test_openclaw(config: dict) -> dict:
        """Test OpenClaw gateway connectivity."""
        base_url = config.get('openclaw_url', DEFAULT_OPENCLAW_URL)
        token = config.get('openclaw_token', '')

        try:
            url = f"{base_url.rstrip('/')}/api/status"
            headers = {}
            if token:
                headers['Authorization'] = f'Bearer {token}'

            resp = requests.get(url, headers=headers, timeout=5)

            if resp.status_code == 200:
                return {'ok': True, 'provider': 'OPENCLAW',
                        'detail': f'OpenClaw activo en {base_url}'}
            else:
                return {'ok': False, 'provider': 'OPENCLAW',
                        'detail': f'OpenClaw respondio {resp.status_code}'}
        except requests.ConnectionError:
            return {'ok': False, 'provider': 'OPENCLAW',
                    'detail': f'No se pudo conectar a {base_url}'}
        except requests.RequestException as e:
            return {'ok': False, 'provider': 'OPENCLAW',
                    'detail': f'Error: {e}'}

    # ── Configuration helpers ─────────────────────────────────

    @staticmethod
    def _get_config(empresa=None) -> dict:
        """
        Build WhatsApp configuration dict.

        Priority:
        1. Empresa-level config (if empresa has whatsapp fields)
        2. ConfiguracionSistema (global singleton)
        3. Django settings (WHATSAPP_* variables)
        """
        config = {
            'provider': 'NONE',
            'meta_phone_id': '',
            'meta_access_token': '',
            'openclaw_url': DEFAULT_OPENCLAW_URL,
            'openclaw_token': '',
        }

        # 1. Try Empresa-level config
        if empresa:
            provider = getattr(empresa, 'whatsapp_provider', 'NONE')
            if provider and provider != 'NONE':
                config['provider'] = provider
                config['meta_phone_id'] = getattr(empresa, 'whatsapp_phone_id', '')
                config['meta_access_token'] = getattr(empresa, 'whatsapp_access_token', '')
                config['openclaw_url'] = getattr(empresa, 'openclaw_gateway_url', '') or DEFAULT_OPENCLAW_URL
                config['openclaw_token'] = getattr(empresa, 'openclaw_gateway_token', '')
                return config

        # 2. Try ConfiguracionSistema (global)
        try:
            from asistencia.models import ConfiguracionSistema
            cfg = ConfiguracionSistema.objects.filter(pk=1).first()
            if cfg:
                wa_provider = getattr(cfg, 'whatsapp_provider', '')
                meta_phone_id = getattr(cfg, 'whatsapp_phone_number_id', '')
                meta_token = getattr(cfg, 'whatsapp_access_token', '')
                openclaw_url = getattr(cfg, 'openclaw_gateway_url', '')
                openclaw_token = getattr(cfg, 'openclaw_gateway_token', '')

                if wa_provider and wa_provider != 'NONE':
                    config['provider'] = wa_provider
                elif meta_token and meta_phone_id:
                    config['provider'] = 'META_CLOUD'
                elif openclaw_url:
                    config['provider'] = 'OPENCLAW'

                config['meta_phone_id'] = meta_phone_id
                config['meta_access_token'] = meta_token
                config['openclaw_url'] = openclaw_url or DEFAULT_OPENCLAW_URL
                config['openclaw_token'] = openclaw_token
        except Exception:
            pass

        # 3. Fallback to Django settings
        if config['provider'] == 'NONE':
            s_provider = getattr(settings, 'WHATSAPP_PROVIDER', '')
            if s_provider:
                config['provider'] = s_provider
            config['meta_phone_id'] = getattr(settings, 'WHATSAPP_PHONE_ID', '') or config['meta_phone_id']
            config['meta_access_token'] = getattr(settings, 'WHATSAPP_ACCESS_TOKEN', '') or config['meta_access_token']
            config['openclaw_url'] = getattr(settings, 'OPENCLAW_GATEWAY_URL', '') or config['openclaw_url']
            config['openclaw_token'] = getattr(settings, 'OPENCLAW_GATEWAY_TOKEN', '') or config['openclaw_token']

        return config

    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """
        Normalize phone number to international format without '+'.
        Accepts: +51999888777, 51999888777, 999888777 (assumes Peru +51)
        Returns: '51999888777' or '' if invalid.
        """
        if not phone:
            return ''

        # Strip whitespace, dashes, parens, dots
        cleaned = ''.join(c for c in str(phone) if c.isdigit())

        if not cleaned:
            return ''

        # If starts with 0, strip leading zero
        if cleaned.startswith('0'):
            cleaned = cleaned[1:]

        # If 9 digits and starts with 9 — Peruvian mobile, prepend 51
        if len(cleaned) == 9 and cleaned.startswith('9'):
            cleaned = '51' + cleaned

        # Must be at least 10 digits for international format
        if len(cleaned) < 10:
            return ''

        return cleaned


# ── Notification Templates ────────────────────────────────────
# Pre-built message builders for common HR events.

class WhatsAppTemplates:
    """Pre-built WhatsApp message templates for common HR events."""

    @staticmethod
    def vacacion_aprobada(nombre: str, fecha_inicio: str, fecha_fin: str, dias: int) -> str:
        """Vacation request approved."""
        return (
            f"Hola {nombre}, tu solicitud de vacaciones ha sido *aprobada*.\n\n"
            f"Periodo: {fecha_inicio} al {fecha_fin}\n"
            f"Dias: {dias}\n\n"
            f"Recuerda coordinar la entrega de pendientes con tu jefe directo.\n"
            f"— Harmoni RRHH"
        )

    @staticmethod
    def vacacion_rechazada(nombre: str, fecha_inicio: str, fecha_fin: str, motivo: str = '') -> str:
        """Vacation request rejected."""
        msg = (
            f"Hola {nombre}, lamentamos informarte que tu solicitud de vacaciones "
            f"del {fecha_inicio} al {fecha_fin} ha sido *rechazada*."
        )
        if motivo:
            msg += f"\n\nMotivo: {motivo}"
        msg += "\n\nPor favor comunicate con tu jefe directo para mas detalles.\n— Harmoni RRHH"
        return msg

    @staticmethod
    def boleta_disponible(nombre: str, periodo: str, monto_neto: str) -> str:
        """Payslip available for download."""
        return (
            f"Hola {nombre}, tu boleta de pago de *{periodo}* ya esta disponible.\n\n"
            f"Monto neto: {monto_neto}\n\n"
            f"Puedes descargarla desde el portal de empleados.\n"
            f"— Harmoni RRHH"
        )

    @staticmethod
    def cumpleanos(nombre: str) -> str:
        """Birthday greeting."""
        return (
            f"Feliz cumpleanos {nombre}!\n\n"
            f"Todo el equipo te desea un excelente dia. "
            f"Que este nuevo ano de vida te traiga muchos exitos.\n\n"
            f"— Tu equipo de Harmoni"
        )

    @staticmethod
    def contrato_por_vencer(nombre: str, fecha_vencimiento: str, dias_restantes: int) -> str:
        """Contract expiring soon."""
        return (
            f"Hola {nombre}, te informamos que tu contrato vence el *{fecha_vencimiento}* "
            f"({dias_restantes} dias restantes).\n\n"
            f"El area de RRHH se comunicara contigo para coordinar la renovacion.\n"
            f"— Harmoni RRHH"
        )

    @staticmethod
    def mensaje_libre(nombre: str, asunto: str, cuerpo: str) -> str:
        """Generic free-form message."""
        return (
            f"Hola {nombre},\n\n"
            f"*{asunto}*\n\n"
            f"{cuerpo}\n\n"
            f"— Harmoni RRHH"
        )
