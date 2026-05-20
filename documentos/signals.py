"""
Signals para tracking de actividad del trabajador (compliance DS 009-2011-TR).

Conecta:
- user_logged_in → LogActividadTrabajador('LOGIN')
- user_login_failed → LogActividadTrabajador('LOGIN_FAILED')
- user_logged_out → LogActividadTrabajador('LOGOUT')

Solo se loguean eventos de trabajadores con Personal vinculado (no admins
puros). Esto evita poluir el log con actividad de RRHH/contadores.
"""
from __future__ import annotations

import logging

from django.contrib.auth.signals import (
    user_logged_in, user_logged_out, user_login_failed,
)
from django.dispatch import receiver

logger = logging.getLogger(__name__)


def _personal_de_usuario(user):
    """Devuelve el Personal vinculado al user, o None."""
    if user is None or not user.is_authenticated:
        return None
    # Personal.usuario tiene related_name='personal_data'
    return getattr(user, 'personal_data', None)


def _extraer_ip_ua(request):
    if request is None:
        return None, ''
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    ip = xff.split(',')[0].strip() if xff else request.META.get('REMOTE_ADDR')
    ua = (request.META.get('HTTP_USER_AGENT') or '')[:500]
    return ip, ua


@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    """Registra login en el LogActividad cuando el user tiene Personal vinculado."""
    personal = _personal_de_usuario(user)
    if personal is None:
        return  # admin sin Personal: no contamos
    try:
        from .models import LogActividadTrabajador
        LogActividadTrabajador.registrar(
            personal=personal,
            tipo='LOGIN',
            request=request,
        )
    except Exception as exc:
        logger.warning('No se pudo registrar LOGIN log: %s', exc)


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    """Registra logout."""
    personal = _personal_de_usuario(user)
    if personal is None:
        return
    try:
        from .models import LogActividadTrabajador
        LogActividadTrabajador.registrar(
            personal=personal,
            tipo='LOGOUT',
            request=request,
        )
    except Exception as exc:
        logger.warning('No se pudo registrar LOGOUT log: %s', exc)


@receiver(user_login_failed)
def log_login_failed(sender, credentials, request, **kwargs):
    """Registra intento fallido — útil para detectar brute-force / typos."""
    # No tenemos user (login falló) → buscar Personal por username = DNI.
    username = (credentials or {}).get('username', '')
    if not username:
        return
    try:
        from personal.models import Personal
        personal = Personal.objects.filter(nro_doc=username).first()
        if personal is None:
            return  # username no corresponde a un trabajador
        ip, ua = _extraer_ip_ua(request)
        from .models import LogActividadTrabajador
        LogActividadTrabajador.objects.create(
            personal=personal,
            usuario=None,
            tipo='LOGIN_FAILED',
            ip=ip,
            user_agent=ua,
            metadata={'username_intentado': username[:50]},
        )
    except Exception as exc:
        logger.warning('No se pudo registrar LOGIN_FAILED: %s', exc)
