"""
Vistas del módulo Tareo — Vista RCO.
"""
import calendar
from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, F as DbF, Q, Sum
from django.http import JsonResponse
from django.shortcuts import render

from asistencia.views._common import solo_admin, _get_importacion_activa


# ---------------------------------------------------------------------------
# VISTA RCO — Tabla detalle con HE 25/35/100
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def vista_rco(request):
    """Tabla detalle de horas extra para personal RCO (navegación por período mes/año)."""
    from asistencia.models import RegistroTareo

    MESES_ES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
                'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
    MESES = [(i + 1, nombre) for i, nombre in enumerate(MESES_ES)]

    hoy = date.today()
    anio_sel = int(request.GET.get('anio', hoy.year))
    mes_sel  = int(request.GET.get('mes',  hoy.month))

    anios_disponibles = sorted(
        set(RegistroTareo.objects.filter(grupo='RCO')
            .values_list('fecha__year', flat=True)),
        reverse=True
    ) or [hoy.year]

    mes_ini = date(anio_sel, mes_sel, 1)
    mes_fin = date(anio_sel, mes_sel, calendar.monthrange(anio_sel, mes_sel)[1])

    buscar  = request.GET.get('buscar', '').strip()
    solo_he = request.GET.get('solo_he', '') == '1'

    # Base queryset for the selected period
    qs_base = RegistroTareo.objects.filter(
        grupo='RCO', fecha__gte=mes_ini, fecha__lte=mes_fin
    ).exclude(
        personal__fecha_cese__isnull=False, fecha__gt=DbF('personal__fecha_cese')
    ).exclude(
        personal__fecha_alta__isnull=False, fecha__lt=DbF('personal__fecha_alta')
    )

    # KPIs from full period (no text filter)
    kpi = qs_base.aggregate(
        personas   = Count('dni', distinct=True),
        he_25_sum  = Sum('he_25'),
        he_35_sum  = Sum('he_35'),
        he_100_sum = Sum('he_100'),
        dias_reg   = Count('id'),
    )
    kpi['he_25_sum']  = kpi['he_25_sum']  or Decimal('0')
    kpi['he_35_sum']  = kpi['he_35_sum']  or Decimal('0')
    kpi['he_100_sum'] = kpi['he_100_sum'] or Decimal('0')
    kpi['he_total']   = kpi['he_25_sum'] + kpi['he_35_sum'] + kpi['he_100_sum']

    # Apply text search filter for tables
    qs_filtrado = qs_base
    if buscar:
        qs_filtrado = qs_filtrado.filter(
            Q(dni__icontains=buscar) | Q(nombre_archivo__icontains=buscar)
        )

    # Detail rows (+ solo_he filter)
    qs = qs_filtrado.order_by('nombre_archivo', 'fecha')
    if solo_he:
        qs = qs.filter(Q(he_25__gt=0) | Q(he_35__gt=0) | Q(he_100__gt=0))

    # Summary by person (buscar applied, solo_he NOT applied to keep all totals)
    resumen = list(
        qs_filtrado
        .values('dni', 'nombre_archivo', 'personal_id')
        .annotate(
            total_he_25=Sum('he_25'),
            total_he_35=Sum('he_35'),
            total_he_100=Sum('he_100'),
            total_horas=Sum('horas_marcadas'),
            dias_trabajados=Count('id', filter=Q(codigo_dia__in=['T', 'NOR', 'TR', 'A', 'CDT', 'CPF', 'LCG', 'ATM', 'CHE', 'LIM', 'SS'])),
            dias_fa=Count('id', filter=Q(codigo_dia__in=['FA', 'F']) & ~Q(condicion__in=['LOCAL', 'LIMA', ''], dia_semana=6)),
            dias_dl=Count('id', filter=Q(codigo_dia__in=['DL', 'DLA'])),
            dias_vac=Count('id', filter=Q(codigo_dia__in=['VAC', 'V'])),
        )
        .order_by('nombre_archivo')
    )
    for r in resumen:
        r['total_he'] = (r['total_he_25'] or Decimal('0')) + \
                        (r['total_he_35'] or Decimal('0')) + \
                        (r['total_he_100'] or Decimal('0'))

    totales = qs_filtrado.aggregate(
        t_he_25=Sum('he_25'),
        t_he_35=Sum('he_35'),
        t_he_100=Sum('he_100'),
        t_horas=Sum('horas_marcadas'),
    )
    totales['t_he_total'] = (totales['t_he_25'] or Decimal('0')) + \
                             (totales['t_he_35'] or Decimal('0')) + \
                             (totales['t_he_100'] or Decimal('0'))

    context = {
        'titulo': f'RCO — Horas Extra {MESES_ES[mes_sel-1]} {anio_sel}',
        'anio_sel': anio_sel,
        'mes_sel': mes_sel,
        'mes_nombre': MESES_ES[mes_sel - 1],
        'meses': MESES,
        'anios_disponibles': anios_disponibles,
        'mes_ini': mes_ini,
        'mes_fin': mes_fin,
        'kpi': kpi,
        'registros': qs,
        'resumen': resumen,
        'totales': totales,
        'buscar': buscar,
        'solo_he': solo_he,
        'total_registros': qs.count(),
    }
    return render(request, 'asistencia/vista_rco.html', context)


@login_required
@solo_admin
def ajax_rco_data(request):
    """JSON con resumen HE por persona para personal RCO."""
    from asistencia.models import RegistroTareo

    importacion_id = request.GET.get('importacion')
    importacion = _get_importacion_activa('RELOJ', importacion_id)

    if not importacion:
        return JsonResponse({'error': 'Sin importación activa'}, status=404)

    data = list(
        RegistroTareo.objects
        .filter(importacion=importacion, grupo='RCO')
        .values('dni', 'nombre_archivo')
        .annotate(
            total_he_25=Sum('he_25'),
            total_he_35=Sum('he_35'),
            total_he_100=Sum('he_100'),
            total_horas=Sum('horas_marcadas'),
        )
        .order_by('nombre_archivo')
    )

    for row in data:
        row['total_he_25'] = float(row['total_he_25'] or 0)
        row['total_he_35'] = float(row['total_he_35'] or 0)
        row['total_he_100'] = float(row['total_he_100'] or 0)
        row['total_horas'] = float(row['total_horas'] or 0)
        row['total_he'] = row['total_he_25'] + row['total_he_35'] + row['total_he_100']

    return JsonResponse({'total': len(data), 'data': data})
