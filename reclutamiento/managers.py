from django.db import models
from django.db.models import Q

from empresas.request_scope import current_request_scope


class VacanteManager(models.Manager):
    """Defensa profunda para no olvidar el RUC en una vista web."""

    def get_queryset(self):
        qs = super().get_queryset()
        scope = current_request_scope()
        if scope is None:
            return qs
        if scope.deny:
            return qs.none()
        if scope.include_unassigned:
            return qs.filter(Q(empresa_id=scope.company_id) | Q(empresa__isnull=True))
        return qs.filter(empresa_id=scope.company_id)


class PostulacionManager(models.Manager):
    """Hereda el RUC desde la vacante del candidato."""

    def get_queryset(self):
        qs = super().get_queryset()
        scope = current_request_scope()
        if scope is None:
            return qs
        if scope.deny:
            return qs.none()
        if scope.include_unassigned:
            return qs.filter(
                Q(vacante__empresa_id=scope.company_id) |
                Q(vacante__empresa__isnull=True)
            )
        return qs.filter(vacante__empresa_id=scope.company_id)
