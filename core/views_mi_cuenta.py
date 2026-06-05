"""
Dashboard "Mi Cuenta" — visualización del plan actual + uso.

URL: /cuenta/plan/

Muestra al admin de la empresa:
- Plan vigente con CTAs
- Trabajadores: barra de progreso (X / cap)
- Periodos cerrados (estadística)
- Storage estimado (boletas + documentos)
- Próximo pago (si está en Suscripcion)
- CTA upgrade contextual
"""
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.shortcuts import render
from django.views.decorators.cache import never_cache


# Derivado de core/planes.py (4 planes por módulos) + estética por plan.
from core.planes import PLANES as _PLANES, PLAN_DEFAULT

_PLAN_ESTILO = {
    'ASISTENCIA': {'color': '#0891b2', 'icon': 'fa-clock'},
    'PLANILLA':   {'color': '#0f766e', 'icon': 'fa-calculator'},
    'TALENTO':    {'color': '#7c3aed', 'icon': 'fa-people-group'},
    'SUITE':      {'color': '#0d2b27', 'icon': 'fa-crown'},
}
PLAN_INFO = {
    code: {
        'nombre':         meta['nombre'],
        'precio_mensual': meta['precio'],
        'cap_workers':    meta['max_trab'],
        'color':          _PLAN_ESTILO.get(code, {}).get('color', '#0f766e'),
        'icon':           _PLAN_ESTILO.get(code, {}).get('icon', 'fa-rocket'),
    }
    for code, meta in _PLANES.items()
}


@login_required
@never_cache  # Per-user dashboard — no cachear página, pero sí los KPIs
def mi_cuenta_plan(request):
    """Dashboard visual del plan vigente.

    Optimizaciones:
    - Cache de KPIs por empresa (TTL 5 min) — invalidado al cambiar plan o workers
    - select_related en Personal → Empresa
    - count() en lugar de cargar querysets
    """
    user = request.user

    # Resolver empresa con select_related (1 query en vez de 2)
    empresa = None
    try:
        personal = getattr(user, 'personal', None)
        if personal:
            # Usar select_related para evitar query extra a empresa
            personal_full = type(personal).objects.select_related('empresa').get(pk=personal.pk)
            empresa = personal_full.empresa
    except Exception:
        pass

    plan_code = empresa.plan if empresa else PLAN_DEFAULT
    plan_info = PLAN_INFO.get(plan_code, PLAN_INFO[PLAN_DEFAULT])

    # ── KPIs cacheados por empresa (5 min TTL) ──
    cache_key = f'micuenta_kpis:{empresa.pk}' if empresa else f'micuenta_kpis_user:{user.pk}'
    kpis = cache.get(cache_key)
    if kpis is None:
        # Workers actuales
        workers_total = 0
        if empresa:
            try:
                from personal.models import Personal
                workers_total = Personal.objects.filter(
                    empresa=empresa, estado='Activo'
                ).count()
            except Exception:
                pass

        # Periodos generados
        periodos_count = 0
        if empresa:
            try:
                from nominas.models import PeriodoNomina
                periodos_count = PeriodoNomina.objects.filter(empresa=empresa).count()
            except Exception:
                pass

        # Boletas
        boletas_count = 0
        if empresa:
            try:
                from nominas.models import RegistroNomina
                boletas_count = RegistroNomina.objects.filter(
                    periodo__empresa=empresa,
                ).count()
            except Exception:
                pass

        kpis = {
            'workers_total':  workers_total,
            'periodos_count': periodos_count,
            'boletas_count':  boletas_count,
        }
        cache.set(cache_key, kpis, timeout=300)  # 5 min

    workers_total  = kpis['workers_total']
    periodos_count = kpis['periodos_count']
    boletas_count  = kpis['boletas_count']

    workers_pct = 0
    if plan_info['cap_workers']:
        workers_pct = int(workers_total / plan_info['cap_workers'] * 100)

    storage_mb = round(boletas_count * 0.08, 1)  # ~80KB por boleta PDF

    # (La suscripción se muestra desde los campos de Empresa — ver mi_plan.html.
    #  Se eliminó la lectura del modelo legacy Suscripcion, que estaba sin uso.)

    # Color de barra según uso
    if workers_pct >= 90:
        progress_color = '#dc2626'   # rojo
        progress_text  = 'cerca del límite'
    elif workers_pct >= 70:
        progress_color = '#f59e0b'   # naranja
        progress_text  = 'uso moderado'
    else:
        progress_color = '#10b981'   # verde
        progress_text  = 'amplio margen'

    return render(request, 'cuenta/mi_plan.html', {
        'empresa':         empresa,
        'plan_code':       plan_code,
        'plan_info':       plan_info,
        'workers_total':   workers_total,
        'workers_pct':     workers_pct,
        'periodos_count':  periodos_count,
        'boletas_count':   boletas_count,
        'storage_mb':      storage_mb,
        'progress_color':  progress_color,
        'progress_text':   progress_text,
    })
