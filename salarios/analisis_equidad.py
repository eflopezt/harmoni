"""
Motor de análisis de equidad salarial.

Calcula brechas de género, outliers respecto a bandas salariales, personal sin banda
asignada, y estadísticas distributivas (percentiles) sobre el personal activo.

Reglas:
- Personal usa el campo `sexo` ('M'/'F'), NO `genero`.
- `sueldo_base` puede ser None — se ignora en el análisis.
- Bandas: matching exacto por `cargo` (case-sensitive, trimmed) + banda activa.
- Aritmética con Decimal para evitar pérdida de precisión en moneda.
"""
from collections import defaultdict
from decimal import Decimal
import statistics
from typing import Any

from personal.models import Personal
from .models import BandaSalarial


# ──────────────────────────────────────────────────────────────────────────────
# Helpers internos
# ──────────────────────────────────────────────────────────────────────────────
def _to_decimal(val) -> Decimal:
    """Convierte float/int a Decimal de forma segura."""
    if val is None:
        return Decimal('0')
    if isinstance(val, Decimal):
        return val
    return Decimal(str(val))


def _percentile(sorted_vals: list[float], pct: float) -> float:
    """Percentil simple (linear interpolation). pct en [0, 100]."""
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return float(sorted_vals[0])
    k = (len(sorted_vals) - 1) * (pct / 100.0)
    f_idx = int(k)
    c_idx = min(f_idx + 1, len(sorted_vals) - 1)
    if f_idx == c_idx:
        return float(sorted_vals[f_idx])
    d0 = sorted_vals[f_idx] * (c_idx - k)
    d1 = sorted_vals[c_idx] * (k - f_idx)
    return float(d0 + d1)


def _get_sexo(empleado) -> str:
    """Obtiene el código de sexo. Maneja Personal con/sin campo `sexo`."""
    return (getattr(empleado, 'sexo', '') or '').strip().upper()


def _get_cargo(empleado) -> str:
    """Obtiene cargo trimmed. Empty string si falta."""
    return (getattr(empleado, 'cargo', '') or '').strip()


def _bandas_index() -> dict[str, BandaSalarial]:
    """Index de bandas activas por cargo (priorizando midpoint si hay duplicados)."""
    index: dict[str, BandaSalarial] = {}
    for b in BandaSalarial.objects.filter(activa=True):
        key = (b.cargo or '').strip()
        if not key:
            continue
        # Si existen múltiples bandas por cargo (varios niveles),
        # nos quedamos con la primera encontrada — el caller puede luego
        # cruzar con el nivel específico si lo necesita.
        if key not in index:
            index[key] = b
    return index


