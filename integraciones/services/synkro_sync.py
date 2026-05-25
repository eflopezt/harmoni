"""
Sincronización directa con la BD remota de Synkro RRHH (SQL Server).

Lee desde la connection 'synkro' (read-only) las tablas:
  - PER_Personas + P_Personal  (maestro, match por DNI)
  - PicadosPersonal            (marcaciones biométricas)
  - PermisosLicencias          (papeletas)
  - Feriados                   (feriados nacionales)

Y escribe en la connection 'default' (Postgres Harmoni):
  - FeriadoCalendario          (upsert por fecha)
  - RegistroPapeleta           (upsert por id externo)
  - RegistroTareo              (upsert por personal+fecha; agrupa picados)

Diseño:
  - Incremental por defecto (lee desde el cursor de la última sync).
  - Idempotente: corrida repetida no duplica.
  - Respeta períodos CERRADOS (no toca esos días).
  - No sobrescribe registros con fuente=MANUAL ni fuente=PAPELETA con ref.
"""
from __future__ import annotations

import logging
import time
from datetime import date, datetime, time as dt_time, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from integraciones.models import SyncSynkroLog
from integraciones.synkro_models import (
    FeriadoSynkro, PermisoLicencia, PerPersona, PPersonal, PicadoPersonal,
)

logger = logging.getLogger('asistencia')

CERO = Decimal('0')

# Turno noche — corte de salida que cruza medianoche.
# Validación: caso DNI 70919188 (LOPEZ TORRE) en Excel manual (plan Q2 2026).
# Regla: un picado antes de las 05:30 AM se interpreta como SALIDA del día
# anterior cuando ese día anterior tiene un picado >= 18:00 (entrada nocturna).
# La heurística del pivot evita falsos positivos con trabajadores diurnos
# muy tempranos (e.g., panadería entrando 05:00 AM).
CORTE_TURNO_NOCHE_AM = dt_time(5, 30)
PIVOT_NOCHE_PM = dt_time(18, 0)

# Tipos de trabajador en Synkro (RH_TipoTrabajador):
#   2 = Obrero (construcción civil) — NO importar a Harmoni
#   3 = Empleado — sí importar
TIPO_TRAB_EMPLEADO = 3
TIPO_TRAB_OBRERO = 2

# Mapeo de motivo_cese de Synkro (texto libre) → choice canónico de Harmoni
# (Personal.MOTIVO_CESE_CHOICES). Si no matchea, usa 'OTRO'.
MOTIVO_CESE_MAP = [
    ('renuncia voluntaria', 'RENUNCIA'),
    ('renuncia',            'RENUNCIA'),
    ('mutuo acuerdo',       'MUTUO_ACUERDO'),
    ('jubilac',             'JUBILACION'),
    ('vencimiento',         'VENCIMIENTO'),
    ('termino de contrato', 'TERMINO_CONTRATO'),
    ('término de contrato', 'TERMINO_CONTRATO'),
    ('termino contrato',    'TERMINO_CONTRATO'),
    ('termino de partida',  'VENCIMIENTO'),
    ('no renovac',          'NO_RENOVACION'),
    ('despido',             'DESPIDO_CAUSA'),
    ('positivo alcotest',   'DESPIDO_CAUSA'),
    ('cese colectivo',      'CESE_COLECTIVO'),
    ('liquidac',            'LIQUIDACION'),
    ('fallec',              'FALLECIMIENTO'),
    ('invalidez',           'INVALIDEZ'),
    ('abandono',            'ABANDONO'),
    ('no inicio',           'OTRO'),
]


def _mapear_motivo_cese(texto: str) -> str:
    if not texto:
        return ''
    t = texto.strip().lower()
    for needle, canon in MOTIVO_CESE_MAP:
        if needle in t:
            return canon
    return 'OTRO'


# Mapeo IdTipoPermiso (Synkro) → tipo_permiso de RegistroPapeleta (Harmoni)
TIPO_PERMISO_MAP: dict[int, str | None] = {
    1:  'DESCANSO_MEDICO',
    2:  'LICENCIA_CON_GOCE',
    3:  'LICENCIA_SIN_GOCE',
    4:  'VACACIONES',
    5:  'LICENCIA_PATERNIDAD',
    6:  'BAJADAS',
    7:  'TRABAJO_REMOTO',
    8:  'COMISION_TRABAJO',
    9:  'SUSPENSION_ACTO_INSEGURO',
    10: 'LICENCIA_FALLECIMIENTO',
    11: 'OTRO',                    # ATM (atención médica) — no hay equivalente directo
    12: 'COMP_DIA_TRABAJO',
    13: 'SUSPENSION',              # AS (Amonestación)
    14: 'BAJADAS_ACUMULADAS',
    15: None,                      # FR (Feriado no recuperable) — se ignora
    16: 'COMPENSACION_HE',
    17: 'COMPENSACION_FERIADO',
}

