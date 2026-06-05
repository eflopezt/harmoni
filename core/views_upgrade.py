"""
Vista pública /upgrade/ — muestra los planes y el plan actual de la empresa.
Los planes derivan de core/planes.py (fuente única) vía views_precios.
"""
from django.shortcuts import render


def upgrade_plan(request):
    """Página de upgrade — muestra los 4 planes con features incluidas."""
    from core.planes import PLANES as _PLANES, PLAN_DEFAULT
    from core.views_precios import PLANES as _CARDS

    # Plan actual real de la empresa del user.
    plan_actual = _PLANES[PLAN_DEFAULT]['nombre']
    if request.user.is_authenticated:
        try:
            from core.middleware_plan_starter import resolve_plan
            code = resolve_plan(request.user)
            plan_actual = _PLANES.get(code, _PLANES[PLAN_DEFAULT])['nombre']
        except Exception:
            pass

    # Reusar las tarjetas de /precios/ con el precio formateado como string.
    planes = []
    for c in _CARDS:
        planes.append({
            **c,
            'precio': c['precio_label'] or f"S/ {c['precio']}",
            'colaboradores': c['colaboradores'].capitalize(),
        })

    return render(request, 'upgrade_plan.html', {
        'plan_actual': plan_actual,
        'planes':      planes,
    })
