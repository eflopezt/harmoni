"""
Reproceso automático de asistencia cuando cambia la condición o grupo de un empleado.

Se dispara desde personal_update() cuando cambian:
  - condicion (LOCAL ↔ FORÁNEO ↔ LIMA)
  - grupo_tareo (STAFF ↔ RCO)

Recalcula:
  1. RegistroTareo.condicion / grupo en todos los registros
  2. Horas (jornada correcta según nueva condición)
  3. BancoHoras (saldos HE)
"""
import logging
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

logger = logging.getLogger(__name__)

CERO = Decimal('0')
DOS = Decimal('2')
JORNADA_SAB_LOCAL = Decimal('5.5')

CODIGOS_SIN_HE = {
    'DL', 'DLA', 'CHE', 'VAC', 'DM', 'LCG', 'LF', 'LP', 'LSG',
    'FA', 'TR', 'CDT', 'CPF', 'FER', 'ATM', 'SAI', 'DS',
}

DIAS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']


def reprocesar_asistencia_personal(personal, old_condicion=None, old_grupo=None):
    """
    Reprocesa registros de asistencia de un empleado en períodos ABIERTOS.

    Solo modifica registros cuyos períodos de cierre NO estén CERRADOS.
    Los períodos cerrados se reportan como omitidos.

    Args:
        personal: instancia de Personal (ya con los nuevos valores)
        old_condicion: condición anterior (para log)
        old_grupo: grupo anterior (para log)

    Returns:
        dict con estadísticas del reproceso
    """
    from asistencia.models import (
        RegistroTareo, ConfiguracionSistema, FeriadoCalendario, BancoHoras,
    )

    config = ConfiguracionSistema.get()
    feriados = set(
        FeriadoCalendario.objects.filter(activo=True).values_list('fecha', flat=True)
    )
    nueva_condicion = (personal.condicion or 'LOCAL').upper().replace('\xc1', 'A')
    nuevo_grupo = (personal.grupo_tareo or 'STAFF').upper()

    # ── Determinar períodos cerrados (no modificables) ──────────
    from cierre.models import PeriodoCierre
    periodos_cerrados = set(
        PeriodoCierre.objects
        .filter(estado='CERRADO')
        .values_list('anio', 'mes')
    )
    # También respetar BancoHoras.cerrado
    bancos_cerrados = set(
        BancoHoras.objects
        .filter(personal=personal, cerrado=True)
        .values_list('periodo_anio', 'periodo_mes')
    )
    meses_cerrados = periodos_cerrados | bancos_cerrados

    def _fecha_en_periodo_cerrado(fecha):
        """Verifica si una fecha pertenece a un período cerrado."""
        return (fecha.year, fecha.month) in meses_cerrados

    # Jornadas según nueva condición
    if nueva_condicion == 'FORANEO':
        jornada_lv = Decimal(str(config.jornada_foraneo_horas))     # 10
        jornada_sab = Decimal(str(config.jornada_foraneo_horas))    # 10
        jornada_dom = Decimal(str(config.jornada_domingo_horas))    # 4
    else:  # LOCAL / LIMA
        jornada_lv = Decimal(str(config.jornada_local_horas))       # 8.5
        jornada_sab = JORNADA_SAB_LOCAL                              # 5.5
        jornada_dom = CERO                                           # descanso

    logger.info(
        f'Reprocesando {personal.apellidos_nombres} ({personal.nro_doc}): '
        f'{old_condicion}→{nueva_condicion}, {old_grupo}→{nuevo_grupo} '
        f'| Períodos cerrados: {sorted(meses_cerrados) or "ninguno"}'
    )

    regs = RegistroTareo.objects.filter(
        personal=personal
    ).order_by('fecha')

    total = regs.count()
    to_update = []
    omitidos_cerrado = 0

    for r in regs:
        # ── Saltar registros en períodos cerrados ──
        if _fecha_en_periodo_cerrado(r.fecha):
            omitidos_cerrado += 1
            continue

        changed = False

        # Actualizar condicion y grupo en el registro
        cond_actual = (r.condicion or '').upper().replace('\xc1', 'A')
        if cond_actual != nueva_condicion:
            r.condicion = personal.condicion
            changed = True
        if (r.grupo or '').upper() != nuevo_grupo:
            r.grupo = nuevo_grupo
            r.he_al_banco = (nuevo_grupo == 'STAFF')
            changed = True

        # Determinar jornada según día y nueva condición
        ds = r.dia_semana if r.dia_semana is not None else r.fecha.weekday()
        es_fer = r.es_feriado or (r.fecha in feriados)
        cod = r.codigo_dia or ''
        hm = r.horas_marcadas

        if ds == 6:
            jornada = jornada_dom
        elif ds == 5:
            jornada = jornada_sab
        else:
            jornada = jornada_lv

        # Recalcular horas
        new_vals = _recalcular(cod, hm, jornada, es_fer, ds)
        if new_vals is None:
            # Domingo LOCAL sin horas y código productivo → DS
            if (ds == 6 and nueva_condicion != 'FORANEO'
                    and not hm and not es_fer
                    and cod in ('NOR', 'A', 'T', '')):
                if r.codigo_dia != 'DS':
                    r.codigo_dia = 'DS'
                    r.fuente_codigo = 'DESCANSO_SEMANAL'
                    r.horas_efectivas = r.horas_normales = CERO
                    r.he_25 = r.he_35 = r.he_100 = CERO
                    changed = True
            if changed:
                to_update.append(r)
            continue

        from asistencia.services.processor import redondear_media_hora
        h_ef, h_norm, he25, he35, he100 = new_vals
        h_ef = redondear_media_hora(h_ef)
        h_norm = redondear_media_hora(h_norm)
        he25 = redondear_media_hora(he25)
        he35 = redondear_media_hora(he35)
        he100 = redondear_media_hora(he100)
        if (r.horas_efectivas != h_ef or r.horas_normales != h_norm
                or r.he_25 != he25 or r.he_35 != he35 or r.he_100 != he100):
            r.horas_efectivas = h_ef
            r.horas_normales = h_norm
            r.he_25 = he25
            r.he_35 = he35
            r.he_100 = he100
            changed = True

        if changed:
            to_update.append(r)

    # Guardar en BD
    if to_update:
        with transaction.atomic():
            RegistroTareo.objects.bulk_update(
                to_update,
                ['condicion', 'grupo', 'he_al_banco', 'codigo_dia', 'fuente_codigo',
                 'horas_efectivas', 'horas_normales', 'he_25', 'he_35', 'he_100'],
                batch_size=300,
            )

    # Recalcular BancoHoras solo para meses NO cerrados
    meses_afectados = set()
    for r in regs:
        meses_afectados.add((r.fecha.year, r.fecha.month))

    banco_updated = 0
    banco_omitidos = 0
    for anio, mes in sorted(meses_afectados):
        # Saltar meses cerrados
        if (anio, mes) in meses_cerrados:
            banco_omitidos += 1
            continue

        # Ciclo según ConfiguracionSistema.dia_corte_planilla
        from asistencia.models import ConfiguracionSistema
        config_ciclo = ConfiguracionSistema.objects.first()
        if config_ciclo:
            ciclo_ini, ciclo_fin = config_ciclo.get_ciclo_he(anio, mes)
        else:
            if mes == 1:
                ciclo_ini = date(anio - 1, 12, 22)
            else:
                ciclo_ini = date(anio, mes - 1, 22)
            ciclo_fin = date(anio, mes, 21)

        sums = (
            RegistroTareo.objects
            .filter(personal=personal, fecha__gte=ciclo_ini, fecha__lte=ciclo_fin)
            .aggregate(s25=Sum('he_25'), s35=Sum('he_35'), s100=Sum('he_100'))
        )
        s25 = sums['s25'] or CERO
        s35 = sums['s35'] or CERO
        s100 = sums['s100'] or CERO
        total_he = s25 + s35 + s100

        if total_he > 0:
            banco, _ = BancoHoras.objects.update_or_create(
                personal=personal, periodo_anio=anio, periodo_mes=mes,
                defaults={
                    'he_25_acumuladas': s25,
                    'he_35_acumuladas': s35,
                    'he_100_acumuladas': s100,
                    'saldo_horas': total_he,
                },
            )
            banco_updated += 1

    # Nombres de meses cerrados para el mensaje
    MESES_ES = ['Ene','Feb','Mar','Abr','May','Jun','Jul','Ago','Sep','Oct','Nov','Dic']
    meses_cerrados_txt = ', '.join(
        f'{MESES_ES[m-1]} {a}' for a, m in sorted(meses_cerrados)
        if (a, m) in meses_afectados
    )

    stats = {
        'total_registros': total,
        'registros_actualizados': len(to_update),
        'registros_omitidos_cerrado': omitidos_cerrado,
        'banco_horas_actualizados': banco_updated,
        'banco_horas_omitidos': banco_omitidos,
        'periodos_cerrados': meses_cerrados_txt,
        'nueva_condicion': nueva_condicion,
        'nuevo_grupo': nuevo_grupo,
    }

    logger.info(
        f'Reproceso completado: {len(to_update)}/{total} registros '
        f'({omitidos_cerrado} omitidos por cierre), '
        f'{banco_updated} BancoHoras ({banco_omitidos} omitidos)'
    )

    return stats