# Fuentes de RegistroTareo que el sync puede sobrescribir con datos de reloj.
# Se respetan: MANUAL (edición humana), PAPELETA (papeleta vigente),
# EXCEL (operador subió Excel con HE/ajustes; debe ganar sobre picados crudos
# para no perder horas extra ya pagadas/autorizadas).
FUENTES_REESCRIBIBLES = {
    'FALTA_AUTO', 'DESCANSO_SEMANAL', 'AUTO_LIMA', 'REGLA_ESPECIAL',
    'FERIADO', 'RELOJ',
}


def _normalizar_dni(dni: str | None) -> str:
    """Strip + collapse interno. No hace lpad ni cambia ceros — Harmoni
    guarda los DNIs como vienen, incluido el de extranjeros (con prefijo
    '00').
    """
    if not dni:
        return ''
    return str(dni).strip()


def _build_personal_index_por_dni() -> dict[str, int]:
    """{dni → personal_id} para match rápido en bucle."""
    from personal.models import Personal
    return {
        _normalizar_dni(p.nro_doc): p.id
        for p in Personal.objects.exclude(nro_doc__isnull=True).exclude(nro_doc='')
    }


def _build_synkro_personal_to_dni(solo_empleados: bool = True) -> dict[int, str]:
    """{P_Personal.IdPersonal (Synkro) → DNI}.

    Por defecto filtra solo Empleados (IdTipoTrabajador=3). Los Obreros
    (construcción civil) NO se importan al ERP Harmoni — viven solo en
    Synkro/Plame y reciben otra modalidad de pago.
    """
    qs = PPersonal.objects.using('synkro')
    if solo_empleados:
        qs = qs.filter(id_tipo_trabajador=TIPO_TRAB_EMPLEADO)
    qs = qs.values_list('id_personal', 'id_persona')
    persona_map = dict(qs)
    persona_ids = list(persona_map.values())
    dni_map = dict(
        PerPersona.objects.using('synkro')
        .filter(id_persona__in=persona_ids)
        .values_list('id_persona', 'dni')
    )
    return {pid: _normalizar_dni(dni_map.get(pers_id, ''))
            for pid, pers_id in persona_map.items()}


# ─────────────────────────────────────────────────────────────────────────
# SYNC PERSONAL — altas, ceses, fecha_ingreso (NO condicion/grupo/sueldo)
# ─────────────────────────────────────────────────────────────────────────


