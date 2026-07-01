"""
Control Tower del ciclo de vida del empleado.

Una sola pantalla que muestra en qué etapa está cada empleado
(Contratado -> Onboarding -> Activo -> En cese -> Cerrado), cuántos hay
por etapa y qué bloquea/qué sigue en cada uno. La etapa se DERIVA de datos
existentes (ver personal/ciclo.py y Personal.etapa_ciclo); aquí se batchean
las señales para evitar N+1.
"""
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import render

from ..models import Personal, Contrato
from ..permissions import filtrar_personal_por_request
from ..ciclo import ETAPAS_ORDEN, etapa_info


def _detalle_etapa(p, etapa, onb_pct, dias_venc):
    """Texto corto de 'qué lo bloquea / qué sigue' para cada empleado."""
    if etapa == 'contratado':
        return 'Falta contrato vigente o activación'
    if etapa == 'onboarding':
        return f'Onboarding {onb_pct}% completado'
    if etapa == 'activo':
        if dias_venc is not None and 0 <= dias_venc <= 30:
            return f'Contrato vence en {dias_venc} d'
        if dias_venc is not None and dias_venc < 0:
            return 'Contrato VENCIDO'
        return 'En operación'
    if etapa == 'cese':
        return 'Liquidación pendiente'
    if etapa == 'cerrado':
        return 'Cerrado'
    return ''


@login_required
def control_tower(request):
    etapa_filtro = (request.GET.get('etapa') or '').strip()
    area_id = (request.GET.get('area') or '').strip()
    buscar = (request.GET.get('buscar') or '').strip()

    qs = filtrar_personal_por_request(request).select_related(
        'subarea', 'subarea__area', 'empresa'
    )
    if area_id:
        qs = qs.filter(subarea_id=area_id)
    if buscar:
        qs = qs.filter(
            Q(apellidos_nombres__icontains=buscar) | Q(nro_doc__icontains=buscar)
        )
    qs = qs.order_by('apellidos_nombres')

    personas = list(qs)
    ids = [p.id for p in personas]

    # ── Señales batcheadas (evita N+1) ──
    con_contrato = set(
        Contrato.objects.filter(personal_id__in=ids, estado='VIGENTE')
        .values_list('personal_id', flat=True)
    )
    onb_en_curso = {}
    try:
        from onboarding.models import ProcesoOnboarding
        for pr in ProcesoOnboarding.objects.filter(
            personal_id__in=ids, estado='EN_CURSO'
        ):
            onb_en_curso[pr.personal_id] = pr
    except Exception:
        pass
    liq_cerrada = set()
    try:
        from nominas.models import LiquidacionLaboral
        liq_cerrada = set(
            LiquidacionLaboral.objects.filter(
                personal_id__in=ids, estado__in=['PAGADA', 'CERRADA']
            ).values_list('personal_id', flat=True)
        )
    except Exception:
        pass

    def etapa_de(p):
        estado = (p.estado or '').strip()
        if estado == 'Cesado':
            return 'cerrado' if p.id in liq_cerrada else 'cese'
        if p.id in onb_en_curso:
            return 'onboarding'
        if estado == 'Inactivo' or p.id not in con_contrato:
            return 'contratado'
        return 'activo'

    # ── Construir filas + contar por etapa ──
    conteo = {code: 0 for code in ETAPAS_ORDEN}
    filas = []
    for p in personas:
        etapa = etapa_de(p)
        conteo[etapa] = conteo.get(etapa, 0) + 1
        proc = onb_en_curso.get(p.id)
        onb_pct = int(getattr(proc, 'porcentaje_avance', 0) or 0) if proc else 0
        dias_venc = p.dias_para_vencimiento_contrato
        if etapa_filtro and etapa != etapa_filtro:
            continue
        filas.append({
            'p': p,
            'etapa': etapa_info(etapa),
            'detalle': _detalle_etapa(p, etapa, onb_pct, dias_venc),
            'onb_pct': onb_pct,
            'dias_venc': dias_venc,
        })

    # ── Candidatos activos (funnel de reclutamiento) ──
    candidatos = 0
    try:
        from reclutamiento.models import Postulacion
        candidatos = Postulacion.objects.filter(estado='ACTIVA').count()
    except Exception:
        pass

    tarjetas = [
        {**etapa_info(code), 'total': conteo.get(code, 0)}
        for code in ETAPAS_ORDEN if code != 'candidato'
    ]

    from ..permissions import filtrar_subareas
    try:
        areas = filtrar_subareas(request.user).select_related('área')
    except Exception:
        areas = []

    context = {
        'filas': filas,
        'tarjetas': tarjetas,
        'candidatos': candidatos,
        'total': len(personas),
        'etapa_filtro': etapa_filtro,
        'area_id': area_id,
        'buscar': buscar,
        'areas': areas,
    }
    return render(request, 'personal/control_tower.html', context)
