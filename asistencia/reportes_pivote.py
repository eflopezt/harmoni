"""
asistencia.reportes_pivote
==========================

Agregador para Reportes Pivote Cross-Empresa.

Construye una estructura tipo Excel:
    filas    = trabajadores (filtrables por empresa, grupo_tareo, subarea)
    columnas = días del rango
    celdas   = código de estado por día (A=asistió, F=falta, T=tardanza,
               V=vacaciones, P=permiso, X=descanso, etc.)

Optimizado para Grupo Sabores (24 RUCs, ~800 trabajadores):
- Bulk queries sin N+1.
- Combina RegistroTareo (estado del día) + RegistroPapeleta (V, P, etc.).
- Resumen por trabajador + totales por día para tabla pivote completa.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal
from typing import Iterable

from django.db.models import Q


# ── Códigos de estado canónicos para el pivote ────────────────────
# La celda muestra UNA sola letra/sigla. Mapeamos el universo amplio
# de codigo_dia del RegistroTareo a un alfabeto de pivote más reducido.
ESTADO_ASISTIO = 'A'      # Trabajó (NOR, T, TR, A, etc.)
ESTADO_TARDANZA = 'T'     # Tarde
ESTADO_FALTA = 'F'        # Falta no justificada
ESTADO_VACACIONES = 'V'   # Vacaciones (papeleta VAC)
ESTADO_PERMISO = 'P'      # Permiso/licencia/dm
ESTADO_DESCANSO = 'X'     # Descanso semanal / DSO
ESTADO_FERIADO = 'H'      # Feriado (holiday)
ESTADO_VACIO = '·'        # Sin registro

# Códigos de RegistroTareo.codigo_dia → estado pivote
_TAREO_CODIGO_MAP = {
    # Asistencia normal
    'NOR': ESTADO_ASISTIO,
    'A': ESTADO_ASISTIO,
    'TR': ESTADO_ASISTIO,   # Trabajo Remoto cuenta como asistió
    'CDT': ESTADO_ASISTIO,
    'CPF': ESTADO_ASISTIO,
    'LIM': ESTADO_ASISTIO,
    'ATM': ESTADO_ASISTIO,
    'CHE': ESTADO_ASISTIO,
    'SS': ESTADO_ASISTIO,
    # Tardanza
    'T': ESTADO_TARDANZA,
    'TARDE': ESTADO_TARDANZA,
    # Falta
    'F': ESTADO_FALTA,
    'FA': ESTADO_FALTA,
    'FL': ESTADO_FALTA,
    # Vacaciones
    'VAC': ESTADO_VACACIONES,
    'V': ESTADO_VACACIONES,
    # Permisos / licencias / descanso médico
    'DM': ESTADO_PERMISO,
    'LCG': ESTADO_PERMISO,
    'LSG': ESTADO_PERMISO,
    'LF': ESTADO_PERMISO,
    'LP': ESTADO_PERMISO,
    'LM': ESTADO_PERMISO,
    'PL': ESTADO_PERMISO,
    'PC': ESTADO_PERMISO,
    'PM': ESTADO_PERMISO,
    'PE': ESTADO_PERMISO,
    'CT': ESTADO_PERMISO,
    'CAP': ESTADO_PERMISO,
    'SAI': ESTADO_PERMISO,
    'SUS': ESTADO_PERMISO,
    'DL': ESTADO_PERMISO,
    'DLA': ESTADO_PERMISO,
    'B': ESTADO_PERMISO,
    # Descanso semanal / DSO
    'DS': ESTADO_DESCANSO,
    'DSO': ESTADO_DESCANSO,
    'X': ESTADO_DESCANSO,
    # Feriado
    'FER': ESTADO_FERIADO,
}

# Tipo papeleta → estado pivote (usado cuando no hay RegistroTareo del día)
_PAPELETA_TIPO_MAP = {
    'VACACIONES': ESTADO_VACACIONES,
    'DESCANSO_MEDICO': ESTADO_PERMISO,
    'LICENCIA_CON_GOCE': ESTADO_PERMISO,
    'LICENCIA_SIN_GOCE': ESTADO_PERMISO,
    'LICENCIA_FALLECIMIENTO': ESTADO_PERMISO,
    'LICENCIA_PATERNIDAD': ESTADO_PERMISO,
    'LICENCIA_MATERNIDAD': ESTADO_PERMISO,
    'COMPENSACION_HE': ESTADO_PERMISO,
    'COMISION_TRABAJO': ESTADO_PERMISO,
    'CAPACITACION': ESTADO_PERMISO,
    'TRABAJO_REMOTO': ESTADO_ASISTIO,
    'BAJADAS': ESTADO_PERMISO,
    'BAJADAS_ACUMULADAS': ESTADO_PERMISO,
    'SUSPENSION': ESTADO_PERMISO,
    'SUSPENSION_ACTO_INSEGURO': ESTADO_PERMISO,
    'COMPENSACION_FERIADO': ESTADO_PERMISO,
    'COMP_DIA_TRABAJO': ESTADO_PERMISO,
    'OTRO': ESTADO_PERMISO,
}


# Para coloring en tabla / Excel / PDF
COLOR_ESTADO = {
    ESTADO_ASISTIO: '#d4edda',      # verde claro
    ESTADO_TARDANZA: '#fff3cd',     # amarillo claro
    ESTADO_FALTA: '#f8d7da',        # rojo claro
    ESTADO_VACACIONES: '#cfe2ff',   # azul
    ESTADO_PERMISO: '#e2d9f3',      # violeta claro
    ESTADO_DESCANSO: '#e9ecef',     # gris
    ESTADO_FERIADO: '#ffe5cc',      # naranja claro
    ESTADO_VACIO: '#ffffff',
}

# Etiqueta humana
LABEL_ESTADO = {
    ESTADO_ASISTIO: 'Asistió',
    ESTADO_TARDANZA: 'Tardanza',
    ESTADO_FALTA: 'Falta',
    ESTADO_VACACIONES: 'Vacaciones',
    ESTADO_PERMISO: 'Permiso/Licencia',
    ESTADO_DESCANSO: 'Descanso',
    ESTADO_FERIADO: 'Feriado',
    ESTADO_VACIO: 'Sin registro',
}


def _map_codigo_tareo(codigo: str | None) -> str:
    """Mapea RegistroTareo.codigo_dia → estado pivote."""
    if not codigo:
        return ESTADO_VACIO
    return _TAREO_CODIGO_MAP.get(codigo.upper(), ESTADO_VACIO)


def _map_tipo_papeleta(tipo: str | None) -> str:
    """Mapea RegistroPapeleta.tipo_permiso → estado pivote."""
    if not tipo:
        return ESTADO_PERMISO
    return _PAPELETA_TIPO_MAP.get(tipo.upper(), ESTADO_PERMISO)


def _rango_fechas(desde: date, hasta: date) -> list[date]:
    if hasta < desde:
        return []
    return [desde + timedelta(days=i) for i in range((hasta - desde).days + 1)]


def construir_pivote(
    desde: date,
    hasta: date,
    empresa_ids: Iterable[int] | None = None,
    grupo_tareo: str | None = None,
    area_id: int | None = None,
    subarea_id: int | None = None,
    limite_trabajadores: int | None = None,
) -> dict:
    """
    Construye estructura pivote cross-empresa.

    Args:
        desde, hasta: rango de fechas (inclusivo).
        empresa_ids: lista/iterable de IDs de empresa (opcional).
        grupo_tareo: 'STAFF' / 'RCO' / 'OTRO' (opcional).
        area_id: id de Area (opcional, vía subarea__area).
        subarea_id: id de SubArea (opcional).
        limite_trabajadores: corta el queryset a N filas (para preview/PDF).

    Returns:
        {
            'desde': date, 'hasta': date,
            'fechas': [date1, ...],
            'trabajadores': [
                {
                    'personal': Personal,
                    'empresa_nombre': str,
                    'dias': {date1: 'A', date2: 'T', ...},
                    'total_trabajados': int,
                    'total_faltas': int,
                    'total_tardanzas': int,
                    'total_vacaciones': int,
                    'total_permisos': int,
                    'total_horas': float,
                    'total_he': float,
                },
                ...
            ],
            'totales_por_dia': {date1: {'A': 50, 'F': 2, ...}, ...},
            'totales_globales': {'A': N, 'F': N, ...},
        }
    """
    from asistencia.models import RegistroTareo, RegistroPapeleta
    from personal.models import Personal

    fechas = _rango_fechas(desde, hasta)
    if not fechas:
        return {
            'desde': desde, 'hasta': hasta, 'fechas': [],
            'trabajadores': [], 'totales_por_dia': {}, 'totales_globales': {},
        }

    # ── 1. Personal filtrado ──
    personal_qs = Personal.objects.filter(estado='Activo').select_related(
        'empresa', 'subarea', 'subarea__area',
    )
    if empresa_ids:
        empresa_ids = [int(e) for e in empresa_ids if str(e).strip()]
        if empresa_ids:
            personal_qs = personal_qs.filter(empresa_id__in=empresa_ids)
    if grupo_tareo:
        personal_qs = personal_qs.filter(grupo_tareo=grupo_tareo)
    if subarea_id:
        personal_qs = personal_qs.filter(subarea_id=subarea_id)
    elif area_id:
        personal_qs = personal_qs.filter(subarea__area_id=area_id)

    personal_qs = personal_qs.order_by('apellidos_nombres')
    if limite_trabajadores:
        personal_qs = personal_qs[:limite_trabajadores]

    personal_list = list(personal_qs)
    personal_ids = [p.id for p in personal_list]

    if not personal_ids:
        return {
            'desde': desde, 'hasta': hasta, 'fechas': fechas,
            'trabajadores': [], 'totales_por_dia': {f: defaultdict(int) for f in fechas},
            'totales_globales': defaultdict(int),
        }

    # ── 2. RegistroTareo bulk (deduplicado por personal+fecha: max importacion_id) ──
    tareo_rows = list(
        RegistroTareo.objects
        .filter(personal_id__in=personal_ids, fecha__gte=desde, fecha__lte=hasta)
        .values('personal_id', 'fecha', 'codigo_dia', 'horas_efectivas',
                'he_25', 'he_35', 'he_100', 'importacion_id')
        .order_by('personal_id', 'fecha', '-importacion_id')
    )

    # Mantener solo el de mayor importacion_id por (personal, fecha)
    tareo_map: dict[tuple[int, date], dict] = {}
    for r in tareo_rows:
        key = (r['personal_id'], r['fecha'])
        if key not in tareo_map:
            tareo_map[key] = r

    # ── 3. Papeletas bulk ──
    papeleta_rows = RegistroPapeleta.objects.filter(
        personal_id__in=personal_ids,
        estado__in=['APROBADA', 'EJECUTADA', 'PENDIENTE'],
        fecha_inicio__lte=hasta,
        fecha_fin__gte=desde,
    ).values('personal_id', 'tipo_permiso', 'fecha_inicio', 'fecha_fin')

    papeleta_map: dict[tuple[int, date], str] = {}
    for p in papeleta_rows:
        d_ini = max(p['fecha_inicio'], desde)
        d_fin = min(p['fecha_fin'], hasta)
        estado_pivote = _map_tipo_papeleta(p['tipo_permiso'])
        d = d_ini
        while d <= d_fin:
            key = (p['personal_id'], d)
            # Si ya hay papeleta para ese día, mantener (primera gana).
            if key not in papeleta_map:
                papeleta_map[key] = estado_pivote
            d += timedelta(days=1)

    # ── 4. Construir filas ──
    trabajadores = []
    totales_por_dia: dict[date, dict] = {f: defaultdict(int) for f in fechas}
    totales_globales: dict = defaultdict(int)

    for p in personal_list:
        dias = {}
        total_trab = 0
        total_falt = 0
        total_tard = 0
        total_vac = 0
        total_perm = 0
        total_descanso = 0
        total_horas = Decimal('0')
        total_he = Decimal('0')

        for f in fechas:
            key = (p.id, f)
            estado = ESTADO_VACIO

            tareo = tareo_map.get(key)
            if tareo:
                estado = _map_codigo_tareo(tareo['codigo_dia'])
                try:
                    total_horas += Decimal(tareo['horas_efectivas'] or 0)
                except Exception:
                    pass
                try:
                    total_he += (
                        Decimal(tareo['he_25'] or 0)
                        + Decimal(tareo['he_35'] or 0)
                        + Decimal(tareo['he_100'] or 0)
                    )
                except Exception:
                    pass

            # Papeleta sobreescribe falta/vacío (justifica el día)
            pap = papeleta_map.get(key)
            if pap and estado in (ESTADO_FALTA, ESTADO_VACIO):
                estado = pap
            # Si la papeleta es vacaciones explícitas, también pisa "asistió" ambiguo
            elif pap == ESTADO_VACACIONES:
                estado = ESTADO_VACACIONES

            dias[f] = estado

            # Acumular
            if estado == ESTADO_ASISTIO:
                total_trab += 1
            elif estado == ESTADO_TARDANZA:
                total_trab += 1
                total_tard += 1
            elif estado == ESTADO_FALTA:
                total_falt += 1
            elif estado == ESTADO_VACACIONES:
                total_vac += 1
            elif estado == ESTADO_PERMISO:
                total_perm += 1
            elif estado == ESTADO_DESCANSO:
                total_descanso += 1

            totales_por_dia[f][estado] += 1
            totales_globales[estado] += 1

        trabajadores.append({
            'personal': p,
            'empresa_nombre': p.empresa.nombre_comercial if p.empresa and getattr(p.empresa, 'nombre_comercial', None) else (
                p.empresa.razon_social if p.empresa else '—'
            ),
            'dias': dias,
            'total_trabajados': total_trab,
            'total_faltas': total_falt,
            'total_tardanzas': total_tard,
            'total_vacaciones': total_vac,
            'total_permisos': total_perm,
            'total_descansos': total_descanso,
            'total_horas': float(total_horas),
            'total_he': float(total_he),
        })

    return {
        'desde': desde,
        'hasta': hasta,
        'fechas': fechas,
        'trabajadores': trabajadores,
        'totales_por_dia': totales_por_dia,
        'totales_globales': totales_globales,
    }


def construir_kpis(desde: date, hasta: date, empresa_ids: Iterable[int] | None = None) -> dict:
    """
    KPIs ejecutivos cross-empresa para panel.

    Returns:
        {
            'total_trabajadores': N,
            'total_dias_prog': N,
            'dias_asistidos': N,
            'dias_falta': N,
            'dias_tardanza': N,
            'tasa_asistencia': %,
            'tasa_puntualidad': %,
            'tasa_ausentismo': %,
            'total_horas': float,
            'total_he': float,
            'tendencia_diaria': [{'fecha': 'dd/mm', 'presentes': N, 'faltas': N}, ...],
            'distribucion_papeletas': [{'tipo': str, 'total': N}, ...],
            'top_tardanzas': [{'nombre': str, 'dni': str, 'total': N}, ...],
            'top_he': [{'nombre': str, 'dni': str, 'total_he': float}, ...],
        }
    """
    from asistencia.models import RegistroTareo, RegistroPapeleta
    from personal.models import Personal
    from django.db.models import Count, Sum

    empresa_ids_list = None
    if empresa_ids:
        empresa_ids_list = [int(e) for e in empresa_ids if str(e).strip()]

    trab_qs = Personal.objects.filter(estado='Activo')
    if empresa_ids_list:
        trab_qs = trab_qs.filter(empresa_id__in=empresa_ids_list)
    total_trabajadores = trab_qs.count()

    # Tareo del rango
    tareo_qs = RegistroTareo.objects.filter(
        fecha__gte=desde, fecha__lte=hasta,
        personal__isnull=False,
    )
    if empresa_ids_list:
        tareo_qs = tareo_qs.filter(personal__empresa_id__in=empresa_ids_list)

    total_dias_prog = tareo_qs.count()
    dias_asistidos = tareo_qs.filter(
        codigo_dia__in=['T', 'NOR', 'TR', 'A', 'CDT', 'CPF', 'LCG', 'ATM', 'CHE', 'LIM', 'SS']
    ).count()
    dias_falta = tareo_qs.filter(codigo_dia__in=['F', 'FA']).count()
    dias_tardanza = tareo_qs.filter(codigo_dia='T').count()

    tasa_asistencia = round(dias_asistidos / total_dias_prog * 100, 1) if total_dias_prog else 0
    tasa_ausentismo = round(dias_falta / total_dias_prog * 100, 1) if total_dias_prog else 0
    tasa_puntualidad = round(
        (dias_asistidos - dias_tardanza) / dias_asistidos * 100, 1
    ) if dias_asistidos else 0

    # Horas totales y HE
    horas_agg = tareo_qs.aggregate(
        h=Sum('horas_efectivas'), he25=Sum('he_25'),
        he35=Sum('he_35'), he100=Sum('he_100'),
    )
    total_horas = float(horas_agg['h'] or 0)
    total_he = float((horas_agg['he25'] or 0) + (horas_agg['he35'] or 0) + (horas_agg['he100'] or 0))

    # Tendencia diaria
    tendencia_raw = list(
        tareo_qs.values('fecha')
        .annotate(
            presentes=Count('id', filter=Q(codigo_dia__in=['T', 'NOR', 'TR', 'A', 'CDT', 'CPF', 'LCG', 'ATM', 'CHE', 'LIM'])),
            faltas=Count('id', filter=Q(codigo_dia__in=['F', 'FA'])),
        )
        .order_by('fecha')
    )
    tendencia_diaria = [
        {'fecha': r['fecha'].strftime('%d/%m'), 'presentes': r['presentes'], 'faltas': r['faltas']}
        for r in tendencia_raw
    ]

    # Distribución de papeletas
    pap_qs = RegistroPapeleta.objects.filter(
        fecha_inicio__lte=hasta,
        fecha_fin__gte=desde,
        estado__in=['APROBADA', 'EJECUTADA'],
    )
    if empresa_ids_list:
        pap_qs = pap_qs.filter(personal__empresa_id__in=empresa_ids_list)
    dist_pap_raw = list(
        pap_qs.values('tipo_permiso').annotate(total=Count('id')).order_by('-total')
    )
    # Resolver display
    from asistencia.models import RegistroPapeleta as _RP
    tipo_display = dict(_RP.TIPO_PERMISO_CHOICES)
    distribucion_papeletas = [
        {'tipo': tipo_display.get(r['tipo_permiso'], r['tipo_permiso']), 'total': r['total']}
        for r in dist_pap_raw
    ]

    # Top 10 tardanzas
    top_tardanzas_raw = list(
        tareo_qs.filter(codigo_dia='T')
        .values('personal__apellidos_nombres', 'personal__nro_doc')
        .annotate(total=Count('id'))
        .order_by('-total')[:10]
    )
    top_tardanzas = [
        {'nombre': r['personal__apellidos_nombres'] or '—',
         'dni': r['personal__nro_doc'] or '—',
         'total': r['total']}
        for r in top_tardanzas_raw
    ]

    # Top 10 horas extra
    top_he_raw = list(
        tareo_qs.values('personal__apellidos_nombres', 'personal__nro_doc')
        .annotate(he=Sum('he_25') + Sum('he_35') + Sum('he_100'))
        .filter(he__gt=0)
        .order_by('-he')[:10]
    )
    top_he = [
        {'nombre': r['personal__apellidos_nombres'] or '—',
         'dni': r['personal__nro_doc'] or '—',
         'total_he': float(r['he'] or 0)}
        for r in top_he_raw
    ]

    return {
        'desde': desde, 'hasta': hasta,
        'total_trabajadores': total_trabajadores,
        'total_dias_prog': total_dias_prog,
        'dias_asistidos': dias_asistidos,
        'dias_falta': dias_falta,
        'dias_tardanza': dias_tardanza,
        'tasa_asistencia': tasa_asistencia,
        'tasa_puntualidad': tasa_puntualidad,
        'tasa_ausentismo': tasa_ausentismo,
        'total_horas': round(total_horas, 1),
        'total_he': round(total_he, 1),
        'tendencia_diaria': tendencia_diaria,
        'distribucion_papeletas': distribucion_papeletas,
        'top_tardanzas': top_tardanzas,
        'top_he': top_he,
    }