def sync_personal() -> dict:
    """Sincroniza datos administrativos de personal desde Synkro.

    SÍ sincroniza:
      - Altas: si hay un DNI en Synkro y no existe en Harmoni → crear
        Personal con datos básicos (nombres, DNI, fecha_alta, celular).
      - Ceses: actualiza fecha_cese y motivo_cese si en Synkro Estado=False
        y FechaTerminoContrato está poblada.
      - Fecha de ingreso (fecha_alta): si está vacía en Harmoni y poblada
        en Synkro, la actualiza.

    NO sincroniza (campos sensibles que afectan cálculo de asistencia o
    que se editan manualmente en el ERP):
      - condicion (LOCAL/FORANEO/LIMA)
      - grupo_tareo (STAFF/RCO)
      - jornada_horas
      - cargo, área, sueldo, AFP, banco
    """
    from personal.models import Personal

    creados = altas_omitidas_sin_datos = 0
    ceses_actualizados = ingreso_actualizado = sin_cambios = 0

    # JOIN P_Personal × PER_Personas en Synkro — solo Empleados (excluye Obreros)
    pp_qs = (PPersonal.objects.using('synkro')
             .filter(id_tipo_trabajador=TIPO_TRAB_EMPLEADO)
             .values('id_personal', 'id_persona', 'estado',
                     'fecha_ingreso', 'fecha_termino_contrato', 'motivo_cese'))

    persona_map = {pp['id_persona']: pp for pp in pp_qs}
    personas_qs = (PerPersona.objects.using('synkro')
                   .filter(id_persona__in=persona_map.keys())
                   .values('id_persona', 'dni', 'a_paterno', 'a_materno',
                           'nombres', 'nombre_completo', 'celular'))

    # Index Harmoni
    personal_existente = {
        _normalizar_dni(p.nro_doc): p
        for p in Personal.objects.exclude(nro_doc__isnull=True).exclude(nro_doc='')
    }

    for psyk in personas_qs:
        dni = _normalizar_dni(psyk['dni'])
        if not dni:
            continue
        pp = persona_map.get(psyk['id_persona'])
        if not pp:
            continue

        existente = personal_existente.get(dni)

        # ── Altas ──
        if existente is None:
            # Solo crear si tenemos al menos un nombre y fecha_ingreso
            apellidos_nombres = (psyk['nombre_completo'] or '').strip()
            if not apellidos_nombres:
                ap = (psyk['a_paterno'] or '').strip()
                am = (psyk['a_materno'] or '').strip()
                no = (psyk['nombres'] or '').strip()
                apellidos_nombres = f'{ap} {am}, {no}'.strip(' ,')
            if not apellidos_nombres or not pp['fecha_ingreso']:
                altas_omitidas_sin_datos += 1
                continue
            try:
                # Crear con campos mínimos. Los campos sensibles (condicion,
                # grupo_tareo, cargo) quedan en defaults — el admin los
                # completa manualmente en el ERP.
                Personal.objects.create(
                    nro_doc=dni,
                    apellidos_nombres=apellidos_nombres[:250],
                    fecha_alta=pp['fecha_ingreso'],
                    celular=(psyk['celular'] or '')[:20],
                    estado='Activo' if pp['estado'] else 'Cesado',
                    fecha_cese=(pp['fecha_termino_contrato']
                                if not pp['estado'] and pp['fecha_termino_contrato']
                                else None),
                    motivo_cese=(_mapear_motivo_cese(pp['motivo_cese'])
                                 if not pp['estado'] else ''),
                )
                creados += 1
            except Exception as exc:
                logger.warning(
                    f'No se pudo crear Personal DNI {dni}: {type(exc).__name__}: {exc}'
                )
                altas_omitidas_sin_datos += 1
            continue

        # ── Actualizaciones (solo campos administrativos) ──
        cambios = []
        # Fecha de ingreso: solo si Harmoni la tiene vacía
        if existente.fecha_alta is None and pp['fecha_ingreso']:
            existente.fecha_alta = pp['fecha_ingreso']
            cambios.append('fecha_alta')
            ingreso_actualizado += 1

        # Cese: si Synkro dice Estado=False y tiene fecha_termino_contrato,
        # y en Harmoni la fecha_cese está vacía o es distinta → actualizar.
        if not pp['estado'] and pp['fecha_termino_contrato']:
            if existente.fecha_cese != pp['fecha_termino_contrato']:
                existente.fecha_cese = pp['fecha_termino_contrato']
                cambios.append('fecha_cese')
            motivo_canon = _mapear_motivo_cese(pp['motivo_cese'])
            if motivo_canon and existente.motivo_cese != motivo_canon:
                existente.motivo_cese = motivo_canon
                cambios.append('motivo_cese')
            if existente.estado != 'Cesado':
                existente.estado = 'Cesado'
                cambios.append('estado')
            if cambios and 'fecha_cese' in cambios:
                ceses_actualizados += 1

        if cambios:
            existente.save(update_fields=cambios)
        else:
            sin_cambios += 1

    return {
        'altas_creadas': creados,
        'altas_omitidas_sin_datos': altas_omitidas_sin_datos,
        'ceses_actualizados': ceses_actualizados,
        'ingreso_actualizado': ingreso_actualizado,
        'sin_cambios': sin_cambios,
    }


# ─────────────────────────────────────────────────────────────────────────
# SYNC FERIADOS
# ─────────────────────────────────────────────────────────────────────────


def sync_feriados() -> int:
    """Upsert FeriadoCalendario desde Synkro.Feriados. Retorna nuevos creados."""
    from asistencia.models import FeriadoCalendario
    creados = 0
    feriados_synkro = list(FeriadoSynkro.objects.using('synkro').all())
    fechas_existentes = set(
        FeriadoCalendario.objects.values_list('fecha', flat=True)
    )
    nuevos = []
    for f in feriados_synkro:
        if f.fecha in fechas_existentes:
            continue
        nuevos.append(FeriadoCalendario(
            fecha=f.fecha,
            nombre=(f.descripcion or 'Feriado').strip()[:150],
            activo=True,
        ))
    if nuevos:
        FeriadoCalendario.objects.bulk_create(nuevos, ignore_conflicts=True)
        creados = len(nuevos)
    return creados


