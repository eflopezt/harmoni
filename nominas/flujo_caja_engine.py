"""
Engine de Proyección de Flujo de Caja de Planilla — Harmoni.

Proyecta mensualmente los desembolsos de planilla basándose en los datos
actuales del personal activo y sus condiciones contractuales.

Componentes por mes:
  headcount         — personal activo en el mes
  rem_bruta         — sueldo + asig. familiar (base remunerativa)
  neto              — rem_bruta - AFP/ONP - IR 5ta (lo que recibe el trabajador)
  cond_trabajo      — condición de trabajo / hospedaje (no rem.)
  alimentacion      — alimentación (no rem.)
  essalud           — EsSalud 9% (aporte empleador)
  gratificaciones   — provisión mensual 1/6 × rem_bruta → 2 gratif/año
  cts               — provisión mensual (D.Leg. 650)
  liquidaciones     — estimado para contratos que vencen el mes

  total_desembolso  — todo lo que sale de caja ese mes
  acumulado         — running total

Base legal:
  AFP: Resolución SBS 2026 (tasas vigentes)
  EsSalud: Ley 26790 Art. 6 — 9%
  Gratif: Ley 27735 — 1 sueldo julio + 1 diciembre
  CTS: DL 650 Art. 21 — 1/12 sueldo por mes
"""
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from dateutil.relativedelta import relativedelta

from personal.models import Personal
from .engine import (
    AFP_TASAS, AFP_APORTE, ONP_TASA, ESSALUD_TASA,
    calcular_ir_5ta_mensual, ASIG_FAM,
)

# ── Constantes locales ────────────────────────────────────────────────
_MESES_ES = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
              'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']

# AFP total (aporte 10% + comisión flujo + prima seguro) — descuento del trabajador
_AFP_TOTAL_PCT = {
    afp: AFP_APORTE + tasas['comision_flujo'] + tasas['seguro']
    for afp, tasas in AFP_TASAS.items()
}
_AFP_DEFAULT_PCT = Decimal('13.35')   # promedio estimado para AFP no identificada


# ── Helpers ───────────────────────────────────────────────────────────

def _r(v: Decimal) -> Decimal:
    """Redondea a 2 decimales con ROUND_HALF_UP."""
    return Decimal(v).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _es_activo_en_mes(emp: dict, mes_inicio: date, mes_fin: date) -> bool:
    """True si el empleado está activo durante algún día del mes."""
    # Alta posterior al cierre del mes
    fecha_alta = emp.get('fecha_alta')
    if fecha_alta and fecha_alta > mes_fin:
        return False
    # Cese anterior al inicio del mes
    fecha_cese = emp.get('fecha_cese')
    if fecha_cese and fecha_cese < mes_inicio:
        return False
    # Contrato vencido antes del inicio del mes
    fecha_fin = emp.get('fecha_fin_contrato')
    if fecha_fin and fecha_fin < mes_inicio:
        return False
    return True


def _vence_en_mes(emp: dict, mes_inicio: date, mes_fin: date) -> bool:
    """True si el contrato vence dentro del mes."""
    fecha_fin = emp.get('fecha_fin_contrato')
    if not fecha_fin:
        return False
    return mes_inicio <= fecha_fin <= mes_fin


def _descuento_pension(emp: dict, rem_computable: Decimal) -> Decimal:
    """Calcula descuento total de pensión del trabajador (AFP o ONP)."""
    regimen = emp.get('regimen_pension', '')
    if regimen == 'AFP':
        pct = _AFP_TOTAL_PCT.get(emp.get('afp', ''), _AFP_DEFAULT_PCT)
        return _r(rem_computable * pct / Decimal('100'))
    elif regimen == 'ONP':
        return _r(rem_computable * ONP_TASA / Decimal('100'))
    return Decimal('0')


def _liquidacion_estimada(emp: dict, mes_fin: date) -> Decimal:
    """
    Estimación de liquidación (gratificación + CTS proporcionales al semestre).
    Se usa para contratos que vencen en el mes.
    """
    sueldo = emp.get('sueldo_base') or Decimal('0')
    asig_fam = ASIG_FAM if emp.get('asignacion_familiar') else Decimal('0')
    rem_comp = sueldo + asig_fam

    # Meses transcurridos en el semestre en curso (1 = primer mes, 6 = último)
    mes = mes_fin.month
    inicio_semestre = date(mes_fin.year, 1 if mes <= 6 else 7, 1)
    meses_semestre = (mes_fin.year * 12 + mes_fin.month) - (
        inicio_semestre.year * 12 + inicio_semestre.month) + 1

    # Gratificación proporcional semestre (Ley 27735)
    gratif_prop = _r(rem_comp * Decimal(meses_semestre) / Decimal('6'))

    # CTS proporcional (DL 650): base = rem_comp + 1/6 de gratif anual
    base_cts = rem_comp + _r(rem_comp / Decimal('6'))
    cts_prop = _r(base_cts * Decimal(meses_semestre) / Decimal('12'))

    return gratif_prop + cts_prop


