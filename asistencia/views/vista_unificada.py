"""
Vista unificada de asistencia — TODOS / STAFF / RCO en una sola URL.
"""
import calendar
from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import render

from asistencia.views._common import solo_admin, _qs_staff_dedup

MESES_ES = [
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
]
MESES = [(i + 1, n) for i, n in enumerate(MESES_ES)]


def _d(v):
    return v or Decimal('0')


def _staff_resumen(mes_ini, mes_fin, buscar=''):
    """Resumen por persona para STAFF (deduplicado)."""
    from asistencia.models import BancoHoras
    from django.db.models import F as DbF

    qs = (
        _qs_staff_dedup(mes_ini, mes_fin)
        .exclude(personal__fecha_cese__isnull=False, fecha__gt=DbF('personal__fecha_cese'))
        .exclude(personal__fecha_alta__isnull=False, fecha__lt=DbF('personal__fecha_alta'))
        .values('personal_id', 'personal__apellidos_nombres',
                'personal__nro_doc', 'personal__condicion')
        .annotate(
            dias_trabajados=Count('id', filter=Q(codigo_dia__in=[
                'T', 'NOR', 'TR', 'LCG', 'ATM', 'CDT', 'CPF', 'SS'])),
            dias_ss=Count('id', filter=Q(codigo_dia='SS')),
            dias_dl=Count('id', filter=Q(codigo_dia__in=['DL', 'DLA'])),
            dias_fa=Count('id', filter=Q(codigo_dia__in=['FA', 'F']) & ~Q(condicion__in=['LOCAL', 'LIMA', ''], dia_semana=6)),
            dias_vac=Count('id', filter=Q(codigo_dia__in=['VAC', 'V'])),
            he_25=Sum('he_25'),
            he_35=Sum('he_35'),
            he_100=Sum('he_100'),
        )
        .order_by('personal__apellidos_nombres')
    )

    if buscar:
        qs = qs.filter(
            Q(personal__apellidos_nombres__icontains=buscar) |
            Q(personal__nro_doc__icontains=buscar)
        )

    banco_map = {
        b['personal_id']: b['saldo_horas']
        for b in BancoHoras.objects.filter(
            periodo_anio=mes_ini.year, periodo_mes=mes_ini.month
        ).values('personal_id', 'saldo_horas')
    }

    rows = []
    for r in qs:
        pid = r['personal_id']
        he_total = _d(r['he_25']) + _d(r['he_35']) + _d(r['he_100'])
        rows.append({
            'personal_id': pid,
            'nombre': r['personal__apellidos_nombres'],
            'nro_doc': r['personal__nro_doc'],
            'condicion': r['personal__condicion'] or 'LOCAL',
            'grupo': 'STAFF',
            'dias_trabajados': r['dias_trabajados'],
            'dias_ss': r['dias_ss'],
            'dias_dl': r['dias_dl'],
            'dias_fa': r['dias_fa'],
            'dias_vac': r['dias_vac'],
            'he_25': _d(r['he_25']),
            'he_35': _d(r['he_35']),
            'he_100': _d(r['he_100']),
            'he_total': he_total,
            'banco_saldo': banco_map.get(pid),
        })
    return rows


def _rco_resumen(mes_ini, mes_fin, buscar=''):
    """Resumen por persona para RCO."""
    from asistencia.models import RegistroTareo
    from django.db.models import F as DbF

    qs = (
        RegistroTareo.objects
        .filter(grupo='RCO', fecha__gte=mes_ini, fecha__lte=mes_fin)
        .exclude(personal__fecha_cese__isnull=False, fecha__gt=DbF('personal__fecha_cese'))
        .exclude(personal__fecha_alta__isnull=False, fecha__lt=DbF('personal__fecha_alta'))
        .values('personal_id', 'personal__apellidos_nombres',
                'personal__nro_doc', 'personal__condicion', 'dni', 'nombre_archivo')
        .annotate(
            dias_trabajados=Count('id', filter=Q(codigo_dia__in=['T', 'NOR', 'TR', 'A', 'CDT', 'CPF', 'LCG', 'ATM', 'CHE', 'LIM', 'SS'])),
            dias_fa=Count('id', filter=Q(codigo_dia__in=['FA', 'F']) & ~Q(condicion__in=['LOCAL', 'LIMA', ''], dia_semana=6)),
            he_25=Sum('he_25'),
            he_35=Sum('he_35'),
            he_100=Sum('he_100'),
        )
        .order_by('personal__apellidos_nombres', 'nombre_archivo')
    )

    if buscar:
        qs = qs.filter(
            Q(personal__apellidos_nombres__icontains=buscar) |
            Q(personal__nro_doc__icontains=buscar) |
            Q(dni__icontains=buscar) |
            Q(nombre_archivo__icontains=buscar)
        )

    rows = []
    for r in qs:
        he_total = _d(r['he_25']) + _d(r['he_35']) + _d(r['he_100'])
        rows.append({
            'personal_id': r['personal_id'],
            'nombre': r['personal__apellidos_nombres'] or r['nombre_archivo'],
            'nro_doc': r['personal__nro_doc'] or r['dni'],
            'condicion': r['personal__condicion'] or 'LOCAL',
            'grupo': 'RCO',
            'dias_trabajados': r['dias_trabajados'],
            'dias_ss': 0,
            'dias_dl': 0,
            'dias_fa': r['dias_fa'],
            'dias_vac': 0,
            'he_25': _d(r['he_25']),
            'he_35': _d(r['he_35']),
            'he_100': _d(r['he_100']),
            'he_total': he_total,
            'banco_saldo': None,
        })
    return rows