# ─────────────────────────────────────────────────────────────────────────
# SYNC PAPELETAS
# ─────────────────────────────────────────────────────────────────────────


def sync_papeletas(cursor_desde: datetime | None,
                   personal_dni_map: dict[int, str],
                   personal_idx: dict[str, int]) -> dict:
    """Lee papeletas nuevas/modificadas desde Synkro y upsert en RegistroPapeleta.

    Match: la papeleta se identifica externamente por
    `(origen='SYNKRO', importacion=None, observaciones LIKE 'SYNKRO#{IdPermiso}')`
    para detectar duplicados en re-corridas.

    Retorna: {creadas, actualizadas, omitidas, no_encontradas, max_cursor}
    """
    from asistencia.models import RegistroPapeleta

    qs = PermisoLicencia.objects.using('synkro').all()
    if cursor_desde:
        # Tomar registros con FechaRegistro o FechaModifica >= cursor
        from django.db.models import Q
        qs = qs.filter(
            Q(fecha_registro__gte=cursor_desde) |
            Q(fecha_modifica__gte=cursor_desde)
        )
    qs = qs.order_by('id_permiso')

    creadas = actualizadas = omitidas = no_encontradas = 0
    max_cursor: datetime | None = None

    # Index existente por marca SYNKRO#{id}
    existentes_por_extid = {}
    for pap in RegistroPapeleta.objects.filter(
        observaciones__contains='SYNKRO#'
    ).only('id', 'observaciones', 'estado', 'tipo_permiso',
           'fecha_inicio', 'fecha_fin', 'detalle'):
        # Extract SYNKRO#{n} del campo observaciones
        marker = pap.observaciones.split('SYNKRO#')[1].split()[0] if 'SYNKRO#' in pap.observaciones else ''
        if marker.isdigit():
            existentes_por_extid[int(marker)] = pap

    for permiso in qs.iterator(chunk_size=200):
        # Cursor: latest de fecha_registro/fecha_modifica (ambos tz-aware
        # cuando vienen de SQL Server con USE_TZ=True).
        ts_candidates = [t for t in (permiso.fecha_modifica, permiso.fecha_registro)
                         if t is not None]
        if ts_candidates:
            ts = max(ts_candidates)
            if max_cursor is None or ts > max_cursor:
                max_cursor = ts

        tipo = TIPO_PERMISO_MAP.get(permiso.id_tipo_permiso)
        if not tipo:
            omitidas += 1
            continue

        dni = personal_dni_map.get(permiso.id_personal)
        if not dni:
            no_encontradas += 1
            continue
        personal_id = personal_idx.get(dni)
        if not personal_id:
            no_encontradas += 1
            continue

        # Defensa contra data corrupta en Synkro (fechas invertidas)
        if permiso.fecha_fin < permiso.fecha_inicio:
            logger.warning(
                f'Synkro PermisoLicencia #{permiso.id_permiso}: '
                f'fechas invertidas {permiso.fecha_inicio}..{permiso.fecha_fin}, omitida.'
            )
            omitidas += 1
            continue

        dias_h = max(1, (permiso.fecha_fin - permiso.fecha_inicio).days + 1)
        defaults = {
            'personal_id': personal_id,
            'dni': dni,
            'tipo_permiso': tipo,
            'fecha_inicio': permiso.fecha_inicio,
            'fecha_fin': permiso.fecha_fin,
            'detalle': (permiso.detalle or '')[:500],
            'dias_habiles': dias_h,
            'estado': 'APROBADA',
            'origen': 'IMPORTACION',
            'observaciones': f'SYNKRO#{permiso.id_permiso} | sync auto',
        }

        existente = existentes_por_extid.get(permiso.id_permiso)
        try:
            with transaction.atomic():
                if existente:
                    # Actualizar solo si cambió algo material
                    cambios = []
                    if existente.tipo_permiso != tipo:
                        cambios.append('tipo_permiso')
                        existente.tipo_permiso = tipo
                    if existente.fecha_inicio != permiso.fecha_inicio:
                        cambios.append('fecha_inicio')
                        existente.fecha_inicio = permiso.fecha_inicio
                    if existente.fecha_fin != permiso.fecha_fin:
                        cambios.append('fecha_fin')
                        existente.fecha_fin = permiso.fecha_fin
                    nuevo_detalle = (permiso.detalle or '')[:500]
                    if (existente.detalle or '') != nuevo_detalle:
                        cambios.append('detalle')
                        existente.detalle = nuevo_detalle
                    if cambios:
                        existente.dias_habiles = max(
                            1, (existente.fecha_fin - existente.fecha_inicio).days + 1
                        )
                        cambios.append('dias_habiles')
                        existente.save(update_fields=cambios)
                        actualizadas += 1
                    else:
                        omitidas += 1
                else:
                    # Crear (signal aplicar_papeleta sincroniza RegistroTareo)
                    RegistroPapeleta.objects.create(**defaults)
                    creadas += 1
        except Exception as exc:
            logger.warning(
                f'Synkro PermisoLicencia #{permiso.id_permiso} '
                f'(personal_id={permiso.id_personal}, tipo={tipo}, '
                f'{permiso.fecha_inicio}..{permiso.fecha_fin}): {type(exc).__name__}: {exc}'
            )
            omitidas += 1

    return {
        'creadas': creadas,
        'actualizadas': actualizadas,
        'omitidas': omitidas,
        'no_encontradas': no_encontradas,
        'max_cursor': max_cursor,
    }


