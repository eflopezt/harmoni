"""
Enlace Roster / Tareo → Planilla.

Cierra la brecha detectada en el diseño: hasta ahora `RegistroNomina.dias_trabajados`
se cargaba manual (default 30) y el motor no leía el Roster. Este servicio
convierte la programación diaria (Roster) — o la asistencia real (Tareo) — en
los contadores que el motor de nómina consume, y expone la base de jornada para
horas extra en regímenes acumulativos (14x7, 21x7).

Funciones:
  - resumen_asistencia_roster(personal, ini, fin)  → dict con conteo por categoría
  - poblar_registro_desde_roster(registro, ...)     → setea dias_trabajados/descanso/falta
  - horas_extra_desde_tareo(personal, ini, fin)      → suma he_25/35/100 reales del Tareo
  - jornada_promedio_ciclo(regimen_turno)            → base de HHEE (jornada acumulativa)

Convenciones de día trabajado:
  - 'mensual'  (régimen general / minería): el sueldo cubre 30 días incluyendo
    descansos; los días trabajados remunerados = 30 − faltas.
  - 'jornal'   (construcción civil): se paga por día efectivamente trabajado;
    días trabajados = días con código T/TR (el dominical se paga aparte).
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

# Categorías de código de roster
# (personal.validators.RosterValidator.CODIGOS_VALIDOS:
#  T, TR, D, V, L, S, F, P, DM, DS, DL, DLA, DOL, FC)
CODIGOS_TRABAJO   = {'T', 'TR'}                      # trabajo presencial / remoto
CODIGOS_DESCANSO  = {'D', 'DS', 'DL', 'DLA', 'DOL'}  # descanso del ciclo / semanal / día libre
CODIGOS_FALTA     = {'F', 'S'}                        # falta injustificada / suspensión (sin goce)
CODIGOS_VACACIONES = {'V'}                            # vacaciones (remunerado, concepto aparte)
CODIGOS_LICENCIA  = {'L', 'P', 'DM', 'FC'}           # licencia / permiso / descanso médico / falta compensada


def resumen_asistencia_roster(personal, fecha_inicio, fecha_fin) -> dict:
    """Cuenta los días del Roster de `personal` en [fecha_inicio, fecha_fin] por categoría.

    Devuelve un dict con: dias_periodo, trabajados, descanso, falta, vacaciones,
    licencia, sin_registro y `codigos` (conteo crudo por código).
    """
    from personal.models import Roster

    codigos = (
        Roster.objects
        .filter(personal=personal, fecha__gte=fecha_inicio, fecha__lte=fecha_fin)
        .values_list('codigo', flat=True)
    )
    conteo: dict[str, int] = {}
    for c in codigos:
        k = (c or '').strip().upper()
        if k:
            conteo[k] = conteo.get(k, 0) + 1

    def _suma(cods):
        return sum(v for k, v in conteo.items() if k in cods)

    dias_periodo = (fecha_fin - fecha_inicio).days + 1
    trabajados = _suma(CODIGOS_TRABAJO)
    descanso   = _suma(CODIGOS_DESCANSO)
    falta      = _suma(CODIGOS_FALTA)
    vacaciones = _suma(CODIGOS_VACACIONES)
    licencia   = _suma(CODIGOS_LICENCIA)
    con_registro = trabajados + descanso + falta + vacaciones + licencia

    return {
        'dias_periodo': dias_periodo,
        'trabajados':   trabajados,
        'descanso':     descanso,
        'falta':        falta,
        'vacaciones':   vacaciones,
        'licencia':     licencia,
        'sin_registro': max(0, dias_periodo - con_registro),
        'codigos':      conteo,
    }


def poblar_registro_desde_roster(registro, *, convencion='mensual', dias_base=30, guardar=False) -> dict:
    """Puebla `registro.dias_trabajados/dias_descanso/dias_falta` desde el Roster.

    Args:
        registro: RegistroNomina (usa registro.periodo.fecha_inicio/fecha_fin y registro.personal).
        convencion: 'mensual' (general/minería) o 'jornal' (construcción).
        dias_base: base del régimen mensual (30 por convención peruana de planilla).
        guardar: si True, hace save(update_fields=...).

    Returns:
        El dict de `resumen_asistencia_roster` (para trazabilidad).
    """
    periodo = registro.periodo
    resumen = resumen_asistencia_roster(
        registro.personal, periodo.fecha_inicio, periodo.fecha_fin,
    )
    falta = resumen['falta']

    if convencion == 'jornal':
        # Construcción: se paga por día efectivamente trabajado.
        registro.dias_trabajados = resumen['trabajados']
    else:
        # Mensual: el sueldo cubre `dias_base` (30) incluyendo descansos;
        # las faltas/suspensiones descuentan.
        registro.dias_trabajados = max(0, dias_base - falta)

    registro.dias_descanso = resumen['descanso']
    registro.dias_falta = falta

    if guardar:
        registro.save(update_fields=['dias_trabajados', 'dias_descanso', 'dias_falta'])
    return resumen


def horas_extra_desde_tareo(personal, fecha_inicio, fecha_fin) -> dict:
    """Suma las horas extra ya calculadas por el módulo de Tareo en el período.

    Reutiliza he_25/he_35/he_100 de `RegistroTareo` (el Tareo ya las calcula
    con su propia lógica de jornada); aquí solo se agregan para la boleta.
    """
    from asistencia.models import RegistroTareo
    from django.db.models import Sum

    agg = (
        RegistroTareo.objects
        .filter(personal=personal, fecha__gte=fecha_inicio, fecha__lte=fecha_fin)
        .aggregate(h25=Sum('he_25'), h35=Sum('he_35'), h100=Sum('he_100'))
    )
    return {
        'he_25':  agg['h25'] or Decimal('0'),
        'he_35':  agg['h35'] or Decimal('0'),
        'he_100': agg['h100'] or Decimal('0'),
    }


def poblar_he_desde_tareo(registro, *, guardar=False) -> dict:
    """Puebla registro.horas_extra_25/35/100 desde el Tareo del período."""
    periodo = registro.periodo
    he = horas_extra_desde_tareo(registro.personal, periodo.fecha_inicio, periodo.fecha_fin)
    registro.horas_extra_25 = he['he_25']
    registro.horas_extra_35 = he['he_35']
    registro.horas_extra_100 = he['he_100']
    if guardar:
        registro.save(update_fields=['horas_extra_25', 'horas_extra_35', 'horas_extra_100'])
    return he


def jornada_promedio_ciclo(regimen_turno) -> Decimal:
    """Horas ordinarias promedio por día del ciclo — base de HHEE en jornada acumulativa.

    Para jornadas acumulativas (Art. 9 D.S. 007-2002-TR) el promedio de horas del
    ciclo no puede exceder el máximo legal (48 h/semana). Se calcula repartiendo
    el máximo de horas del ciclo entre el total de días del ciclo (trabajo+descanso).
    Ej. 21x7 → 192 h / 28 días = 6.86 h/día promedio legal.

    NOTA: es la base legal promedio; el pago efectivo de HHEE debe considerar la
    jornada pactada. Este helper se expone para las estrategias de cálculo (F2+);
    no se cablea directamente al motor aquí.
    """
    if regimen_turno is None:
        return Decimal('8')
    total = regimen_turno.ciclo_total_dias
    if not total:
        return Decimal('8')
    return (regimen_turno.horas_max_ciclo / Decimal(str(total))).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP,
    )