def _totales(rows):
    return {
        'personas': len(rows),
        'dias_trabajados': sum(r['dias_trabajados'] for r in rows),
        'dias_fa': sum(r['dias_fa'] for r in rows),
        'he_25': sum(r['he_25'] for r in rows),
        'he_35': sum(r['he_35'] for r in rows),
        'he_100': sum(r['he_100'] for r in rows),
        'he_total': sum(r['he_total'] for r in rows),
    }


@login_required
@solo_admin
def vista_unificada(request):
    """Vista unificada TODOS | STAFF | RCO con tabs por período."""
    from asistencia.models import RegistroTareo

    hoy = date.today()
    anio_sel = int(request.GET.get('anio', hoy.year))
    mes_sel = int(request.GET.get('mes', hoy.month))
    grupo_sel = request.GET.get('grupo', 'TODOS').upper()
    buscar = request.GET.get('buscar', '').strip()

    if grupo_sel not in ('TODOS', 'STAFF', 'RCO'):
        grupo_sel = 'TODOS'

    mes_ini = date(anio_sel, mes_sel, 1)
    mes_fin = date(anio_sel, mes_sel, calendar.monthrange(anio_sel, mes_sel)[1])

    # Años disponibles (unión STAFF + RCO)
    _a_staff = set(RegistroTareo.objects.filter(grupo='STAFF')
                   .values_list('fecha__year', flat=True))
    _a_rco = set(RegistroTareo.objects.filter(grupo='RCO')
                 .values_list('fecha__year', flat=True))
    anios_disponibles = sorted(_a_staff | _a_rco | {hoy.year}, reverse=True)

    # Construir filas según tab
    staff_rows = _staff_resumen(mes_ini, mes_fin, buscar) if grupo_sel in ('TODOS', 'STAFF') else []
    rco_rows = _rco_resumen(mes_ini, mes_fin, buscar) if grupo_sel in ('TODOS', 'RCO') else []

    if grupo_sel == 'TODOS':
        rows = staff_rows + rco_rows
        rows.sort(key=lambda r: r['nombre'] or '')
    elif grupo_sel == 'STAFF':
        rows = staff_rows
    else:
        rows = rco_rows

    totales = _totales(rows)

    # KPI rápidos del período (para las cards superiores)
    qs_all = RegistroTareo.objects.filter(fecha__gte=mes_ini, fecha__lte=mes_fin)
    if grupo_sel != 'TODOS':
        qs_all = qs_all.filter(grupo=grupo_sel)

    kpi = qs_all.aggregate(
        total_he_25=Sum('he_25'),
        total_he_35=Sum('he_35'),
        total_he_100=Sum('he_100'),
        total_fa=Count('id', filter=Q(codigo_dia__in=['FA', 'F'])),
    )

    context = {
        'titulo': f'{"Todos" if grupo_sel == "TODOS" else grupo_sel} — {MESES_ES[mes_sel - 1]} {anio_sel}',
        'anio_sel': anio_sel,
        'mes_sel': mes_sel,
        'mes_nombre': MESES_ES[mes_sel - 1],
        'meses': MESES,
        'anios_disponibles': anios_disponibles,
        'grupo_sel': grupo_sel,
        'buscar': buscar,
        'rows': rows,
        'totales': totales,
        'kpi': {
            'he_25': _d(kpi['total_he_25']),
            'he_35': _d(kpi['total_he_35']),
            'he_100': _d(kpi['total_he_100']),
            'he_total': _d(kpi['total_he_25']) + _d(kpi['total_he_35']) + _d(kpi['total_he_100']),
            'faltas': kpi['total_fa'] or 0,
        },
        'mes_ini': mes_ini,
        'mes_fin': mes_fin,
    }
    return render(request, 'asistencia/vista_unificada.html', context)