# ─────────────────────────────────────────────────────────────────────────
# SYNC PICADOS → REGISTRO TAREO
# ─────────────────────────────────────────────────────────────────────────


def _remapear_turno_noche(
    grupos: dict[tuple[int, date], list[datetime]],
) -> int:
    """Re-agrupa picados de madrugada al día anterior cuando hay evidencia
    de turno noche.

    Reglas:
      - Un grupo cuya totalidad de picados son < 05:30 AM es candidato a
        ser SALIDA del día anterior.
      - Solo se remapea si el grupo del día anterior ya tiene picados y al
        menos uno es >= 18:00 (entrada de turno noche evidenciada).

    Muta `grupos` in-place: mueve picados del candidato al día anterior y
    elimina la clave del candidato. Retorna el número de claves remapeadas.

    Edge case conocido: si en la corrida solo se sincroniza el día N+1
    (madrugada) y el día N ya estaba sincronizado pero quedó con salida
    None, este remapeo no lo detecta — habría que ir a BD a buscar el
    RegistroTareo previo. Mitigación: el sync periódico solapa la ventana
    (ventana_picados_dias=7 por defecto) así que ambos días vendrán juntos.
    TODO: agregar lookup BD opcional si se observa que el caso ocurre.
    """
    remapear: list[tuple[tuple[int, date], tuple[int, date]]] = []
    for clave_src, picados_src in grupos.items():
        if not picados_src:
            continue
        if not all(p.time() < CORTE_TURNO_NOCHE_AM for p in picados_src):
            continue
        id_personal, fecha_src = clave_src
        clave_dst = (id_personal, fecha_src - timedelta(days=1))
        picados_dst = grupos.get(clave_dst)
        if not picados_dst:
            continue
        if not any(p.time() >= PIVOT_NOCHE_PM for p in picados_dst):
            continue
        remapear.append((clave_src, clave_dst))

    for src, dst in remapear:
        grupos[dst].extend(grupos.pop(src))
    return len(remapear)


