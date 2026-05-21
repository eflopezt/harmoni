"""
Analytics — Vistas del Predictor de Rotación de Personal.

Panel y detalle por trabajador. Algoritmo en `analytics.predictor_rotacion`.
"""
from collections import Counter

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, render

from .predictor_rotacion import calcular_score_rotacion, top_personal_en_riesgo


def _es_staff(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff)


@login_required
@user_passes_test(_es_staff)
def predictor_rotacion_panel(request):
    """Panel principal del predictor — top trabajadores en riesgo + filtros."""
    nivel_filtro = (request.GET.get('nivel') or '').strip().upper()
    area_filtro = (request.GET.get('area') or '').strip()

    # Score >= 20 captura BAJO+; el template filtra después si se pide.
    en_riesgo = top_personal_en_riesgo(limit=50, min_score=20)

    if nivel_filtro in ('CRITICO', 'ALTO', 'MEDIO', 'BAJO'):
        en_riesgo = [r for r in en_riesgo if r['analisis']['nivel'] == nivel_filtro]

    if area_filtro:
        try:
            area_id = int(area_filtro)
            en_riesgo = [
                r for r in en_riesgo
                if r['personal'].subarea and r['personal'].subarea.area_id == area_id
            ]
        except (TypeError, ValueError):
            pass

    # Stats
    total = len(en_riesgo)
    criticos = sum(1 for r in en_riesgo if r['analisis']['nivel'] == 'CRITICO')
    altos = sum(1 for r in en_riesgo if r['analisis']['nivel'] == 'ALTO')
    medios = sum(1 for r in en_riesgo if r['analisis']['nivel'] == 'MEDIO')
    bajos = sum(1 for r in en_riesgo if r['analisis']['nivel'] == 'BAJO')

    # Top factores recurrentes
    factores_counter: Counter = Counter()
    for r in en_riesgo:
        for f in r['analisis']['factores']:
            factores_counter[f.nombre] += 1
    top_factores = factores_counter.most_common(8)

    # Áreas para filtro
    try:
        from personal.models import Area
        areas = Area.objects.filter(activa=True).order_by('nombre')
    except Exception:
        areas = []

    context = {
        'titulo': 'Predictor de Rotación',
        'en_riesgo': en_riesgo,
        'total': total,
        'criticos': criticos,
        'altos': altos,
        'medios': medios,
        'bajos': bajos,
        'top_factores': top_factores,
        'areas': areas,
        'filtro_nivel': nivel_filtro,
        'filtro_area': area_filtro,
    }
    return render(request, 'analytics/predictor_rotacion.html', context)


@login_required
@user_passes_test(_es_staff)
def predictor_rotacion_detalle(request, pk):
    """Detalle del análisis para un trabajador específico."""
    from personal.models import Personal

    personal = get_object_or_404(Personal, pk=pk)
    analisis = calcular_score_rotacion(personal)

    return render(request, 'analytics/predictor_rotacion_detalle.html', {
        'titulo': f'Análisis de Rotación — {personal.apellidos_nombres}',
        'personal': personal,
        'analisis': analisis,
    })
