"""
Detector de Anomalías en Planilla.

Compara el período actual contra el anterior y detecta variaciones
sospechosas que requieren revisión antes de aprobar:

- Neto subió/bajó > 30% sin explicación
- Trabajador NUEVO en este período (alta)
- Trabajador FALTANTE respecto al mes anterior (cese?)
- Sueldo básico cambió sin trazabilidad
- Descuentos atípicos (>50% del bruto)

URL: /nominas/anomalias/<periodo_pk>/
"""
from decimal import Decimal

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, render

solo_admin = user_passes_test(lambda u: u.is_superuser)


# ── Thresholds ────────────────────────────────────────────────
PCT_CAMBIO_NETO_SIGNIFICATIVO = Decimal('30.00')    # >30% cambio = alerta
PCT_DESCUENTO_ATIPICO         = Decimal('50.00')    # >50% bruto descontado = alerta
PCT_AUMENTO_SUELDO_BASE       = Decimal('15.00')    # >15% aumento básico = alerta


def _pct_cambio(antes: Decimal, despues: Decimal) -> Decimal:
    if not antes or antes == 0:
        return Decimal('100') if despues > 0 else Decimal('0')
    return (despues - antes) / antes * Decimal('100')


def detectar_anomalias_periodo(periodo):
    """
    Para un período dado, compara contra el período anterior (mismo tipo)
    y devuelve lista de anomalías estructuradas.

    Returns: lista de dicts {tipo, severidad, registro, mensaje, ...}
    """
    from .models import PeriodoNomina, RegistroNomina

    # Período anterior (mismo tipo, mes anterior)
    anterior = None
    mes_ant = periodo.mes - 1
    anio_ant = periodo.anio
    if mes_ant <= 0:
        mes_ant = 12
        anio_ant -= 1
    anterior = PeriodoNomina.objects.filter(
        tipo=periodo.tipo, anio=anio_ant, mes=mes_ant,
        estado__in=['CALCULADO', 'APROBADO', 'CERRADO'],
    ).first()

    anomalias = []

    # Index registros actuales y anteriores por personal_id
    actuales = {r.personal_id: r for r in periodo.registros.select_related('personal').all()}
    anteriores = {}
    if anterior:
        anteriores = {r.personal_id: r for r in anterior.registros.select_related('personal').all()}

    # ── 1. Nuevos trabajadores (no estaban en el anterior) ──
    if anterior:
        nuevos = set(actuales.keys()) - set(anteriores.keys())
        for pid in nuevos:
            r = actuales[pid]
            anomalias.append({
                'tipo':       'NUEVO',
                'severidad':  'info',
                'icon':       'fas fa-user-plus',
                'color':      '#1d4ed8',
                'registro':   r,
                'mensaje':    f'Nuevo en planilla este mes — neto S/ {r.neto_a_pagar:,.2f}',
                'delta':      None,
            })

        # ── 2. Trabajadores faltantes (estaban pero ya no) ──
        faltantes = set(anteriores.keys()) - set(actuales.keys())
        for pid in faltantes:
            r_ant = anteriores[pid]
            anomalias.append({
                'tipo':       'FALTANTE',
                'severidad':  'warn',
                'icon':       'fas fa-user-minus',
                'color':      '#d97706',
                'registro':   r_ant,
                'mensaje':    f'Estaba el mes anterior con neto S/ {r_ant.neto_a_pagar:,.2f} — ¿cesado o liquidado?',
                'delta':      None,
            })

    # ── 3. Cambios significativos en neto ──
    for pid, r_act in actuales.items():
        r_ant = anteriores.get(pid)
        if not r_ant:
            continue
        neto_act = r_act.neto_a_pagar or Decimal('0')
        neto_ant = r_ant.neto_a_pagar or Decimal('0')
        pct = _pct_cambio(neto_ant, neto_act)
        if abs(pct) >= PCT_CAMBIO_NETO_SIGNIFICATIVO:
            delta = neto_act - neto_ant
            anomalias.append({
                'tipo':       'NETO_CAMBIO',
                'severidad':  'critico' if abs(pct) >= 50 else 'warn',
                'icon':       'fas fa-chart-line' if pct > 0 else 'fas fa-chart-line',
                'color':      '#15803d' if pct > 0 else '#dc2626',
                'registro':   r_act,
                'mensaje':    f'Neto cambió {pct:+.1f}% ({"+" if delta > 0 else ""}S/ {delta:,.2f}) vs mes anterior',
                'delta':      delta,
                'pct':        pct,
            })

    # ── 4. Descuentos atípicos ──
    for pid, r_act in actuales.items():
        bruto = r_act.total_ingresos or Decimal('0')
        descuentos = r_act.total_descuentos or Decimal('0')
        if bruto > 0:
            pct_desc = descuentos / bruto * Decimal('100')
            if pct_desc >= PCT_DESCUENTO_ATIPICO:
                anomalias.append({
                    'tipo':       'DESCUENTOS_ATIPICOS',
                    'severidad':  'warn',
                    'icon':       'fas fa-exclamation-triangle',
                    'color':      '#dc2626',
                    'registro':   r_act,
                    'mensaje':    f'Descuentos = {pct_desc:.1f}% del bruto (S/ {descuentos:,.2f} de S/ {bruto:,.2f})',
                    'pct':        pct_desc,
                })

    # ── 5. Cambios en sueldo básico ──
    for pid, r_act in actuales.items():
        r_ant = anteriores.get(pid)
        if not r_ant:
            continue
        sb_act = r_act.sueldo_base or Decimal('0')
        sb_ant = r_ant.sueldo_base or Decimal('0')
        pct = _pct_cambio(sb_ant, sb_act)
        if abs(pct) >= PCT_AUMENTO_SUELDO_BASE:
            delta = sb_act - sb_ant
            anomalias.append({
                'tipo':       'SUELDO_BASE_CAMBIO',
                'severidad':  'warn',
                'icon':       'fas fa-dollar-sign',
                'color':      '#0369a1',
                'registro':   r_act,
                'mensaje':    f'Sueldo básico cambió {pct:+.1f}% (S/ {sb_ant:,.2f} → S/ {sb_act:,.2f})',
                'delta':      delta,
                'pct':        pct,
            })

    # Ordenar por severidad
    sev_order = {'critico': 0, 'warn': 1, 'info': 2}
    anomalias.sort(key=lambda a: (sev_order.get(a['severidad'], 99), -abs(a.get('pct') or 0)))

    return {
        'anomalias':   anomalias,
        'anterior':    anterior,
        'total_act':   len(actuales),
        'total_ant':   len(anteriores),
        'criticos':    sum(1 for a in anomalias if a['severidad'] == 'critico'),
        'warns':       sum(1 for a in anomalias if a['severidad'] == 'warn'),
        'infos':       sum(1 for a in anomalias if a['severidad'] == 'info'),
    }


@login_required
@solo_admin
def anomalias_periodo(request, pk):
    """Detector de anomalías de un período específico."""
    from .models import PeriodoNomina

    periodo = get_object_or_404(PeriodoNomina, pk=pk)
    report = detectar_anomalias_periodo(periodo)

    return render(request, 'nominas/anomalias.html', {
        'periodo':   periodo,
        **report,
    })