def sync_picados(cursor_desde: datetime | None,
                 personal_dni_map: dict[int, str],
                 personal_idx: dict[str, int],
                 ventana_dias_max: int = 60) -> dict:
    """Lee picados nuevos desde el cursor y los consolida en RegistroTareo
    como 1 fila por (personal, fecha) usando MIN/MAX de Fecha como
    entrada/salida.

    Solo procesa picados de los últimos `ventana_dias_max` días aunque el
    cursor sea más antiguo (evita reprocesar histórico masivo en caso de
    reset accidental del cursor).
    """
    from asistencia.models import (
        FeriadoCalendario, RegistroTareo, TareoImportacion,
    )
    from asistencia.views.calendario import _recalcular_horas
    from cierre.models import PeriodoCierre

    # Determinar ventana real
    fecha_min = (timezone.now() - timedelta(days=ventana_dias_max)).date()
    if cursor_desde:
        cursor_fecha = cursor_desde.date()
        if cursor_fecha < fecha_min:
            cursor_fecha = fecha_min
    else:
        cursor_fecha = fecha_min

    # Cursor: usamos FechaSinMS (date) para incremental por día
    qs = (PicadoPersonal.objects.using('synkro')
          .filter(fecha_sin_ms__gte=cursor_fecha)
          .order_by('id_personal', 'fecha'))

    # Agrupar picados en memoria por (personal_id_synkro, fecha)
    grupos: dict[tuple[int, date], list[datetime]] = {}
    max_cursor: datetime | None = None
    for p in qs.iterator(chunk_size=2000):
        key = (p.id_personal, p.fecha_sin_ms)
        grupos.setdefault(key, []).append(p.fecha)
        if max_cursor is None or p.fecha > max_cursor:
            max_cursor = p.fecha

    if not grupos:
        return {'creados': 0, 'actualizados': 0, 'no_encontrados': 0,
                'omitidos_cerrado': 0, 'max_cursor': max_cursor}

    # Turno noche: re-agrupar picados de madrugada al día anterior cuando
    # hay evidencia de entrada nocturna. Ver _remapear_turno_noche.
    remapeos_noche = _remapear_turno_noche(grupos)
    if remapeos_noche:
        logger.info(
            '[sync_picados] turno noche: %d grupos de madrugada remapeados '
            'al día anterior.', remapeos_noche
        )

    # Caches
    feriados_set = set(
        FeriadoCalendario.objects.filter(activo=True)
        .values_list('fecha', flat=True)
    )
    cerrados = set(
        PeriodoCierre.objects.filter(estado='CERRADO')
        .values_list('anio', 'mes')
    )
    imp_synkro, _ = TareoImportacion.objects.get_or_create(
        tipo='RELOJ', archivo_nombre='synkro_sync_directo',
        defaults={
            'estado': 'COMPLETADO', 'total_registros': 0,
            'periodo_inicio': date(2025, 1, 1), 'periodo_fin': date(2030, 12, 31),
        },
    )

    from personal.models import Personal
    personal_obj_cache: dict[int, Personal] = {}

    creados = actualizados = no_encontrados = omitidos_cerrado = 0

    for (id_personal_syn, fecha), picados in grupos.items():
        if (fecha.year, fecha.month) in cerrados:
            omitidos_cerrado += 1
            continue
        dni = personal_dni_map.get(id_personal_syn)
        if not dni:
            no_encontrados += 1
            continue
        pid_harmoni = personal_idx.get(dni)
        if not pid_harmoni:
            no_encontrados += 1
            continue

        # Cargar Personal una vez por persona en esta corrida
        if pid_harmoni not in personal_obj_cache:
            try:
                personal_obj_cache[pid_harmoni] = Personal.objects.get(pk=pid_harmoni)
            except Personal.DoesNotExist:
                no_encontrados += 1
                continue
        p_obj = personal_obj_cache[pid_harmoni]

        # Respetar período laboral: no crear/actualizar registros fuera del
        # rango fecha_alta..fecha_cese del trabajador.
        if p_obj.fecha_alta and fecha < p_obj.fecha_alta:
            continue
        if p_obj.fecha_cese and fecha > p_obj.fecha_cese:
            continue

        if not picados:
            continue
        entrada = min(picados).time()
        salida = max(picados).time() if len(picados) >= 2 else None

        es_feriado = fecha in feriados_set
        condicion = (p_obj.condicion or 'LOCAL').upper()
        grupo = p_obj.grupo_tareo or ('STAFF' if condicion.replace('Á', 'A') != 'FORANEO' else 'RCO')

        # Buscar registro existente
        reg = RegistroTareo.objects.filter(personal_id=pid_harmoni, fecha=fecha).first()
        if reg is None:
            # Crear nuevo
            reg = RegistroTareo(
                importacion=imp_synkro,
                personal_id=pid_harmoni,
                dni=dni,
                nombre_archivo=p_obj.apellidos_nombres or '',
                grupo=grupo, condicion=condicion,
                fecha=fecha, dia_semana=fecha.weekday(),
                es_feriado=es_feriado,
                hora_entrada_real=entrada,
                hora_salida_real=salida,
                codigo_dia='A' if salida else 'SS',
                fuente_codigo='RELOJ',
                he_al_banco=(grupo == 'STAFF'),
            )
            _recalcular_horas(reg)
            reg.save()
            creados += 1
        else:
            # Solo sobrescribir si la fuente es reescribible (no MANUAL/PAPELETA)
            if reg.fuente_codigo == 'MANUAL':
                continue
            if reg.fuente_codigo == 'PAPELETA' and (reg.papeleta_ref or '').startswith('PAP#'):
                # Día cubierto por papeleta vigente: respetar
                continue
            if reg.fuente_codigo not in FUENTES_REESCRIBIBLES:
                continue
            cambios = False
            if reg.hora_entrada_real != entrada:
                reg.hora_entrada_real = entrada
                cambios = True
            if reg.hora_salida_real != salida:
                reg.hora_salida_real = salida
                cambios = True
            if cambios or reg.fuente_codigo != 'RELOJ':
                reg.fuente_codigo = 'RELOJ'
                # Códigos auto-reescribibles cuando llegan nuevos picados:
                # FA/F/DS/NA/FER → primera vez que el sistema "vio" al trabajador
                # SS/SE → marcación parcial previa (solo entrada o solo salida)
                # Si ahora hay entrada+salida → debería ser 'A' (asistido).
                if reg.codigo_dia in ('FA', 'F', 'DS', 'NA', 'FER', 'SS', 'SE'):
                    reg.codigo_dia = 'A' if salida else 'SS'
                _recalcular_horas(reg)
                reg.save()
                actualizados += 1

    # ── Propagar HE → BancoHoras (solo STAFF) ──────────────────────────
    # Sin este paso, los picados se sincronizan pero el banco queda desactualizado.
    # Caso real (Stiler mayo 2026): 123 STAFF con HE pero solo 19 en BancoHoras.
    banco_resumen = _propagar_banco_horas_desde_picados(
        creados=creados,
        actualizados=actualizados,
        personal_obj_cache=personal_obj_cache,
        fechas_procesadas=set(fecha for (_, fecha) in grupos.keys()),
    )

    return {
        'creados': creados,
        'actualizados': actualizados,
        'no_encontrados': no_encontrados,
        'omitidos_cerrado': omitidos_cerrado,
        'max_cursor': max_cursor,
        'banco_horas': banco_resumen,
    }


