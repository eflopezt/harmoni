"""
Sincronización automática Papeleta ↔ RegistroTareo.

Funciones reutilizables invocadas desde:
  - Signals (post_save / post_delete de RegistroPapeleta)
  - Comando de management sync_papeletas_registros (reconciliación masiva)

Reglas:
  - Papeleta en estado APROBADA/EJECUTADA → sus días cubren RegistroTareo con
    el código derivado de tipo_permiso (ef=HE=0).
  - Papeleta en RECHAZADA/ANULADA/PENDIENTE o eliminada → días se restauran
    al código "default" (FA, DS, FER según reglas de calendario).
  - Nunca sobrescribe días con RELOJ+ef>0 ni fuente MANUAL (trabajo real gana).
"""
from datetime import date, timedelta
from decimal import Decimal

from asistencia.models import (
    FeriadoCalendario, RegistroPapeleta, RegistroTareo, TareoImportacion,
)


CERO = Decimal('0')

# Códigos auto que el sync puede sobrescribir.
CODIGOS_AUTO = {'FA', 'DS', 'NA', 'CPF', 'FER', 'DL', 'DLA', 'CHE', 'VAC',
                'DM', 'LCG', 'LSG', 'LF', 'LP', 'LM', 'CT', 'CDT', 'SUS',
                'SAI', 'CAP', 'TR', 'OTR'}

TIPO_A_CODIGO = {
    'BAJADAS':                  'DL',
    'BAJADAS_ACUMULADAS':       'DLA',
    'VACACIONES':               'VAC',
    'DESCANSO_MEDICO':          'DM',
    'COMPENSACION_HE':          'CHE',
    'LICENCIA_CON_GOCE':        'LCG',
    'LICENCIA_SIN_GOCE':        'LSG',
    'LICENCIA_FALLECIMIENTO':   'LF',
    'LICENCIA_PATERNIDAD':      'LP',
    'LICENCIA_MATERNIDAD':      'LM',
    'COMISION_TRABAJO':         'CT',
    'COMPENSACION_FERIADO':     'CPF',
    'COMP_DIA_TRABAJO':         'CDT',
    'SUSPENSION':               'SUS',
    'SUSPENSION_ACTO_INSEGURO': 'SAI',
    'CAPACITACION':             'CAP',
    'TRABAJO_REMOTO':           'CT',
    'OTRO':                     'OTR',
}

# Inverso: codigo_dia → tipo_permiso. Solo códigos que claramente
# representan un permiso/licencia/compensación (no estados de presencia
# ni faltas). Se usa para auto-crear papeleta desde matriz de asistencia.
CODIGO_A_TIPO = {
    'DL':  'BAJADAS',
    'DLA': 'BAJADAS_ACUMULADAS',
    'VAC': 'VACACIONES',
    'V':   'VACACIONES',
    'DM':  'DESCANSO_MEDICO',
    'CHE': 'COMPENSACION_HE',
    'LCG': 'LICENCIA_CON_GOCE',
    'LSG': 'LICENCIA_SIN_GOCE',
    'LF':  'LICENCIA_FALLECIMIENTO',
    'LP':  'LICENCIA_PATERNIDAD',
    'LM':  'LICENCIA_MATERNIDAD',
    'CPF': 'COMPENSACION_FERIADO',
    'CDT': 'COMP_DIA_TRABAJO',
    'SUS': 'SUSPENSION',
    'SAI': 'SUSPENSION_ACTO_INSEGURO',
    'CAP': 'CAPACITACION',
    'CT':  'COMISION_TRABAJO',
}


def _cond_norm(c: str) -> str:
    return (c or 'LOCAL').upper().replace('Á', 'A').replace('Ñ', 'N')


def _codigo_default(personal, fecha: date, es_feriado: bool) -> tuple[str, str]:
    """Retorna (codigo, fuente) para un día sin papeleta ni marcación real.

    Evalúa ReglaEspecialPersonal activas: si el default hubiera sido X y
    una regla tiene codigo_reloj_trigger=X, devuelve codigo_resultado.
    """
    cond = _cond_norm(personal.condicion)
    dow = fecha.weekday()

    if es_feriado:
        codigo, fuente = 'FER', 'FERIADO'
    elif dow == 6 and cond in ('LOCAL', 'LIMA'):
        codigo, fuente = 'DS', 'DESCANSO_SEMANAL'
    elif cond == 'LIMA' and dow < 6:
        codigo, fuente = 'A', 'AUTO_LIMA'
    else:
        codigo, fuente = 'FA', 'FALTA_AUTO'

    # Evaluar ReglaEspecialPersonal (overrride por empleado)
    from django.db.models import Q
    from asistencia.models import ReglaEspecialPersonal
    reglas = ReglaEspecialPersonal.objects.filter(
        personal=personal, activa=True, fecha_desde__lte=fecha,
    ).filter(Q(fecha_hasta__isnull=True) | Q(fecha_hasta__gte=fecha))
    for regla in reglas.order_by('prioridad', 'id'):
        if regla.dias_semana and dow not in regla.dias_semana:
            continue
        if regla.condicion_laboral and _cond_norm(regla.condicion_laboral) != cond:
            continue
        if regla.solo_feriados and not es_feriado:
            continue
        if regla.codigo_reloj_trigger and regla.codigo_reloj_trigger != codigo:
            continue
        return regla.codigo_resultado, 'REGLA_ESPECIAL'

    return codigo, fuente


