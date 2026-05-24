"""
Cliente HTTP para hablar con el sidecar Baileys (harmoni-wa-bot).

Lee config de Django settings:
  WA_BOT_URL          (default http://127.0.0.1:3001)
  WA_BOT_API_TOKEN    (opcional, Bearer token)

Cuando migremos a Meta Cloud API, este módulo se reemplaza por una
implementación que llama a graph.facebook.com — la interfaz pública
(send_text, send_menu) se queda igual.
"""
import logging

import requests
from django.conf import settings

logger = logging.getLogger('wa_marketing')

DEFAULT_BOT_URL = 'http://127.0.0.1:3001'


def _base_url() -> str:
    return getattr(settings, 'WA_BOT_URL', DEFAULT_BOT_URL).rstrip('/')


def _headers() -> dict:
    token = getattr(settings, 'WA_BOT_API_TOKEN', '')
    h = {'Content-Type': 'application/json'}
    if token:
        h['Authorization'] = f'Bearer {token}'
    return h


def send_text(phone: str, message: str) -> dict:
    """
    Envía un mensaje de texto. Retorna {'ok': bool, 'id': str|None, 'error': str|None}.
    """
    try:
        resp = requests.post(
            f'{_base_url()}/send',
            json={'phone': phone, 'message': message},
            headers=_headers(),
            timeout=15,
        )
        data = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}
        if resp.ok and data.get('ok'):
            return {'ok': True, 'id': data.get('id'), 'error': None}
        return {'ok': False, 'id': None, 'error': data.get('error') or f'HTTP {resp.status_code}'}
    except requests.RequestException as e:
        logger.error('send_text falló: %s', e)
        return {'ok': False, 'id': None, 'error': str(e)}


def send_menu(phone: str, text: str, sections: list,
              footer: str = 'Harmoni ERP', button_text: str = 'Ver opciones') -> dict:
    """
    Envía un mensaje de lista (Baileys soporta listMessage nativo).

    sections: lista de dicts con shape:
      [{'title': 'Opciones', 'rows': [{'title': '...', 'rowId': '1'}, ...]}]
    """
    try:
        resp = requests.post(
            f'{_base_url()}/send-menu',
            json={
                'phone': phone,
                'text': text,
                'sections': sections,
                'footer': footer,
                'buttonText': button_text,
            },
            headers=_headers(),
            timeout=15,
        )
        data = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}
        if resp.ok and data.get('ok'):
            return {'ok': True, 'id': data.get('id'), 'error': None}
        return {'ok': False, 'id': None, 'error': data.get('error') or f'HTTP {resp.status_code}'}
    except requests.RequestException as e:
        logger.error('send_menu falló: %s', e)
        return {'ok': False, 'id': None, 'error': str(e)}


def status() -> dict:
    """Devuelve el estado del sidecar (conectado, QR pendiente, etc.)."""
    try:
        resp = requests.get(f'{_base_url()}/status', headers=_headers(), timeout=5)
        if resp.ok:
            return resp.json()
        return {'ok': False, 'state': 'error', 'error': f'HTTP {resp.status_code}'}
    except requests.RequestException as e:
        return {'ok': False, 'state': 'unreachable', 'error': str(e)}
