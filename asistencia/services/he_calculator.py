"""
Calculadora unificada de Horas Extra (HE).

Regla legal:
  - Decreto Legislativo 854 → jornada máxima 48h/semana.
  - D.S. 007-2002-TR Art. 10 → 1ra y 2da HE al 25%, 3ra+ al 35%.
  - D.Leg. 713 Art. 3-4 → descanso semanal trabajado al 100%.
  - D.Leg. 713 Art. 9 → feriado laborado al 100%.

Histórico:
  La lógica de cálculo HE estaba duplicada en:
    - asistencia/services/processor.py → TareoProcessor._calcular_horas_raw
    - asistencia/views/calendario.py   → _recalcular_horas

  Este módulo es la fuente única de verdad. Ambos callers son thin
  wrappers que reutilizan `calcular_he_componentes` y/o
  `calcular_he_para_registro`.

API pública:
  - calcular_he_componentes(codigo, horas_marcadas, jornada_h, ...) -> tuple
      Función pura. Devuelve (horas_ef, horas_normales, he_25, he_35, he_100)
      SIN redondear (el wrapper redondea con `redondear_media_hora`).

  - calcular_he_para_registro(reg, config, personal) -> dict
      Conveniencia para edición vía UI (calendario). Calcula la jornada
      desde reg+config+personal y devuelve los componentes ya redondeados.

  - obtener_jornada_diaria(personal, condicion, dia_semana, config, *, modo)
      Resuelve la jornada del día. `modo='processor'` aplica el override
      sólo si personal.jornada_horas != 8 (regla histórica del importador);
      `modo='ui'` aplica el override si está seteado (regla #5 de calendario).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal, Optional

from asistencia.services._helpers import (
    calcular_almuerzo_h,
    redondear_media_hora,
)

CERO = Decimal('0')

# ──────────────────────────────────────────────────────────────
# Sets de códigos
# ──────────────────────────────────────────────────────────────
# Códigos que NO generan HE (el día se paga pero no suma horas al banco/pago).
# Importador: usa esta lista canónica.
CODIGOS_SIN_HE = {
    'SS', 'DL', 'DLA', 'CHE', 'VAC', 'DM', 'LCG', 'LF',
    'LP', 'LSG', 'FA', 'TR', 'CDT', 'CPF', 'ATM', 'SAI',
    'DS', 'FER',
}

# Mismo conjunto + códigos extra que sólo aparecen en la UI de calendario
# (sinónimos legacy o códigos sintéticos para celdas vacías).
CODIGOS_SIN_HE_UI = CODIGOS_SIN_HE | {'F', 'V', 'SUB', 'B', 'LIM', 'NA'}


# ──────────────────────────────────────────────────────────────
# Jornada diaria
# ──────────────────────────────────────────────────────────────
def obtener_jornada_diaria(
    personal,
    condicion: str,
    dia_semana: int,
    config,
    *,
    modo: Literal['processor', 'ui'] = 'processor',
) -> Decimal:
    """
    Jornada en horas para `dia_semana` (0=lun … 6=dom).

    Reglas:
      LOCAL / LIMA  lun–vie (0–4) → config.jornada_local_horas   (def 8.5h)
      LOCAL / LIMA  sábado  (5)   → config.jornada_sabado_horas  (def 5.5h)
      LOCAL / LIMA  domingo (6)   → 0   (descanso semanal; si trabaja → 100%)
      FORÁNEO       lun–sáb       → config.jornada_foraneo_horas (def 11.0h)
      FORÁNEO       domingo       → config.jornada_domingo_horas (def 4.0h)

    Override en Personal.jornada_horas:
      modo='processor': sólo si valor != 8 (regla histórica del importador
                        que evita que el default del campo anule la config).
      modo='ui':        si está seteado (cualquier valor). Regla #5 fix de
                        calendario — la UI sí permite override explícito a 8.
    """
    if modo == 'processor':
        if (personal and personal.jornada_horas
                and Decimal(str(personal.jornada_horas)) != Decimal('8')):
            return Decimal(str(personal.jornada_horas))
    else:  # modo == 'ui'
        if personal and personal.jornada_horas is not None:
            return Decimal(str(personal.jornada_horas))

    cond_norm = (condicion or '').upper().replace('Á', 'A')

    if dia_semana == 6:  # domingo
        if cond_norm == 'FORANEO':
            return Decimal(str(config.jornada_domingo_horas))
        return CERO

    if cond_norm == 'FORANEO':
        return Decimal(str(config.jornada_foraneo_horas))

    if dia_semana == 5:  # sábado
        return Decimal(str(config.jornada_sabado_horas))
    return Decimal(str(config.jornada_local_horas))


# ──────────────────────────────────────────────────────────────
# Núcleo: cálculo de componentes HE (función pura)
# ──────────────────────────────────────────────────────────────
def calcular_he_componentes(
    codigo: str,
    horas_marcadas: Optional[Decimal],
    jornada_h: Decimal,
    es_feriado: bool,
    es_ss: bool = False,
    dia_semana: Optional[int] = None,
    tiene_papeleta_comp: bool = False,
    he_bloqueado: bool = False,
    almuerzo_manual: Optional[Decimal] = None,
    fuente_codigo: str = '',
    codigos_sin_he: Optional[set] = None,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal]:
    """
    Función pura. Devuelve (horas_efectivas, horas_normales, he_25, he_35, he_100)
    SIN redondear. El caller redondea con `redondear_media_hora`.

    Reglas HE (D.S. 007-2002-TR, art. 10):
      - 1ra y 2da HE → tasa 25%
      - 3ra HE en adelante → tasa 35%
      - Feriado laborado → 100% (D.Leg. 713, Art. 9)
      - Descanso semanal trabajado → 100% (D.Leg. 713, Art. 3-4)

    Regla SS (Sin Salida):
      - Día SS se paga como jornada completa (horas_efectivas = jornada)
      - NO genera HE de ningún tipo
      - NO va al banco de horas
      - En feriado o domingo LOCAL → SS se paga al 100%

    `codigos_sin_he`: permite que la UI inyecte un set ampliado (CODIGOS_SIN_HE_UI)
    sin afectar el importador.
    """
    sin_he = codigos_sin_he if codigos_sin_he is not None else CODIGOS_SIN_HE

    # ── SS (Sin Salida): paga jornada, sin HE adicional ─────
    if es_ss:
        j = jornada_h if jornada_h > CERO else Decimal('8.5')
        es_descanso = (dia_semana == 6) if dia_semana is not None else False
        # LOCAL domingo o feriado: SS también se paga al 100%
        # D.Leg. 713: trabajar en descanso semanal o feriado → 100%
        if (es_feriado or es_descanso) and (es_feriado or jornada_h == CERO):
            return j, CERO, CERO, CERO, j
        return j, j, CERO, CERO, CERO

    # ── Marcación incompleta: horas < jornada/2 → SS implícito
    # Si marcó entrada pero no salida (o solo salida a refrigerio),
    # el biométrico calcula pocas horas. Se reconoce jornada completa, sin HE.
    if (horas_marcadas and horas_marcadas > CERO
            and horas_marcadas < jornada_h / 2
            and codigo not in sin_he):
        return jornada_h, jornada_h, CERO, CERO, CERO

    # ── Códigos sin horas ni HE ──────────────────────────────
    if codigo in sin_he or not horas_marcadas or horas_marcadas <= CERO:
        return CERO, CERO, CERO, CERO, CERO

    # ── Descontar almuerzo ───────────────────────────────────
    almuerzo_h = calcular_almuerzo_h(horas_marcadas, jornada_h, almuerzo_manual)
    horas_ef = max(CERO, horas_marcadas - almuerzo_h)

    # ── Feriado laborado o descanso semanal trabajado: 100% ─
    # Si hay papeleta de compensación APROBADA → trata como día normal
    # (D.Leg. 713 Art. 6 — compensación en lugar de pago HE 100%).
    es_descanso_semanal = (
        ((dia_semana == 6) if dia_semana is not None else False)
        or codigo == 'DSL'
    )
    codigo_es_feriado = codigo == 'FL'
    # Si el CÓDIGO dice laborado en descanso/feriado, todas las horas al 100%
    # (no aplica la jornada reducida de FORÁNEO domingo).
    codigo_fuerza_100 = codigo in ('DSL', 'FL')
    # #4 fix: si el admin cambió manualmente a NOR/T/A, calcular como día normal
    # (el trabajador tiene descanso semanal en otro día, no el domingo)
    codigo_fuerza_normal = (
        codigo in ('NOR', 'T', 'A') and fuente_codigo == 'MANUAL'
    )
    if ((es_feriado or codigo_es_feriado or es_descanso_semanal)
            and not tiene_papeleta_comp and not codigo_fuerza_normal):
        jornada = Decimal(str(jornada_h))
        if es_feriado or codigo_fuerza_100 or jornada == CERO:
            # Feriado (toda condición) o LOCAL domingo: TODAS las horas al 100%
            return horas_ef, CERO, CERO, CERO, horas_ef
        # FORÁNEO domingo (4h jornada): normal hasta jornada, exceso HE 100%
        h_norm = min(horas_ef, jornada)
        he100 = max(CERO, horas_ef - jornada)
        return horas_ef, h_norm, CERO, CERO, he100

    # ── Día normal ───────────────────────────────────────────
    jornada = Decimal(str(jornada_h))
    if horas_ef <= jornada:
        return horas_ef, horas_ef, CERO, CERO, CERO

    # ── Control HE: sin solicitud aprobada → se capan en jornada
    # DL 728: HE son voluntarias; el empleador puede exigir autorización previa.
    if he_bloqueado:
        return jornada, jornada, CERO, CERO, CERO

    # Exceso sobre la jornada normal → HE
    exceso = horas_ef - jornada
    he25 = min(exceso, Decimal('2'))            # primeras 2 HE al 25%
    he35 = max(CERO, exceso - Decimal('2'))     # 3ra HE en adelante al 35%
    return horas_ef, jornada, he25, he35, CERO


# ──────────────────────────────────────────────────────────────
# Conveniencia: cálculo desde un RegistroTareo (UI calendario)
# ──────────────────────────────────────────────────────────────
def calcular_he_para_registro(reg, config, personal) -> dict:
    """
    Calcula horas para un RegistroTareo (camino UI / edición manual).

    - Resuelve jornada desde personal/config (modo='ui' → respeta override).
    - Recalcula horas marcadas desde entrada/salida (helper compartido).
    - Aplica tope sanitario 16h.
    - Consulta FeriadoCalendario y SolicitudHE en DB si hace falta.
    - Devuelve dict con componentes YA REDONDEADOS a múltiplos de 0.5.

    Output keys:
      horas_marcadas, horas_efectivas, horas_normales,
      he_25, he_35, he_100, almuerzo_h, jornada_h

    Notas:
      - El caller (calendario._recalcular_horas) es responsable de asignar
        los valores al modelo (`reg.horas_efectivas = ...`).
      - Mantiene paridad de comportamiento con la versión histórica de
        calendario._recalcular_horas — incluido el TODO de he_bloqueado.
    """
    import logging
    from asistencia.services._helpers import (
        calcular_horas_marcadas_desde_horarios,
        cap_horas_dia,
    )
    from asistencia.models import FeriadoCalendario

    logger = logging.getLogger('asistencia')
    condicion = (reg.condicion or '').upper()
    dia_semana = reg.fecha.weekday()

    jornada_h = obtener_jornada_diaria(
        personal, condicion, dia_semana, config, modo='ui',
    )

    # Horas marcadas desde entrada/salida (fallback al campo si están vacías)
    horas_marcadas = calcular_horas_marcadas_desde_horarios(
        reg.fecha, reg.hora_entrada_real, reg.hora_salida_real,
        horas_marcadas_fallback=reg.horas_marcadas,
    )
    # #6 fix: tope sanitario 16h
    horas_marcadas = cap_horas_dia(
        horas_marcadas, dni=reg.dni, fecha=reg.fecha, logger=logger,
    )

    codigo = reg.codigo_dia

    # ¿Feriado? La UI consulta DB porque el flag `reg.es_feriado` puede no
    # estar seteado en registros antiguos.
    es_feriado_db = reg.es_feriado or FeriadoCalendario.objects.filter(
        fecha=reg.fecha, activo=True,
    ).exists()

    # ¿HE bloqueado? Misma regla que processor: si config exige solicitud,
    # bloquear HE cuando no hay SolicitudHE APROBADA para ese día.
    he_bloqueado = False
    if personal and getattr(config, 'he_requiere_solicitud', False):
        from asistencia.models import SolicitudHE
        he_bloqueado = not SolicitudHE.objects.filter(
            personal=personal, fecha=reg.fecha, estado='APROBADA',
        ).exists()

    # SS (Sin Salida) tiene su propia rama; el resto pasa por el núcleo
    es_ss = (codigo == 'SS')

    horas_ef, h_norm, he25, he35, he100 = calcular_he_componentes(
        codigo=codigo,
        horas_marcadas=horas_marcadas,
        jornada_h=jornada_h,
        es_feriado=es_feriado_db,
        es_ss=es_ss,
        dia_semana=dia_semana,
        tiene_papeleta_comp=False,   # la UI no resuelve papeletas aquí
        he_bloqueado=he_bloqueado,
        almuerzo_manual=reg.almuerzo_manual,
        fuente_codigo=reg.fuente_codigo or '',
        codigos_sin_he=CODIGOS_SIN_HE_UI,
    )

    # Cálculo del almuerzo para debug/inspect (no se aplica si ya está SS / sin horas)
    if horas_marcadas and horas_marcadas > CERO and codigo not in CODIGOS_SIN_HE_UI:
        almuerzo_h_dbg = calcular_almuerzo_h(
            horas_marcadas, jornada_h, reg.almuerzo_manual,
        )
    else:
        almuerzo_h_dbg = CERO

    return {
        'horas_marcadas': horas_marcadas,
        'horas_efectivas': redondear_media_hora(horas_ef),
        'horas_normales': redondear_media_hora(h_norm),
        'he_25': redondear_media_hora(he25),
        'he_35': redondear_media_hora(he35),
        'he_100': redondear_media_hora(he100),
        'almuerzo_h': almuerzo_h_dbg,
        'jornada_h': jornada_h,
    }