# ──────────────────────────────────────────────────────────────────────────────
# Motor principal
# ──────────────────────────────────────────────────────────────────────────────
def analizar_equidad_salarial(area_id: int | None = None,
                              grupo_tareo: str | None = None) -> dict[str, Any]:
    """
    Analiza la equidad salarial sobre el personal activo.

    Args:
        area_id: filtra por subarea__area_id si se proporciona.
        grupo_tareo: filtra por grupo_tareo si se proporciona.

    Returns:
        dict con:
          - gap_genero: {'M': avg, 'F': avg, 'gap_pct': float, 'n_m', 'n_f'}
          - por_area: [{'area', 'avg_m', 'avg_f', 'gap_pct', 'n_m', 'n_f'}, ...]
          - outliers_alto: [{'personal', 'sueldo', 'banda', 'exceso'}, ...]
          - outliers_bajo: [{'personal', 'sueldo', 'banda', 'deficit'}, ...]
          - sin_banda: [{'personal', 'sueldo', 'cargo'}, ...]
          - distribucion_bandas: {'p25_below': int, 'p25_p50': int, 'p50_p75': int, 'p75_above': int}
          - stats_generales: {avg_sueldo, median, p25, p75, total_planilla, n}
    """
    qs = Personal.objects.filter(
        estado='Activo',
        sueldo_base__isnull=False,
        sueldo_base__gt=0,
    ).select_related('subarea__area')

    if area_id:
        try:
            qs = qs.filter(subarea__area_id=int(area_id))
        except (ValueError, TypeError):
            pass
    if grupo_tareo:
        qs = qs.filter(grupo_tareo=grupo_tareo)

    empleados = list(qs)
    bandas_idx = _bandas_index()

    # ── Stats generales ───────────────────────────────────────
    sueldos = [float(e.sueldo_base) for e in empleados]
    sueldos_sorted = sorted(sueldos)
    n_total = len(sueldos)

    if n_total > 0:
        avg = round(sum(sueldos) / n_total, 2)
        median = round(statistics.median(sueldos), 2)
        p25 = round(_percentile(sueldos_sorted, 25), 2)
        p75 = round(_percentile(sueldos_sorted, 75), 2)
        total_planilla = round(sum(sueldos), 2)
    else:
        avg = median = p25 = p75 = 0.0
        total_planilla = 0.0

    stats_generales = {
        'avg_sueldo': avg,
        'median': median,
        'p25': p25,
        'p75': p75,
        'total_planilla': total_planilla,
        'n': n_total,
    }

    # ── Gap de género global ───────────────────────────────────
    sueldos_m = [float(e.sueldo_base) for e in empleados if _get_sexo(e) == 'M']
    sueldos_f = [float(e.sueldo_base) for e in empleados if _get_sexo(e) == 'F']
    avg_m = round(sum(sueldos_m) / len(sueldos_m), 2) if sueldos_m else 0.0
    avg_f = round(sum(sueldos_f) / len(sueldos_f), 2) if sueldos_f else 0.0
    gap_pct = None
    if avg_m > 0 and sueldos_f and sueldos_m:
        gap_pct = round((avg_m - avg_f) / avg_m * 100, 2)

    gap_genero = {
        'M': avg_m,
        'F': avg_f,
        'gap_pct': gap_pct,
        'n_m': len(sueldos_m),
        'n_f': len(sueldos_f),
    }

    # ── Por área ───────────────────────────────────────────────
    area_data: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {'M': [], 'F': [], 'todos': []}
    )
    for e in empleados:
        area_nombre = (
            e.subarea.area.nombre
            if e.subarea and getattr(e.subarea, 'area', None)
            else 'Sin área'
        )
        s_val = float(e.sueldo_base)
        area_data[area_nombre]['todos'].append(s_val)
        sx = _get_sexo(e)
        if sx == 'M':
            area_data[area_nombre]['M'].append(s_val)
        elif sx == 'F':
            area_data[area_nombre]['F'].append(s_val)

    por_area = []
    for area_n in sorted(area_data.keys()):
        d = area_data[area_n]
        prom_m_a = round(sum(d['M']) / len(d['M']), 2) if d['M'] else None
        prom_f_a = round(sum(d['F']) / len(d['F']), 2) if d['F'] else None
        gap_a = None
        if prom_m_a and prom_f_a and prom_m_a > 0:
            gap_a = round((prom_m_a - prom_f_a) / prom_m_a * 100, 2)
        por_area.append({
            'area': area_n,
            'avg_m': prom_m_a,
            'avg_f': prom_f_a,
            'gap_pct': gap_a,
            'n_m': len(d['M']),
            'n_f': len(d['F']),
            'n_total': len(d['todos']),
        })

    # ── Outliers vs banda ──────────────────────────────────────
    outliers_alto: list[dict] = []
    outliers_bajo: list[dict] = []
    sin_banda: list[dict] = []

    for e in empleados:
        cargo = _get_cargo(e)
        sueldo = _to_decimal(e.sueldo_base)
        banda = bandas_idx.get(cargo) if cargo else None

        if not banda:
            sin_banda.append({
                'personal': e,
                'sueldo': sueldo,
                'cargo': cargo or '(sin cargo)',
            })
            continue

        if sueldo > banda.maximo:
            outliers_alto.append({
                'personal': e,
                'sueldo': sueldo,
                'banda': banda,
                'exceso': sueldo - banda.maximo,
                'exceso_pct': round(
                    (sueldo - banda.maximo) / banda.maximo * 100, 2
                ) if banda.maximo > 0 else Decimal('0'),
            })
        elif sueldo < banda.minimo:
            outliers_bajo.append({
                'personal': e,
                'sueldo': sueldo,
                'banda': banda,
                'deficit': banda.minimo - sueldo,
                'deficit_pct': round(
                    (banda.minimo - sueldo) / banda.minimo * 100, 2
                ) if banda.minimo > 0 else Decimal('0'),
            })

    # Orden: mayor desviación primero
    outliers_alto.sort(key=lambda x: x['exceso'], reverse=True)
    outliers_bajo.sort(key=lambda x: x['deficit'], reverse=True)
    sin_banda.sort(key=lambda x: x['sueldo'], reverse=True)

    # ── Distribución por percentiles ───────────────────────────
    distribucion = {
        'p25_below': 0,
        'p25_p50': 0,
        'p50_p75': 0,
        'p75_above': 0,
    }
    for s in sueldos:
        if s < p25:
            distribucion['p25_below'] += 1
        elif s < median:
            distribucion['p25_p50'] += 1
        elif s < p75:
            distribucion['p50_p75'] += 1
        else:
            distribucion['p75_above'] += 1

    return {
        'gap_genero': gap_genero,
        'por_area': por_area,
        'outliers_alto': outliers_alto,
        'outliers_bajo': outliers_bajo,
        'sin_banda': sin_banda,
        'distribucion_bandas': distribucion,
        'stats_generales': stats_generales,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Simulador de ajuste — calcula impacto de alinear outliers_bajo a un objetivo
# ──────────────────────────────────────────────────────────────────────────────
def simular_ajuste_outliers(objetivo: str = 'mediana') -> dict[str, Any]:
    """
    Simula el ajuste salarial de los outliers_bajo al objetivo elegido.

    Args:
        objetivo: 'minimo' (banda.minimo), 'mediana' (banda.medio) o 'maximo' (banda.maximo).

    Returns:
        dict con:
          - propuestas: [{'personal', 'sueldo_actual', 'sueldo_nuevo', 'incremento',
                          'incremento_pct', 'banda'}, ...]
          - impacto: {'incremento_mensual_total', 'incremento_anual_total',
                      'planilla_actual', 'planilla_nueva',
                      'incremento_pct_planilla', 'n_afectados'}
    """
    if objetivo not in ('minimo', 'mediana', 'maximo'):
        objetivo = 'mediana'

    analisis = analizar_equidad_salarial()
    outliers = analisis['outliers_bajo']

    propuestas = []
    incremento_total = Decimal('0')

    for o in outliers:
        banda: BandaSalarial = o['banda']
        if objetivo == 'minimo':
            sueldo_nuevo = banda.minimo
        elif objetivo == 'maximo':
            sueldo_nuevo = banda.maximo
        else:
            sueldo_nuevo = banda.medio

        sueldo_actual = o['sueldo']
        incremento = sueldo_nuevo - sueldo_actual
        if incremento < 0:
            # Si por alguna razón el sueldo actual ya está por encima del objetivo,
            # no proponemos reducirlo (no bajamos sueldos como parte del ajuste).
            continue

        incremento_pct = (
            round(incremento / sueldo_actual * 100, 2)
            if sueldo_actual > 0 else Decimal('0')
        )
        propuestas.append({
            'personal': o['personal'],
            'sueldo_actual': sueldo_actual,
            'sueldo_nuevo': sueldo_nuevo,
            'incremento': incremento,
            'incremento_pct': incremento_pct,
            'banda': banda,
        })
        incremento_total += incremento

    planilla_actual = _to_decimal(analisis['stats_generales']['total_planilla'])
    planilla_nueva = planilla_actual + incremento_total

    pct_planilla = Decimal('0')
    if planilla_actual > 0:
        pct_planilla = round(incremento_total / planilla_actual * 100, 2)

    impacto = {
        'incremento_mensual_total': incremento_total,
        'incremento_anual_total': incremento_total * 12,
        'planilla_actual': planilla_actual,
        'planilla_nueva': planilla_nueva,
        'incremento_pct_planilla': pct_planilla,
        'n_afectados': len(propuestas),
    }

    return {
        'propuestas': propuestas,
        'impacto': impacto,
        'objetivo': objetivo,
    }