def _es_trabajo_real(r: RegistroTareo) -> bool:
    """Día marcado por biométrico / ingreso manual: no sobrescribir."""
    if r.fuente_codigo == 'MANUAL':
        return True
    if r.fuente_codigo == 'RELOJ' and (r.horas_efectivas or CERO) > CERO:
        return True
    return False


def aplicar_papeleta(pap: RegistroPapeleta) -> dict:
    """Aplica el código derivado de la papeleta a todos los días cubiertos.

    Solo sobrescribe registros auto o inexistentes. Retorna stats.
    Días en período CERRADO se omiten automáticamente.
    """
    stats = {'actualizados': 0, 'creados': 0, 'skip_trabajo_real': 0,
             'skip_sin_mapeo': 0, 'skip_sin_personal': 0,
             'skip_periodo_cerrado': 0}
    if pap.personal_id is None:
        stats['skip_sin_personal'] = 1
        return stats
    codigo = TIPO_A_CODIGO.get(pap.tipo_permiso)
    if not codigo:
        stats['skip_sin_mapeo'] = 1
        return stats

    imp = _get_or_create_imp()
    feriados = _feriados_cache(pap.fecha_inicio, pap.fecha_fin)
    cerrados = _meses_cerrados_cache(pap.fecha_inicio, pap.fecha_fin)

    a_crear = []
    d = pap.fecha_inicio
    while d <= pap.fecha_fin:
        # Período cerrado: no modificar registros bloqueados
        if (d.year, d.month) in cerrados:
            stats['skip_periodo_cerrado'] += 1
            d += timedelta(days=1)
            continue
        es_feriado = d in feriados
        r = RegistroTareo.objects.filter(personal=pap.personal, fecha=d).first()
        if r is None:
            cond = pap.personal.condicion or 'LOCAL'
            grupo = pap.personal.grupo_tareo or ('STAFF' if _cond_norm(cond) != 'FORANEO' else 'RCO')
            a_crear.append(RegistroTareo(
                importacion=imp,
                personal=pap.personal,
                dni=pap.personal.nro_doc,
                nombre_archivo=pap.personal.apellidos_nombres,
                grupo=grupo, condicion=cond,
                fecha=d, dia_semana=d.weekday(),
                es_feriado=es_feriado,
                codigo_dia=codigo,
                fuente_codigo='PAPELETA',
                horas_efectivas=CERO, horas_normales=CERO,
                he_25=CERO, he_35=CERO, he_100=CERO,
                he_al_banco=(grupo == 'STAFF'),
                papeleta_ref=f'PAP#{pap.pk}',
            ))
            stats['creados'] += 1
        elif _es_trabajo_real(r):
            stats['skip_trabajo_real'] += 1
        elif r.codigo_dia != codigo:
            r.codigo_dia = codigo
            r.fuente_codigo = 'PAPELETA'
            r.horas_efectivas = CERO
            r.horas_normales = CERO
            r.he_25 = CERO
            r.he_35 = CERO
            r.he_100 = CERO
            r.papeleta_ref = f'PAP#{pap.pk}'
            r.save(update_fields=['codigo_dia', 'fuente_codigo',
                                   'horas_efectivas', 'horas_normales',
                                   'he_25', 'he_35', 'he_100', 'papeleta_ref'])
            stats['actualizados'] += 1
        d += timedelta(days=1)

    if a_crear:
        RegistroTareo.objects.bulk_create(a_crear, batch_size=200)
    return stats


def revertir_papeleta(pap: RegistroPapeleta) -> dict:
    """Restaura a código default los días que estaban con esta papeleta.

    Reconoce la papeleta por papeleta_ref=f'PAP#{pap.pk}'.
    Si hay otra papeleta aprobada en el mismo día, la respeta.
    """
    stats = {'restaurados': 0, 'skip_trabajo_real': 0,
             'replazados_otra_pap': 0, 'skip_sin_personal': 0,
             'skip_periodo_cerrado': 0}
    if pap.personal_id is None:
        stats['skip_sin_personal'] = 1
        return stats
    feriados = _feriados_cache(pap.fecha_inicio, pap.fecha_fin)
    cerrados = _meses_cerrados_cache(pap.fecha_inicio, pap.fecha_fin)

    ref = f'PAP#{pap.pk}'
    regs = RegistroTareo.objects.filter(
        personal=pap.personal,
        fecha__gte=pap.fecha_inicio, fecha__lte=pap.fecha_fin,
        papeleta_ref=ref,
    )
    for r in regs:
        # Período cerrado: no modificar
        if (r.fecha.year, r.fecha.month) in cerrados:
            stats['skip_periodo_cerrado'] += 1
            continue
        if _es_trabajo_real(r):
            stats['skip_trabajo_real'] += 1
            continue
        # ¿Hay otra papeleta aprobada cubriendo ese día?
        otra = RegistroPapeleta.objects.filter(
            personal=pap.personal,
            estado__in=['APROBADA', 'EJECUTADA'],
            fecha_inicio__lte=r.fecha,
            fecha_fin__gte=r.fecha,
        ).exclude(pk=pap.pk).order_by('-id').first()
        if otra:
            codigo_nueva = TIPO_A_CODIGO.get(otra.tipo_permiso, 'FA')
            r.codigo_dia = codigo_nueva
            r.fuente_codigo = 'PAPELETA'
            r.papeleta_ref = f'PAP#{otra.pk}'
            stats['replazados_otra_pap'] += 1
        else:
            codigo, fuente = _codigo_default(pap.personal, r.fecha, r.fecha in feriados)
            r.codigo_dia = codigo
            r.fuente_codigo = fuente
            r.papeleta_ref = ''
            stats['restaurados'] += 1
        r.horas_efectivas = CERO
        r.horas_normales = CERO
        r.he_25 = CERO
        r.he_35 = CERO
        r.he_100 = CERO
        r.save(update_fields=['codigo_dia', 'fuente_codigo', 'papeleta_ref',
                               'horas_efectivas', 'horas_normales',
                               'he_25', 'he_35', 'he_100'])
    return stats


