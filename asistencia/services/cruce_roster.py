"""
Cruce Tareo ↔ Roster (Fase 2) + validación de topes de jornada.

Dos funciones del régimen atípico/acumulativo (14x7, 21x7) que faltaba conectar:

1. **Cruce**: compara la asistencia REAL (RegistroTareo) con la programación
   PROYECTADA (Roster) por persona-fecha y puebla `CruceTareoRoster` con el tipo
   de variación (coincide, trabajó sin roster, ausente proyectado, etc.).

2. **Topes de jornada**: en jornada acumulativa el promedio de horas del ciclo
   no puede exceder 8 h/día ni 48 h/semana (Art. 9 D.S. 007-2002-TR). Aquí se
   calcula el promedio y se marca si excede.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

# Categorías de código (reutiliza la taxonomía del roster).
_ROSTER_TRABAJO   = {'T', 'TR'}
_ROSTER_DESCANSO  = {'D', 'DS', 'DL', 'DLA', 'DOL'}
_ROSTER_FALTA     = {'F', 'S'}
_ROSTER_VACACIONES = {'V'}
_ROSTER_LICENCIA  = {'L', 'P', 'DM', 'FC'}

# Códigos de RegistroTareo.codigo_dia (marcación real ya procesada).
_TAREO_TRABAJO    = {'A', 'NOR', 'T', 'TR', 'CHE'}
_TAREO_DESCANSO   = {'DL', 'DS', 'DLA', 'D'}
_TAREO_FALTA      = {'F', 'FL', 'FA', 'FI'}
_TAREO_VACACIONES = {'VAC', 'V'}
_TAREO_LICENCIA   = {'L', 'DM', 'P'}


def _cat(codigo: str, trabajo, descanso, falta, vacaciones, licencia) -> str:
    c = (codigo or '').strip().upper()
    if c in trabajo:    return 'trabajo'
    if c in descanso:   return 'descanso'
    if c in falta:      return 'falta'
    if c in vacaciones: return 'vacaciones'
    if c in licencia:   return 'licencia'
    return 'otro'


def categoria_roster(codigo: str) -> str:
    return _cat(codigo, _ROSTER_TRABAJO, _ROSTER_DESCANSO, _ROSTER_FALTA,
                _ROSTER_VACACIONES, _ROSTER_LICENCIA)


def categoria_tareo(codigo_dia: str) -> str:
    return _cat(codigo_dia, _TAREO_TRABAJO, _TAREO_DESCANSO, _TAREO_FALTA,
                _TAREO_VACACIONES, _TAREO_LICENCIA)


def clasificar_variacion(cat_tareo: str, cat_roster: str | None) -> str:
    """Devuelve el código de `CruceTareoRoster.VARIACION`."""
    if cat_roster is None:
        return 'NO_EN_ROSTER'          # marcó asistencia sin estar programado
    if cat_tareo == cat_roster:
        return 'COINCIDE'
    if cat_roster == 'descanso' and cat_tareo == 'trabajo':
        return 'TRABAJO_SIN_ROSTER'
    if cat_roster == 'trabajo' and cat_tareo == 'falta':
        return 'AUSENTE_PROYECTADO'
    if cat_roster == 'trabajo' and cat_tareo in ('licencia', 'vacaciones'):
        return 'LICENCIA_NO_PROYECTADA'
    if cat_tareo == 'falta':
        return 'FALTA_NO_PROYECTADA'
    if cat_roster == 'descanso' and cat_tareo == 'trabajo':
        return 'DL_POSTERGADO'
    return 'COINCIDE'


def poblar_cruce(fecha_inicio, fecha_fin, *, guardar=True) -> dict:
    """Puebla CruceTareoRoster para los RegistroTareo del rango.

    Returns: dict con conteos por tipo de variación.
    """
    from asistencia.models import RegistroTareo, CruceTareoRoster
    from personal.models import Roster

    tareos = (
        RegistroTareo.objects
        .filter(fecha__gte=fecha_inicio, fecha__lte=fecha_fin, personal__isnull=False)
        .select_related('personal')
    )
    # Índice de roster por (personal_id, fecha)
    rosters = Roster.objects.filter(fecha__gte=fecha_inicio, fecha__lte=fecha_fin)
    ridx = {(r.personal_id, r.fecha): r for r in rosters}

    conteo: dict[str, int] = {}
    for t in tareos:
        r = ridx.get((t.personal_id, t.fecha))
        cat_t = categoria_tareo(t.codigo_dia)
        cat_r = categoria_roster(r.codigo) if r else None
        variacion = clasificar_variacion(cat_t, cat_r)
        conteo[variacion] = conteo.get(variacion, 0) + 1
        if guardar:
            CruceTareoRoster.objects.update_or_create(
                registro_tareo=t,
                defaults=dict(
                    roster_codigo=(r.codigo if r else ''),
                    roster_id=(r.pk if r else None),
                    variacion=variacion,
                    detalle_variacion=f'tareo={t.codigo_dia} vs roster={(r.codigo if r else "—")}',
                ),
            )
    return conteo


# ── Topes de jornada acumulativa ───────────────────────────────────

def _r(v) -> Decimal:
    return Decimal(v).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def promedio_jornada(horas_totales, dias_ciclo) -> Decimal:
    """Promedio de horas por día del ciclo (incluye días de descanso)."""
    if not dias_ciclo:
        return Decimal('0')
    return _r(Decimal(str(horas_totales)) / Decimal(str(dias_ciclo)))


def excede_tope(horas_totales, dias_ciclo, tope_diario=Decimal('8')) -> bool:
    """True si el promedio diario del ciclo excede el tope legal (8 h/día).

    Equivale a > 48 h/semana promedio (Art. 9 D.S. 007-2002-TR).
    """
    return promedio_jornada(horas_totales, dias_ciclo) > Decimal(str(tope_diario))


def validar_jornada_personal(personal, fecha_inicio, fecha_fin) -> dict:
    """Suma las horas efectivas del Tareo en el rango y calcula el promedio del
    ciclo, marcando si excede el tope legal."""
    from asistencia.models import RegistroTareo
    from django.db.models import Sum

    agg = (
        RegistroTareo.objects
        .filter(personal=personal, fecha__gte=fecha_inicio, fecha__lte=fecha_fin)
        .aggregate(h=Sum('horas_efectivas'))
    )
    horas = agg['h'] or Decimal('0')
    dias = (fecha_fin - fecha_inicio).days + 1
    prom = promedio_jornada(horas, dias)
    return {
        'horas_totales':   _r(horas),
        'dias_ciclo':      dias,
        'promedio_diario': prom,
        'excede':          prom > Decimal('8'),
        'tope_diario':     Decimal('8'),
    }
