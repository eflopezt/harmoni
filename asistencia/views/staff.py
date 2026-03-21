"""
Vistas del módulo Tareo — Vista STAFF.
"""
import calendar
from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.http import JsonResponse
from django.shortcuts import render

from asistencia.views._common import solo_admin, _get_importacion_activa, _qs_staff_dedup


# ---------------------------------------------------------------------------
# VISTA STAFF — Matriz persona × día
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def vista_staff(request):
    """
    Resumen mensual del personal STAFF.
    Muestra por persona: días trabajados, SS, DL, CHE, HE, saldo banco.
    Selector de año/mes. Click en persona → detalle diario.
    """
    from personal.models import Personal
    from asistencia.models import BancoHoras, RegistroTareo

    MESES_ES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
                'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
    MESES = [(i + 1, nombre) for i, nombre in enumerate(MESES_ES)]

    hoy = date.today()
    anio_sel = int(request.GET.get('anio', hoy.year))
    mes_sel  = int(request.GET.get('mes',  hoy.month))
    buscar   = request.GET.get('buscar', '').strip()

    anios_disponibles = sorted(
        set(RegistroTareo.objects.filter(grupo='STAFF')
            .values_list('fecha__year', flat=True)),
        reverse=True
    ) or [hoy.year]

    # Mes calendario seleccionado (para display de asistencia)
    mes_ini = date(anio_sel, mes_sel, 1)
    mes_fin = date(anio_sel, mes_sel, calendar.monthrange(anio_sel, mes_sel)[1])

    # Ciclo HE (solo referencia en encabezado)
    if mes_sel == 1:
        mes_ant, anio_ant = 12, anio_sel - 1
    else:
        mes_ant, anio_ant = mes_sel - 1, anio_sel
    ciclo_ini = date(anio_ant, mes_ant, 21)
    ciclo_fin = mes_fin

    # Resumen por persona para el mes calendario
    # Usa queryset deduplicado: 1 registro por (personal, fecha) → importación más reciente
    from django.db.models import F as DbF
    qs_base = _qs_staff_dedup(mes_ini, mes_fin).exclude(
        personal__fecha_cese__isnull=False, fecha__gt=DbF('personal__fecha_cese')
    ).exclude(
        personal__fecha_alta__isnull=False, fecha__lt=DbF('personal__fecha_alta')
    )
    qs_resumen = (
        qs_base
        .values('personal_id', 'personal__apellidos_nombres', 'personal__nro_doc',
                'personal__condicion', 'dni')
        .annotate(
            dias_trabajados = Count('id', filter=Q(codigo_dia__in=['T', 'NOR', 'TR', 'A', 'LCG', 'ATM', 'CDT', 'CPF', 'SS', 'CHE', 'LIM'])),
            dias_ss         = Count('id', filter=Q(codigo_dia='SS')),
            dias_dl         = Count('id', filter=Q(codigo_dia__in=['DL', 'DLA'])),
            dias_che        = Count('id', filter=Q(codigo_dia='CHE')),
            dias_vac        = Count('id', filter=Q(codigo_dia__in=['VAC', 'V'])),
            dias_dm         = Count('id', filter=Q(codigo_dia='DM')),
            dias_lsg        = Count('id', filter=Q(codigo_dia='LSG')),
            # Faltas: excluir domingos LOCAL (son DS, no faltas)
            dias_fa         = Count('id', filter=Q(codigo_dia__in=['FA', 'F']) & ~Q(condicion__in=['LOCAL', 'LIMA', ''], dia_semana=6)),
            he_25           = Sum('he_25'),
            he_35           = Sum('he_35'),
            he_100          = Sum('he_100'),
            total_horas_ef  = Sum('horas_efectivas'),
        )
        .order_by('personal__apellidos_nombres')
    )

    if buscar:
        qs_resumen = qs_resumen.filter(
            Q(personal__apellidos_nombres__icontains=buscar) |
            Q(personal__nro_doc__icontains=buscar)
        )

    # Banco de horas del mes seleccionado por persona
    banco_map = {
        b['personal_id']: b
        for b in BancoHoras.objects.filter(
            periodo_anio=anio_sel, periodo_mes=mes_sel
        ).values('personal_id', 'saldo_horas', 'he_compensadas',
                 'he_25_acumuladas', 'he_35_acumuladas')
    }

    # Combinar
    personas = []
    for r in qs_resumen:
        pid = r['personal_id']
        banco = banco_map.get(pid, {})
        personas.append({
            'personal_id': pid,
            'nombre': r['personal__apellidos_nombres'],
            'nro_doc': r['personal__nro_doc'],
            'condicion': r['personal__condicion'] or 'LOCAL',
            'dni': r['dni'],
            'dias_trabajados': r['dias_trabajados'],
            'dias_ss':  r['dias_ss'],
            'dias_dl':  r['dias_dl'],
            'dias_che': r['dias_che'],
            'dias_vac': r['dias_vac'],
            'dias_dm':  r['dias_dm'],
            'dias_lsg': r['dias_lsg'],
            'dias_fa':  r['dias_fa'],
            'he_25':  r['he_25']  or Decimal('0'),
            'he_35':  r['he_35']  or Decimal('0'),
            'he_100': r['he_100'] or Decimal('0'),
            'he_total': (r['he_25'] or Decimal('0')) + (r['he_35'] or Decimal('0')) + (r['he_100'] or Decimal('0')),
            'banco_saldo':       banco.get('saldo_horas', None),
            'banco_he_25':       banco.get('he_25_acumuladas', None),
            'banco_he_35':       banco.get('he_35_acumuladas', None),
            'banco_compensadas': banco.get('he_compensadas', None),
        })

    # Totales
    totales = {
        'personas':       len(personas),
        'dias_trabajados': sum(p['dias_trabajados'] for p in personas),
        'he_25':  sum(p['he_25']  for p in personas),
        'he_35':  sum(p['he_35']  for p in personas),
        'he_100': sum(p['he_100'] for p in personas),
        'he_total': sum(p['he_total'] for p in personas),
        'banco_saldo': sum(p['banco_saldo'] for p in personas if p['banco_saldo'] is not None),
        'dias_ss': sum(p['dias_ss'] for p in personas),
        'dias_fa': sum(p['dias_fa'] for p in personas),
    }

    context = {
        'titulo': f'STAFF — {MESES_ES[mes_sel - 1]} {anio_sel}',
        'anio_sel': anio_sel,
        'mes_sel': mes_sel,
        'mes_nombre': MESES_ES[mes_sel - 1],
        'meses': MESES,
        'anios_disponibles': anios_disponibles,
        'personas': personas,
        'totales': totales,
        'mes_ini': mes_ini,
        'mes_fin': mes_fin,
        'ciclo_ini': ciclo_ini,
        'ciclo_fin': ciclo_fin,
        'buscar': buscar,
    }
    return render(request, 'asistencia/vista_staff.html', context)


@login_required
@solo_admin
def ajax_staff_data(request):
    """JSON con datos STAFF para la matriz."""
    from asistencia.models import RegistroTareo

    importacion_id = request.GET.get('importacion')
    importacion = _get_importacion_activa('RELOJ', importacion_id)

    if not importacion:
        return JsonResponse({'error': 'Sin importación activa'}, status=404)

    data = list(
        RegistroTareo.objects
        .filter(importacion=importacion, grupo='STAFF')
        .values('dni', 'nombre_archivo', 'fecha', 'codigo_dia',
                'horas_marcadas', 'he_25', 'he_35', 'he_100')
        .order_by('nombre_archivo', 'fecha')
    )

    for row in data:
        row['fecha'] = row['fecha'].isoformat()
        row['horas_marcadas'] = float(row['horas_marcadas'] or 0)
        row['he_25'] = float(row['he_25'])
        row['he_35'] = float(row['he_35'])
        row['he_100'] = float(row['he_100'])

    return JsonResponse({
        'importacion': str(importacion),
        'total': len(data),
        'data': data,
    })