# ── Engine principal ──────────────────────────────────────────────────

def proyectar_flujo_caja(n_meses: int = 18, empresa_id=None) -> tuple:
    """
    Genera la proyección mensual del flujo de caja de planilla.

    Args:
        n_meses:    Número de meses a proyectar (6–36). Default 18.
        empresa_id: Filtrar por empresa (None = todas).

    Returns:
        (meses, empleados) donde:
            meses     — list[dict] con totales por mes + presencia del empleado
            empleados — list[dict] datos del personal (con 'presencias' adjunto)
    """
    n_meses = max(1, min(n_meses, 60))
    hoy = date.today()
    inicio = hoy.replace(day=1)

    # ── Consulta de empleados ──────────────────────────────────────────
    qs = Personal.objects.filter(estado__in=['Activo', 'Suspendido'])
    if empresa_id:
        qs = qs.filter(empresa_id=empresa_id)

    empleados = list(qs.values(
        'id', 'apellidos_nombres', 'nro_doc', 'cargo',
        'grupo_tareo', 'condicion', 'regimen_pension', 'afp',
        'asignacion_familiar', 'sueldo_base',
        'cond_trabajo_mensual', 'alimentacion_mensual', 'viaticos_mensual',
        'eps_descuento_mensual',
        'fecha_alta', 'fecha_fin_contrato', 'fecha_cese',
        'estado',
        'subarea__area__nombre',
    ))

    # ── Precompute month boundaries ───────────────────────────────────
    months_info = []
    for i in range(n_meses):
        fecha = inicio + relativedelta(months=i)
        mes_fin = (fecha + relativedelta(months=1)) - timedelta(days=1)
        months_info.append({
            'fecha':     fecha,
            'inicio':    fecha,
            'fin':       mes_fin,
            'mes_label': f"{_MESES_ES[fecha.month]}-{str(fecha.year)[2:]}",
        })

    # ── Employee presence matrix ──────────────────────────────────────
    # emp_presencias[j][i] = bool (active in month i for employee j)
    emp_presencias = []
    for emp in empleados:
        pres = [
            _es_activo_en_mes(emp, m['inicio'], m['fin'])
            for m in months_info
        ]
        emp_presencias.append(pres)
        emp['presencias'] = pres
        emp['meses_activos'] = sum(pres)

    # ── Monthly aggregation ───────────────────────────────────────────
    meses = []
    acumulado = Decimal('0')

    for i, m_info in enumerate(months_info):
        mes_inicio = m_info['inicio']
        mes_fin    = m_info['fin']

        t = {k: Decimal('0') for k in (
            'rem_bruta', 'descuentos_pension', 'ir_5ta', 'neto',
            'cond_trabajo', 'alimentacion', 'viaticos',
            'essalud', 'gratificaciones', 'cts', 'liquidaciones',
        )}
        headcount = 0

        for j, emp in enumerate(empleados):
            if not emp_presencias[j][i]:
                continue

            headcount += 1
            sueldo   = emp.get('sueldo_base') or Decimal('0')
            asig_fam = ASIG_FAM if emp.get('asignacion_familiar') else Decimal('0')
            rem_comp = sueldo + asig_fam

            # Pensión (AFP o ONP — descuento del trabajador)
            desc_pension = _descuento_pension(emp, rem_comp)

            # IR 5ta — proyección anualizada
            eps_anual = (emp.get('eps_descuento_mensual') or Decimal('0')) * 12
            # rem × 14 meses: 12 ordinarios + 2 gratificaciones
            rem_anual = rem_comp * Decimal('14')
            ir = calcular_ir_5ta_mensual(rem_anual, deduccion_eps_anual=eps_anual)

            # Neto trabajador (ingresa a su cuenta)
            neto = rem_comp - desc_pension - ir

            # EsSalud (aporte empleador)
            essalud = _r(rem_comp * ESSALUD_TASA / Decimal('100'))

            # Provisión gratificación (1/6 mensual → 2 × año)
            gratif_prov = _r(rem_comp / Decimal('6'))

            # Provisión CTS (D.Leg. 650): base = rem_comp + 1/6 rem (asimilado a gratif)
            base_cts  = rem_comp + _r(rem_comp / Decimal('6'))
            cts_prov  = _r(base_cts / Decimal('12'))

            # Liquidación para empleados que terminan este mes
            liq = _liquidacion_estimada(emp, mes_fin) if _vence_en_mes(emp, mes_inicio, mes_fin) else Decimal('0')

            t['rem_bruta']        += rem_comp
            t['descuentos_pension'] += desc_pension
            t['ir_5ta']           += ir
            t['neto']             += neto
            t['cond_trabajo']     += (emp.get('cond_trabajo_mensual') or Decimal('0'))
            t['alimentacion']     += (emp.get('alimentacion_mensual') or Decimal('0'))
            t['viaticos']         += (emp.get('viaticos_mensual') or Decimal('0'))
            t['essalud']          += essalud
            t['gratificaciones']  += gratif_prov
            t['cts']              += cts_prov
            t['liquidaciones']    += liq

        # Total desembolso: rem_bruta (neto + pensiones → AFP/ONP)
        # + no-rem + cargas sociales + provisiones + liquidaciones
        total_desembolso = (
            t['rem_bruta']
            + t['cond_trabajo']
            + t['alimentacion']
            + t['viaticos']
            + t['essalud']
            + t['gratificaciones']
            + t['cts']
            + t['liquidaciones']
        )
        acumulado += total_desembolso

        meses.append({
            'fecha':          m_info['fecha'],
            'mes_label':      m_info['mes_label'],
            'headcount':      headcount,
            'rem_bruta':      _r(t['rem_bruta']),
            'neto':           _r(t['neto']),
            'cond_trabajo':   _r(t['cond_trabajo']),
            'alimentacion':   _r(t['alimentacion']),
            'viaticos':       _r(t['viaticos']),
            'essalud':        _r(t['essalud']),
            'gratificaciones': _r(t['gratificaciones']),
            'cts':            _r(t['cts']),
            'liquidaciones':  _r(t['liquidaciones']),
            'total_desembolso': _r(total_desembolso),
            'acumulado':      _r(acumulado),
            # Presupuesto (se enriquece en la vista)
            'presup_total':   None,
            'variacion':      None,
            'variacion_pct':  None,
        })

    return meses, empleados