# ── helpers de caché ───────────────────────────────────────────────
_imp_cache = {'imp': None}
def _get_or_create_imp() -> TareoImportacion:
    imp = _imp_cache['imp']
    # El pk cacheado puede apuntar a una fila que ya no existe (rollback de
    # transacción en tests, borrado manual): validar contra la BD.
    if imp is None or imp.pk is None or \
            not TareoImportacion.objects.filter(pk=imp.pk).exists():
        _imp_cache['imp'] = TareoImportacion.objects.create(
            archivo_nombre='papeletas_sync_auto',
            tipo='RELOJ',
            periodo_inicio=date(2024, 1, 1),
            periodo_fin=date(2030, 12, 31),
            estado='COMPLETADO',
        )
    return _imp_cache['imp']


_feriados_cache_data = {'set': None, 'year_range': None}
def _feriados_cache(ini: date, fin: date) -> set:
    key = (ini.year, fin.year)
    if _feriados_cache_data['year_range'] != key:
        _feriados_cache_data['set'] = set(
            FeriadoCalendario.objects.filter(
                fecha__year__gte=ini.year, fecha__year__lte=fin.year, activo=True
            ).values_list('fecha', flat=True)
        )
        _feriados_cache_data['year_range'] = key
    return _feriados_cache_data['set']


_cerrados_cache_data = {'set': None}
def _meses_cerrados_cache(ini: date, fin: date) -> set:
    """Set de tuplas (anio, mes) con PeriodoCierre.estado='CERRADO'.

    Cache de proceso (no transaccional): se invalida con reset_caches().
    El range ini/fin se ignora — cargamos todos los cerrados (son pocos).
    """
    if _cerrados_cache_data['set'] is None:
        from cierre.models import PeriodoCierre
        _cerrados_cache_data['set'] = set(
            PeriodoCierre.objects
            .filter(estado='CERRADO')
            .values_list('anio', 'mes')
        )
    return _cerrados_cache_data['set']


def reset_caches():
    _imp_cache['imp'] = None
    _feriados_cache_data['year_range'] = None
    _feriados_cache_data['set'] = None
    _cerrados_cache_data['set'] = None


def crear_papeleta_desde_codigo(personal, fecha: date, codigo: str,
                                 usuario=None, observacion: str = ''):
    """Crea una papeleta APROBADA de un día desde un código de RegistroTareo.

    Si ya existe papeleta APROBADA/EJECUTADA con el mismo tipo cubriendo
    ese día y persona, no crea otra.

    Retorna (papeleta, creada). (None, False) si el código no es de papeleta.
    """
    tipo = CODIGO_A_TIPO.get((codigo or '').upper())
    if not tipo or personal is None:
        return None, False

    existente = RegistroPapeleta.objects.filter(
        personal=personal,
        tipo_permiso=tipo,
        estado__in=['APROBADA', 'EJECUTADA'],
        fecha_inicio__lte=fecha,
        fecha_fin__gte=fecha,
    ).first()
    if existente:
        return existente, False

    area_nombre = ''
    if getattr(personal, 'subarea_id', None):
        try:
            area_nombre = personal.subarea.area.nombre
        except Exception:
            area_nombre = ''

    pap = RegistroPapeleta.objects.create(
        personal=personal,
        dni=getattr(personal, 'nro_doc', '') or '',
        nombre_archivo=getattr(personal, 'apellidos_nombres', '') or '',
        tipo_permiso=tipo,
        fecha_inicio=fecha,
        fecha_fin=fecha,
        dias_habiles=1,
        estado='APROBADA',
        origen='SISTEMA',
        creado_por=usuario,
        aprobado_por=usuario,
        fecha_aprobacion=date.today(),
        observaciones=observacion or 'Generada automáticamente desde matriz de asistencia',
        area_trabajo=area_nombre[:150],
        cargo=(getattr(personal, 'cargo', '') or '')[:150],
    )
    return pap, True
