"""
Health endpoint público de Nóminas — para status pages e integraciones externas.

Sin autenticación: devuelve sólo métricas agregadas sin datos sensibles.

URL: /api/health/nominas/
"""
from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET


@require_GET
@cache_page(60)  # cache 1 min — datos cambian poco y queremos blindar de abuso
def nominas_health(request):
    """
    Endpoint sin auth con métricas agregadas.

    Acepta ?empresa=<id> para filtrar a una empresa específica (multi-tenant, ADR-001).
    Sin parámetro: métricas globales del sistema.

    NO devuelve datos sensibles (sin códigos, nombres, RUC, ni montos).
    """
    payload = {
        'status':           'ok',
        'service':          'harmoni-nominas',
        'timestamp':        None,
        'empresa_id':       None,
        'empresa_ruc':      None,
        'onboarding_score': None,
        'conceptos':        {'activos': 0, 'total': 0},
        'cambios_7d':       0,
    }

    from django.utils import timezone
    payload['timestamp'] = timezone.now().isoformat()

    # Filtro por empresa (ADR-001: cada empresa puede tener su propio health)
    empresa_filter = request.GET.get('empresa', '').strip()
    empresa = None
    if empresa_filter and empresa_filter.isdigit():
        try:
            from empresas.models import Empresa
            empresa = Empresa.objects.filter(pk=int(empresa_filter)).first()
            if empresa:
                payload['empresa_id'] = empresa.pk
                payload['empresa_ruc'] = empresa.ruc  # RUC público (registrado en SUNAT)
        except Exception:
            pass

    # Onboarding score (no expone qué está mal)
    try:
        from .views_onboarding_validator import build_onboarding_report
        report = build_onboarding_report()
        payload['onboarding_score'] = report['score']
        if report['n_error'] > 0:
            payload['status'] = 'critico'
        elif report['n_warn'] > 0:
            payload['status'] = 'warn'
    except Exception:
        pass

    # Conceptos count (count is safe)
    try:
        from .models import ConceptoRemunerativo
        payload['conceptos']['activos'] = ConceptoRemunerativo.objects.filter(activo=True).count()
        payload['conceptos']['total']   = ConceptoRemunerativo.objects.count()
    except Exception:
        pass

    # Audit log cambios 7d (filtrado por empresa si aplica)
    try:
        from datetime import timedelta
        from .models import ConceptoAuditLog
        desde = timezone.now() - timedelta(days=7)
        qs = ConceptoAuditLog.objects.filter(fecha__gte=desde)
        if empresa:
            qs = qs.filter(empresa=empresa)
        payload['cambios_7d'] = qs.count()
    except Exception:
        pass

    return JsonResponse(payload)
