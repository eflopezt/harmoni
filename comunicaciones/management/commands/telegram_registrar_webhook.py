"""
Registra el webhook de aprobaciones en la Bot API de Telegram.

Uso (en el servidor, con TELEGRAM_WEBHOOK_SECRET en el entorno):
    python manage.py telegram_registrar_webhook
    python manage.py telegram_registrar_webhook --url https://harmoni.pe

Requiere ConfiguracionSistema.telegram_bot_token configurado.
"""
import json
import os
import urllib.request

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Registra el webhook de Telegram para aprobaciones inline.'

    def add_arguments(self, parser):
        parser.add_argument('--url', default='https://harmoni.pe',
                            help='Base pública del sitio (default: https://harmoni.pe)')

    def handle(self, *args, **opts):
        from asistencia.models import ConfiguracionSistema

        token = (ConfiguracionSistema.get().telegram_bot_token or '').strip()
        if not token:
            raise CommandError('ConfiguracionSistema.telegram_bot_token no configurado.')
        secret = (os.environ.get('TELEGRAM_WEBHOOK_SECRET') or '').strip()
        if not secret:
            raise CommandError('TELEGRAM_WEBHOOK_SECRET no está en el entorno.')

        webhook_url = opts['url'].rstrip('/') + '/comunicaciones/telegram/webhook/'
        payload = json.dumps({
            'url': webhook_url,
            'secret_token': secret,
            'allowed_updates': ['callback_query'],
        }).encode('utf-8')
        req = urllib.request.Request(
            f'https://api.telegram.org/bot{token}/setWebhook',
            data=payload, headers={'Content-Type': 'application/json'}, method='POST',
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        if not data.get('ok'):
            raise CommandError(f'setWebhook falló: {data}')
        self.stdout.write(self.style.SUCCESS(f'Webhook registrado: {webhook_url}'))