# ── Engine de Plan de Plantilla ───────────────────────────────────────

def proyectar_desde_plan(plan, n_meses: int = None) -> tuple:
    """
    Proyecta el flujo de caja de un PlanPlantilla.

    Usa las LineaPlan del plan como fuente de datos en lugar de Personal activo.
    Cada línea puede tener `cantidad` > 1 (N posiciones iguales).

    Args:
        plan:     instancia de PlanPlantilla (ya consultada con prefetch_related opcional)
        n_meses:  meses a proyectar; si None, usa el horizonte natural del plan
                  (fecha_fin − hoy) o 18 por defecto.

    Returns:
        (meses, posiciones) con la misma estructura que proyectar_flujo_caja(),
        pero 'posiciones' son dicts derivados de LineaPlan (sin FK Personal).
    """

    hoy     = date.today()
    inicio  = hoy.replace(day=1)

    # Horizonte: hasta fecha_fin del plan o n_meses explícito
    if n_meses is None:
        if plan.fecha_fin:
            # meses entre inicio y fecha_fin del plan
            meses_plan = (plan.fecha_fin.year * 12 + plan.fecha_fin.month) - \
                         (inicio.year * 12 + inicio.month) + 1
            n_meses = max(6, min(meses_plan, 60))
        else:
            n_meses = 18
    n_meses = max(6, min(n_meses, 60))

    # ── Líneas del plan ───────────────────────────────────────────────
    lineas_qs = plan.lineas.select_related('area', 'personal').order_by('orden', 'cargo')
    lineas = list(lineas_qs.values(
        'id', 'cargo', 'cantidad',
        'sueldo_base', 'asignacion_familiar',
        'regimen_pension', 'afp',
        'cond_trabajo_mensual', 'alimentacion_mensual',
        'fecha_inicio_puesto', 'fecha_fin_puesto',
        'personal__apellidos_nombres',
        'area_id', 'area__nombre',
        'notas', 'orden',
    ))

    # Convertir campos numéricos a Decimal (values() puede devolver str en SQLite)
    for l in lineas:
        l['sueldo_base']         = Decimal(str(l['sueldo_base'] or 0))
        l['cond_trabajo_mensual'] = Decimal(str(l['cond_trabajo_mensual'] or 0))
        l['alimentacion_mensual'] = Decimal(str(l['alimentacion_mensual'] or 0))
        # Añadir fecha_cese = None (no existe en el plan, solo fecha_fin_puesto)
        l['fecha_cese']          = None
        l['fecha_alta']          = l['fecha_inicio_puesto']
        l['fecha_fin_contrato']  = l['fecha_fin_puesto'] or plan.fecha_fin

    # ── Límites de mes ────────────────────────────────────────────────
    months_info = []
    for i in range(n_meses):
        fecha   = inicio + relativedelta(months=i)
        mes_fin = (fecha + relativedelta(months=1)) - timedelta(days=1)
        months_info.append({
            'fecha':     fecha,
            'inicio':    fecha,
            'fin':       mes_fin,
            'mes_label': f"{_MESES_ES[fecha.month]}-{str(fecha.year)[2:]}",
        })

    # ── Presencias (igual que en proyectar_flujo_caja) ────────────────
    linea_presencias = []
    for l in lineas:
        pres = [
            _es_activo_en_mes(l, m['inicio'], m['fin'])
            for m in months_info
        ]
        linea_presencias.append(pres)
        l['presencias']    = pres
        l['meses_activos'] = sum(pres)

    # ── Agregación mensual ────────────────────────────────────────────
    meses     = []
    acumulado = Decimal('0')

    for i, m_info in enumerate(months_info):
        mes_inicio = m_info['inicio']
        mes_fin    = m_info['fin']

        t = {k: Decimal('0') for k in (
            'rem_bruta', 'descuentos_pension', 'ir_5ta', 'neto',
            'cond_trabajo', 'alimentacion', 'viaticos',
            'essalud', 'gratificaciones', 'cts', 'liquidaciones',
        )}
        headcount = 0

        for j, l in enumerate(lineas):
            if not linea_presencias[j][i]:
                continue

            n = l['cantidad']   # multiplicador: N posiciones iguales
            headcount += n

            sueldo   = l['sueldo_base']
            asig_fam = ASIG_FAM if l['asignacion_familiar'] else Decimal('0')
            rem_comp = sueldo + asig_fam

            # Pensión (por persona × cantidad)
            desc_pension = _descuento_pension(l, rem_comp) * n

            # IR 5ta (por persona × cantidad)
            rem_anual = rem_comp * Decimal('14')
            ir = calcular_ir_5ta_mensual(rem_anual) * n

            neto    = (rem_comp - _descuento_pension(l, rem_comp) - calcular_ir_5ta_mensual(rem_anual)) * n
            essalud = _r(rem_comp * ESSALUD_TASA / Decimal('100')) * n

            gratif_prov = _r(rem_comp / Decimal('6')) * n
            base_cts    = rem_comp + _r(rem_comp / Decimal('6'))
            cts_prov    = _r(base_cts / Decimal('12')) * n

            # Liquidación: solo si el puesto vence en este mes
            if _vence_en_mes(l, mes_inicio, mes_fin):
                liq = _liquidacion_estimada(l, mes_fin) * n
            else:
                liq = Decimal('0')

            t['rem_bruta']          += rem_comp * n
            t['descuentos_pension'] += desc_pension
            t['ir_5ta']             += ir
            t['neto']               += neto
            t['cond_trabajo']       += (l['cond_trabajo_mensual'] or Decimal('0')) * n
            t['alimentacion']       += (l['alimentacion_mensual'] or Decimal('0')) * n
            t['essalud']            += essalud
            t['gratificaciones']    += gratif_prov
            t['cts']                += cts_prov
            t['liquidaciones']      += liq

        total_desembolso = (
            t['rem_bruta']
            + t['cond_trabajo']
            + t['alimentacion']
            + t['viaticos']
            + t['essalud']
            + t['gratificaciones']
            + t['cts']
            + t['liquidaciones']
        )
        acumulado += total_desembolso

        meses.append({
            'fecha':            m_info['fecha'],
            'mes_label':        m_info['mes_label'],
            'headcount':        headcount,
            'rem_bruta':        _r(t['rem_bruta']),
            'neto':             _r(t['neto']),
            'cond_trabajo':     _r(t['cond_trabajo']),
            'alimentacion':     _r(t['alimentacion']),
            'viaticos':         Decimal('0'),   # LineaPlan no tiene viáticos
            'essalud':          _r(t['essalud']),
            'gratificaciones':  _r(t['gratificaciones']),
            'cts':              _r(t['cts']),
            'liquidaciones':    _r(t['liquidaciones']),
            'total_desembolso': _r(total_desembolso),
            'acumulado':        _r(acumulado),
            'presup_total':     None,
            'variacion':        None,
            'variacion_pct':    None,
        })

    return meses, lineas
