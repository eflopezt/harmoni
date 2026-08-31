"""
Context processor para alertas de Nóminas en el banner del admin.

Inyecta `nominas_alerts` con un dict de alertas detectadas:
- onboarding_score (si < 80)
- inconsistencias (conceptos)
- acuses_pendientes (boletas sin firmar)
- conceptos_sin_plame (si > 5)

Cached por superuser 5 minutos para perf.
"""
from django.core.cache import cache


_TTL_NOMINAS_ALERTS = 300  # 5 min — barato calcularlos pero no necesitamos refresh constante


def _calcular_alertas(empresa=None):
    """Devuelve dict con todos los flags de alerta — uncached."""
    alertas = {
        'count':            0,
        'onboarding_score': None,
        'inconsistencias':  0,
        'acuses_pendientes': 0,
        'sin_plame':        0,
        'severidad':        'ok',  # ok / warn / critico
    }

    # Onboarding score
    try:
        from .views_onboarding_validator import build_onboarding_report
        report = build_onboarding_report(empresa)
        alertas['onboarding_score'] = report['score']
        if report['n_error'] > 0:
            alertas['count'] += report['n_error']
            alertas['severidad'] = 'critico'
        elif report['n_warn'] > 0 and alertas['severidad'] != 'critico':
            alertas['severidad'] = 'warn'
    except Exception:
        pass

    # Inconsistencias en conceptos
    try:
        from .models import ConceptoRemunerativo
        from .views_conceptos import detectar_inconsistencias
        n = 0
        for c in ConceptoRemunerativo.objects.filter(activo=True).only(
            'id', 'codigo', 'subtipo', 'tipo', 'afecto_essalud', 'afecto_afp',
            'afecto_onp', 'afecto_cts', 'afecto_gratif', 'afecto_vacaciones',
            'afecto_renta', 'codigo_plame', 'formula', 'monto_fijo', 'es_sistema',
        ):
            if detectar_inconsistencias(c):
                n += 1
        alertas['inconsistencias'] = n
        if n > 0:
            alertas['count'] += n
            if alertas['severidad'] == 'ok':
                alertas['severidad'] = 'warn'
    except Exception:
        pass

    # Sin PLAME (activos)
    try:
        from .models import ConceptoRemunerativo
        n = ConceptoRemunerativo.objects.filter(codigo_plame='', activo=True).count()
        alertas['sin_plame'] = n
        if n > 5:
            alertas['count'] += 1
            if alertas['severidad'] == 'ok':
                alertas['severidad'] = 'warn'
    except Exception:
        pass

    # Acuses pendientes (boletas APROBADO/CERRADO sin firma)
    try:
        from documentos.models import AcuseReciboBoleta
        from .models import RegistroNomina
        firmados = AcuseReciboBoleta.objects.values_list('registro_nomina_id', flat=True)
        n = RegistroNomina.objects.filter(
            periodo__estado__in=['APROBADO', 'CERRADO'],
        )
        if empresa is not None:
            n = n.filter(periodo__empresa=empresa)
        n = n.exclude(pk__in=firmados).count()
        alertas['acuses_pendientes'] = n
        if n > 0:
            alertas['count'] += n
            if alertas['severidad'] == 'ok':
                alertas['severidad'] = 'warn'
    except Exception:
        pass

    return alertas


def nominas_alerts(request):
    """Inyecta `nominas_alerts` solo si el usuario es admin."""
    user = getattr(request, 'user', None)
    if not (user and user.is_authenticated and user.is_superuser):
        return {}

    empresa = getattr(request, 'empresa_actual', None)
    key = f'nominas_alerts:v2:{user.pk}:{getattr(empresa, "pk", "all")}'
    cached = cache.get(key)
    if cached is not None:
        return {'nominas_alerts': cached}

    alertas = _calcular_alertas(empresa)
    cache.set(key, alertas, _TTL_NOMINAS_ALERTS)
    return {'nominas_alerts': alertas}


def invalidar_nominas_alerts(user_pk=None):
    """Llamado por signals al cambiar conceptos. Si user_pk dado, invalida solo ese."""
    if user_pk is not None:
        cache.delete(f'nominas_alerts:v2:{user_pk}:all')
    else:
        # Borrado masivo — Django cache no soporta pattern delete portable.
        # En su lugar, el TTL de 5 min asegura refresh natural.
        pass