def _propagar_banco_horas_desde_picados(creados: int, actualizados: int,
                                        personal_obj_cache: dict,
                                        fechas_procesadas: set) -> dict:
    """Propaga HE del tareo recién sincronizado al BancoHoras (solo STAFF).

    Se llama al final de sync_picados. Recorre los meses afectados por la
    sincronización y, para cada STAFF activo con HE en ese mes, hace
    update_or_create del BancoHoras con los acumulados desde RegistroTareo.

    NO toca registros donde periodo_cerrado=True ni reescribe meses ya
    auditados (cerrado=True en BancoHoras).
    """
    from decimal import Decimal
    from django.db.models import Sum, Q
    from asistencia.models import BancoHoras, RegistroTareo

    if not fechas_procesadas:
        return {'meses_actualizados': 0, 'staff_actualizados': 0}

    # Meses afectados
    meses_set = {(f.year, f.month) for f in fechas_procesadas}

    # Staff IDs cacheados (los que ya procesamos en sync_picados)
    staff_ids = [pid for pid, p in personal_obj_cache.items()
                 if p and (p.grupo_tareo or '').upper() == 'STAFF']

    if not staff_ids:
        return {'meses_actualizados': 0, 'staff_actualizados': 0}

    total_actualizados = 0
    for anio, mes in meses_set:
        # No reescribir meses ya cerrados (auditados)
        cerrados_ids = set(BancoHoras.objects.filter(
            periodo_anio=anio, periodo_mes=mes, cerrado=True,
            personal_id__in=staff_ids,
        ).values_list('personal_id', flat=True))

        candidatos_ids = [pid for pid in staff_ids if pid not in cerrados_ids]
        if not candidatos_ids:
            continue

        # Sumar HE del mes por trabajador
        resumen = (
            RegistroTareo.objects.filter(
                fecha__year=anio, fecha__month=mes,
                personal_id__in=candidatos_ids,
                grupo='STAFF',
            )
            .values('personal_id')
            .annotate(s25=Sum('he_25'), s35=Sum('he_35'), s100=Sum('he_100'))
        )

        for r in resumen:
            pid = r['personal_id']
            s25 = r['s25'] or Decimal('0')
            s35 = r['s35'] or Decimal('0')
            s100 = r['s100'] or Decimal('0')
            total_acum = s25 + s35 + s100
            if total_acum == 0:
                continue

            banco, _created = BancoHoras.objects.get_or_create(
                personal_id=pid,
                periodo_anio=anio,
                periodo_mes=mes,
                defaults={'observaciones': 'Sincronizado desde Synkro (sync_picados)'},
            )
            # Solo actualizar si los acumulados cambiaron
            cambio = (
                banco.he_25_acumuladas != s25 or
                banco.he_35_acumuladas != s35 or
                banco.he_100_acumuladas != s100
            )
            if cambio:
                banco.he_25_acumuladas = s25
                banco.he_35_acumuladas = s35
                banco.he_100_acumuladas = s100
                # Saldo = acumuladas - compensadas (preserva he_compensadas existente)
                banco.saldo_horas = total_acum - (banco.he_compensadas or Decimal('0'))
                banco.save(update_fields=[
                    'he_25_acumuladas', 'he_35_acumuladas', 'he_100_acumuladas',
                    'saldo_horas', 'actualizado_en',
                ])
                total_actualizados += 1

    return {
        'meses_actualizados': len(meses_set),
        'staff_actualizados': total_actualizados,
    }


