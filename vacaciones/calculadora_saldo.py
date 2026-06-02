"""
Calculadora de Saldo Vacacional.

Wrapper de alto nivel sobre SaldoVacacional para resolver la pregunta
"¿cuántos días de vacaciones puede pedir HOY el trabajador X?".

Base legal:
- DL 713 Art. 10: Derecho a vacaciones tras 1 año completo de servicio (30 días/año).
- DL 713 Art. 17: Período mínimo de 7 días consecutivos para fraccionar.
- DL 713 Art. 22: Vacaciones truncas proporcionales al cese (30/12 × meses).
- DS 012-92-TR: Reglamento del DL 713.

Esta función es la fuente única de verdad para mostrar el saldo disponible
en el wizard del trabajador y para validar solicitudes nuevas antes de
enviarlas a APROBADA.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional, Dict, Any

from django.db.models import Sum


def _norm_fecha(f):
    """Normaliza una fecha que puede venir como date o str ISO. None si inválida."""
    if not f:
        return None
    if isinstance(f, str):
        try:
            return date.fromisoformat(f[:10])
        except ValueError:
            return None
    return f


def dias_truncos_vacaciones(fecha_alta, fecha_corte: Optional[date] = None) -> float:
    """Días de vacaciones truncos del período en curso (proporcional), DL 713 Art. 22.

    2.5 días por mes (30/12), con meses de 30 días, contados desde el último
    aniversario de servicio hasta la fecha de corte. Tope 30. Función PURA
    (no consulta BD) → reutilizable en liquidación al cese sin tocar la BD.

    Antes este valor vivía en SaldoVacacional.dias_truncos, que nunca se
    persiste (queda 0) → la liquidación omitía los truncos del período en curso.
    """
    f_alta = _norm_fecha(fecha_alta)
    if not f_alta:
        return 0.0
    fecha_corte = fecha_corte or date.today()
    dias_servicio = (fecha_corte - f_alta).days
    if dias_servicio <= 0:
        return 0.0
    anios_servicio = dias_servicio // 365
    dias_periodo_actual = dias_servicio - (anios_servicio * 365)
    meses_periodo_actual = dias_periodo_actual / 30.0
    return min(30.0, round(30.0 / 12.0 * meses_periodo_actual, 2))


def calcular_saldo_vacaciones(personal, fecha_corte: Optional[date] = None) -> Dict[str, Any]:
    """
    Calcula el saldo vacacional disponible para un trabajador a una fecha de corte.

    Combina:
      - Días completos: 30 por cada año de servicio cumplido (DL 713 Art. 10)
      - Días truncos: proporcionales al período en curso (30/12 × meses)
      - Días consumidos: sumatoria de SolicitudVacacion APROBADA + EN_GOCE + COMPLETADA
      - Días pendientes aprobación: solicitudes en estado PENDIENTE / BORRADOR

    Args:
        personal: instancia de personal.models.Personal (o None)
        fecha_corte: fecha al día — por defecto hoy

    Returns:
        Dict con las llaves:
            dias_completos          (int)   — años cumplidos × 30
            dias_truncos            (float) — proporcional al período en curso
            dias_consumidos         (int)   — ya gozados o en goce
            dias_disponibles        (int)   — total - consumidos - pendientes_aprobacion
            dias_pendientes_aprobacion (int) — solicitudes sin aprobar todavía
            anios_servicio          (int)
            meses_servicio          (float)
            cumple_anio             (bool)  — True si tiene >=1 año de antigüedad
            fecha_cumple_anio       (date)  — cuándo cumple el primer año (si aún no)
            fecha_corte             (date)
            tiene_fecha_alta        (bool)
    """
    fecha_corte = fecha_corte or date.today()

    # Edge case: personal sin fecha_alta
    if not personal or not getattr(personal, 'fecha_alta', None):
        return {
            'dias_completos': 0,
            'dias_truncos': 0.0,
            'dias_consumidos': 0,
            'dias_disponibles': 0,
            'dias_pendientes_aprobacion': 0,
            'anios_servicio': 0,
            'meses_servicio': 0.0,
            'cumple_anio': False,
            'fecha_cumple_anio': None,
            'fecha_corte': fecha_corte,
            'tiene_fecha_alta': False,
        }

    f_alta = personal.fecha_alta
    if isinstance(f_alta, str):
        try:
            f_alta = date.fromisoformat(f_alta[:10])
        except ValueError:
            f_alta = None

    if not f_alta:
        return {
            'dias_completos': 0,
            'dias_truncos': 0.0,
            'dias_consumidos': 0,
            'dias_disponibles': 0,
            'dias_pendientes_aprobacion': 0,
            'anios_servicio': 0,
            'meses_servicio': 0.0,
            'cumple_anio': False,
            'fecha_cumple_anio': None,
            'fecha_corte': fecha_corte,
            'tiene_fecha_alta': False,
        }

    dias_servicio = (fecha_corte - f_alta).days
    anios_servicio = dias_servicio // 365
    meses_servicio = round(dias_servicio / 30.0, 1)
    cumple_anio = dias_servicio >= 365

    from datetime import timedelta
    fecha_cumple = f_alta + timedelta(days=365) if not cumple_anio else None

    # Días completos: 30 × años cumplidos
    dias_completos = anios_servicio * 30

    # Días truncos: proporcional al período en curso (helper puro reutilizable)
    dias_truncos = dias_truncos_vacaciones(f_alta, fecha_corte)

    # ── Consumidos: solicitudes en estado terminal aprobado ─────────
    # Importación tardía para evitar ciclos
    from .models import SolicitudVacacion

    consumidos_qs = SolicitudVacacion.objects.filter(
        personal=personal,
        estado__in=['APROBADA', 'EN_GOCE', 'COMPLETADA'],
    ).aggregate(total=Sum('dias_calendario'))
    dias_consumidos = consumidos_qs['total'] or 0

    # ── Pendientes aprobación ──
    pend_qs = SolicitudVacacion.objects.filter(
        personal=personal,
        estado__in=['BORRADOR', 'PENDIENTE'],
    ).aggregate(total=Sum('dias_calendario'))
    dias_pendientes_aprobacion = pend_qs['total'] or 0

    # ── Disponible ──
    # Total generado = dias_completos + dias_truncos (sólo si ya cumplió 1 año
    # tiene derecho a "tomar" vacaciones; los truncos sólo se pagan en cese
    # según Art. 22, pero para visualización los mostramos).
    total_generado = dias_completos + (dias_truncos if cumple_anio else 0)

    dias_disponibles = max(
        0,
        int(total_generado) - int(dias_consumidos) - int(dias_pendientes_aprobacion)
    )

    return {
        'dias_completos': int(dias_completos),
        'dias_truncos': float(dias_truncos),
        'dias_consumidos': int(dias_consumidos),
        'dias_disponibles': int(dias_disponibles),
        'dias_pendientes_aprobacion': int(dias_pendientes_aprobacion),
        'anios_servicio': int(anios_servicio),
        'meses_servicio': float(meses_servicio),
        'cumple_anio': bool(cumple_anio),
        'fecha_cumple_anio': fecha_cumple,
        'fecha_corte': fecha_corte,
        'tiene_fecha_alta': True,
    }


def validar_solicitud(personal, fecha_inicio: date, fecha_fin: date) -> Dict[str, Any]:
    """
    Valida si un trabajador puede solicitar vacaciones en el rango dado.

    Reglas:
      - Personal debe tener fecha_alta
      - Debe cumplir ≥ 1 año de servicio (DL 713 Art. 10)
      - fecha_fin >= fecha_inicio
      - dias solicitados <= saldo disponible
      - Período mínimo de 7 días consecutivos (DL 713 Art. 17) — soft warning

    Returns:
        Dict {
            'ok': bool,
            'dias_solicitados': int,
            'saldo': dict (resultado de calcular_saldo_vacaciones),
            'errores': list[str],
            'avisos': list[str],
        }
    """
    errores = []
    avisos = []

    if fecha_fin < fecha_inicio:
        errores.append('La fecha de fin no puede ser anterior a la fecha de inicio.')
        dias = 0
    else:
        dias = (fecha_fin - fecha_inicio).days + 1

    saldo = calcular_saldo_vacaciones(personal)

    if not saldo['tiene_fecha_alta']:
        errores.append('El trabajador no tiene fecha de ingreso registrada.')
    elif not saldo['cumple_anio']:
        errores.append(
            f'Aún no cumple 1 año de servicio (cumple el '
            f'{saldo["fecha_cumple_anio"].strftime("%d/%m/%Y") if saldo["fecha_cumple_anio"] else "—"}). '
            f'DL 713 Art. 10 exige 1 año completo para el derecho.'
        )

    if dias > saldo['dias_disponibles']:
        errores.append(
            f'Saldo insuficiente: solicita {dias} día(s) pero sólo dispone de '
            f'{saldo["dias_disponibles"]} día(s) (ya consumió {saldo["dias_consumidos"]}, '
            f'pendiente aprobación {saldo["dias_pendientes_aprobacion"]}).'
        )

    if dias > 0 and dias < 7:
        avisos.append(
            f'Período de {dias} día(s). DL 713 Art. 17 recomienda mínimo 7 días '
            f'consecutivos para fraccionar las vacaciones.'
        )

    return {
        'ok': len(errores) == 0,
        'dias_solicitados': dias,
        'saldo': saldo,
        'errores': errores,
        'avisos': avisos,
    }
