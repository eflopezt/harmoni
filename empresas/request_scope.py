"""Contexto aislado del RUC activo durante un request web."""
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class RequestCompanyScope:
    company_id: int | None = None
    deny: bool = False
    include_unassigned: bool = False


_scope = ContextVar('harmoni_request_company_scope', default=None)


def activate_request_scope(request):
    """Activa alcance solo para usuarios de sesion ya autenticados."""
    if not getattr(request.user, 'is_authenticated', False):
        return _scope.set(None)
    empresa = getattr(request, 'empresa_actual', None)
    if empresa is not None:
        return _scope.set(RequestCompanyScope(
            company_id=empresa.pk,
            include_unassigned=bool(request.user.is_superuser),
        ))
    if request.user.is_superuser and getattr(request, 'modo_consolidado', False):
        return _scope.set(None)
    return _scope.set(RequestCompanyScope(deny=True))


def reset_request_scope(token):
    _scope.reset(token)


def current_request_scope():
    return _scope.get()