def _recalcular(codigo, horas_marcadas, jornada_h, es_feriado, dia_semana):
    """
    Recalcula horas para un registro individual.
    Retorna (h_ef, h_norm, he25, he35, he100) o None si no aplica.
    """
    # SS
    if codigo == 'SS':
        j = jornada_h if jornada_h > CERO else Decimal('8.5')
        if (es_feriado or dia_semana == 6) and (es_feriado or jornada_h == CERO):
            return j, CERO, CERO, CERO, j
        return j, j, CERO, CERO, CERO

    # Códigos sin HE
    if codigo in CODIGOS_SIN_HE:
        return CERO, CERO, CERO, CERO, CERO

    # Sin horas marcadas → None (manejar fuera)
    if not horas_marcadas or horas_marcadas <= CERO:
        if jornada_h > CERO and codigo not in ('', 'DS', 'FA'):
            return jornada_h, jornada_h, CERO, CERO, CERO
        return None

    horas_m = Decimal(str(horas_marcadas))

    # Almuerzo: >7h bruto → 1h
    almuerzo = Decimal('1') if horas_m > 7 else CERO
    horas_ef = max(CERO, horas_m - almuerzo)

    if horas_ef <= CERO:
        return CERO, CERO, CERO, CERO, CERO

    # Feriado/Domingo
    if es_feriado or dia_semana == 6:
        if es_feriado or jornada_h == CERO:
            return horas_ef, CERO, CERO, CERO, horas_ef
        else:
            h_norm = min(horas_ef, jornada_h)
            he100 = max(CERO, horas_ef - jornada_h)
            return horas_ef, h_norm, CERO, CERO, he100

    # Día normal
    if horas_ef <= jornada_h:
        return horas_ef, horas_ef, CERO, CERO, CERO

    exceso = horas_ef - jornada_h
    he25 = min(exceso, DOS)
    he35 = max(CERO, exceso - DOS)
    return horas_ef, jornada_h, he25, he35, CERO
