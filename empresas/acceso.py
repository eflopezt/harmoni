"""Reglas centrales de acceso multiempresa.

La empresa elegida en la sesion es una preferencia de interfaz, no una
autorizacion. Todas las vistas que trabajan con datos por RUC deben resolver
su alcance desde estas funciones.
"""
from __future__ import annotations

from django.db.models import Q, QuerySet

from .models import Empresa


def empresas_accesibles(user, *, activas=True) -> QuerySet:
    """Empresas que ``user`` puede operar, con politica fail-closed."""
    qs = Empresa.objects.all()
    if activas:
        qs = qs.filter(activa=True)
    if not getattr(user, 'is_authenticated', False):
        return qs.none()
    if user.is_superuser:
        return qs
    return qs.filter(
        Q(creado_por=user) | Q(personal__usuario=user)
    ).distinct()


def empresa_es_accesible(user, empresa) -> bool:
    if empresa is None:
        return False
    return empresas_accesibles(user).filter(pk=empresa.pk).exists()


def empresas_del_request(request) -> QuerySet:
    """Alcance efectivo: un RUC o el consolidado de un superusuario."""
    permitidas = empresas_accesibles(request.user)
    actual = getattr(request, 'empresa_actual', None)
    if actual is not None:
        return permitidas.filter(pk=actual.pk)
    if request.user.is_superuser and getattr(request, 'modo_consolidado', False):
        return permitidas
    return permitidas.none()


def filtrar_por_empresas(qs, request, campo='empresa'):
    """Restringe ``qs`` al alcance efectivo usando una ruta ORM a Empresa."""
    return qs.filter(**{f'{campo}__in': empresas_del_request(request)})