# ─────────────────────────────────────────────────────────────────────────
# ORQUESTADOR
# ─────────────────────────────────────────────────────────────────────────


def _ultimo_cursor() -> tuple[datetime | None, datetime | None]:
    """(cursor_papeletas, cursor_picados) del último log OK."""
    last = (SyncSynkroLog.objects
            .filter(estado='OK')
            .order_by('-iniciado_en')
            .first())
    if not last:
        return None, None
    return last.cursor_papeletas, last.cursor_picados


def run_sync(usuario=None, origen: str = 'AUTO',
             ventana_picados_dias: int = 60) -> SyncSynkroLog:
    """Corre el sync completo. Crea SyncSynkroLog y lo retorna.

    Excepciones propagadas se capturan y se guardan en error_mensaje.
    """
    log = SyncSynkroLog.objects.create(
        origen=origen, usuario=usuario, estado='EN_PROGRESO',
    )
    t0 = time.time()
    try:
        cursor_pap_prev, cursor_pic_prev = _ultimo_cursor()

        # 1. Personal: altas + ceses + fecha_ingreso (NO condicion/grupo).
        # Se hace antes que feriados/papeletas/picados para que el resto
        # encuentre a las personas recién creadas.
        res_personal = sync_personal()

        # 2. Maestros y mapping de DNI (después del sync de personal)
        personal_idx = _build_personal_index_por_dni()
        personal_dni_map = _build_synkro_personal_to_dni()

        # 3. Feriados (full upsert; no necesita cursor)
        feriados_creados = sync_feriados()

        # 4. Papeletas (incremental). Cada papeleta tiene su propia
        # transacción interna; si una falla por data corrupta no afecta
        # al resto.
        res_pap = sync_papeletas(cursor_pap_prev, personal_dni_map, personal_idx)

        # 5. Picados (incremental)
        res_pic = sync_picados(cursor_pic_prev, personal_dni_map, personal_idx,
                               ventana_dias_max=ventana_picados_dias)

        log.feriados_creados = feriados_creados
        log.papeletas_creadas = res_pap['creadas']
        log.papeletas_actualizadas = res_pap['actualizadas']
        log.papeletas_omitidas = res_pap['omitidas']
        log.registros_tareo_creados = res_pic['creados']
        log.registros_tareo_actualizados = res_pic['actualizados']
        log.personas_no_encontradas = (
            res_pap['no_encontradas'] + res_pic['no_encontrados']
        )
        log.cursor_papeletas = res_pap['max_cursor'] or cursor_pap_prev
        log.cursor_picados = res_pic['max_cursor'] or cursor_pic_prev
        log.estado = 'OK'
        log.detalle = {
            'personal': res_personal,
            'papeletas': res_pap | {'max_cursor': str(res_pap.get('max_cursor') or '')},
            'picados': {**res_pic, 'max_cursor': str(res_pic.get('max_cursor') or '')},
            'feriados': {'creados': feriados_creados},
            'personal_synkro_total': len(personal_dni_map),
            'personal_harmoni_total': len(personal_idx),
        }
    except Exception as exc:
        logger.exception('Sync Synkro falló')
        log.estado = 'ERROR'
        log.error_mensaje = f'{type(exc).__name__}: {exc}'[:2000]
    finally:
        log.finalizado_en = timezone.now()
        log.duracion_segundos = round(time.time() - t0, 2)
        log.save()
    return log
