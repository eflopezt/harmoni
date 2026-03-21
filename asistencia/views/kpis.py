"""
Vistas del módulo Tareo — Dashboard KPIs.
"""
import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import render

from asistencia.views._common import solo_admin

# Códigos de permiso/licencia en RegistroTareo
CODIGOS_PERMISO = ['PL', 'PC', 'PM', 'PE', 'LCG', 'LSG', 'LF', 'LP', 'LM',
                   'CHE', 'DL', 'DLA', 'B', 'CAP', 'SUS', 'TR']


# ---------------------------------------------------------------------------
# DASHBOARD KPIs (mejorado)
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def kpi_dashboard_view(request):
    """Dashboard de KPIs de asistencia con gráficas."""
    from asistencia.models import BancoHoras, RegistroTareo, TareoImportacion

    hoy = date.today()
    anio = int(request.GET.get('anio', hoy.year))
    mes = int(request.GET.get('mes', hoy.month))

    from asistencia.models import ConfiguracionSistema
    config = ConfiguracionSistema.get()
    inicio, fin = config.get_ciclo_asistencia(anio, mes)

    from django.db.models import F as DbF
    qs = RegistroTareo.objects.filter(fecha__gte=inicio, fecha__lte=fin).exclude(
        personal__fecha_cese__isnull=False, fecha__gt=DbF('personal__fecha_cese')
    ).exclude(
        personal__fecha_alta__isnull=False, fecha__lt=DbF('personal__fecha_alta')
    )

    # KPIs principales
    total_dias_prog = qs.count()
    dias_trabajados = qs.filter(codigo_dia__in=['T', 'NOR', 'TR', 'A', 'CDT', 'CPF', 'LCG', 'ATM', 'CHE', 'LIM']).count()
    # Faltas reales: excluir domingos LOCAL (son DS, no faltas)
    faltas = qs.filter(codigo_dia__in=['FA', 'F']).exclude(condicion__in=['LOCAL', 'LIMA', ''], dia_semana=6).count()
    vacaciones = qs.filter(codigo_dia__in=['VAC', 'V']).count()
    dm = qs.filter(codigo_dia='DM').count()
    dl_bajadas = qs.filter(codigo_dia__in=['DL', 'DLA', 'B']).count()

    tasa_asistencia = round(dias_trabajados / total_dias_prog * 100, 1) if total_dias_prog else 0
    tasa_absentismo = round(faltas / total_dias_prog * 100, 1) if total_dias_prog else 0

    # HE totales del ciclo HE
    inicio_he, fin_he = config.get_ciclo_he(anio, mes)
    qs_he = RegistroTareo.objects.filter(fecha__gte=inicio_he, fecha__lte=fin_he)
    he_totales = qs_he.aggregate(
        t25=Sum('he_25'), t35=Sum('he_35'), t100=Sum('he_100'))
    he_25_total = he_totales['t25'] or Decimal('0')
    he_35_total = he_totales['t35'] or Decimal('0')
    he_100_total = he_totales['t100'] or Decimal('0')

    # Por grupo
    staff_stats = qs.filter(grupo='STAFF').aggregate(
        dias=Count('id'),
        he25=Sum('he_25'), he35=Sum('he_35'),
    )
    staff_stats['faltas'] = qs.filter(grupo='STAFF', codigo_dia__in=['FA', 'F']).exclude(condicion__in=['LOCAL', 'LIMA', ''], dia_semana=6).count()
    rco_stats = qs.filter(grupo='RCO').aggregate(
        dias=Count('id'),
        he25=Sum('he_25'), he35=Sum('he_35'), he100=Sum('he_100'),
    )
    rco_stats['faltas'] = qs.filter(grupo='RCO', codigo_dia__in=['FA', 'F']).exclude(condicion__in=['LOCAL', 'LIMA', ''], dia_semana=6).count()

    # Tendencia diaria del ciclo (para gráfica de línea principal)
    tendencia = list(
        qs.values('fecha')
        .annotate(
            trabajados=Count('id', filter=Q(codigo_dia__in=['T', 'NOR', 'TR', 'A', 'CDT', 'CPF', 'LCG', 'ATM', 'CHE', 'LIM'])),
            ausentes=Count('id', filter=Q(codigo_dia__in=['FA', 'F']) & ~Q(condicion__in=['LOCAL', 'LIMA', ''], dia_semana=6)),
        )
        .order_by('fecha')
    )
    for t in tendencia:
        t['fecha'] = t['fecha'].strftime('%d/%m')

    # Top 10 ausentes del mes
    top_ausentes = list(
        qs.filter(codigo_dia__in=['FA', 'F']).exclude(condicion__in=['LOCAL', 'LIMA', ''], dia_semana=6)
        .values('personal__apellidos_nombres', 'personal__nro_doc', 'grupo')
        .annotate(total_faltas=Count('id'))
        .order_by('-total_faltas')[:10]
    )

    # Banco de horas STAFF - resumen
    banco_mes = BancoHoras.objects.filter(periodo_anio=anio, periodo_mes=mes).aggregate(
        personas=Count('id'),
        saldo=Sum('saldo_horas'),
        acum=Sum('he_25_acumuladas') + Sum('he_35_acumuladas'),
    )

    # ── NUEVOS KPIs ─────────────────────────────────────────────────────────

    # 1. Tendencia últimos 7 días
    tendencia_7d_json = '[]'
    try:
        fecha_7d_ini = hoy - timedelta(days=6)
        qs_7d = RegistroTareo.objects.filter(
            fecha__gte=fecha_7d_ini,
            fecha__lte=hoy,
            personal__estado='Activo',
        )
        tendencia_7d_raw = list(
            qs_7d.values('fecha')
            .annotate(
                presentes=Count('id', filter=Q(codigo_dia__in=['T', 'NOR', 'TR', 'A', 'CDT', 'CPF', 'LCG', 'ATM', 'CHE', 'LIM'])),
                faltas_dia=Count('id', filter=Q(codigo_dia__in=['FA', 'F']) & ~Q(condicion__in=['LOCAL', 'LIMA', ''], dia_semana=6)),
                permisos=Count('id', filter=Q(codigo_dia__in=CODIGOS_PERMISO)),
            )
            .order_by('fecha')
        )
        tendencia_7d = [
            {
                'fecha': row['fecha'].strftime('%-d/%m') if hasattr(row['fecha'], 'strftime') else str(row['fecha']),
                'presentes': row['presentes'],
                'faltas': row['faltas_dia'],
                'permisos': row['permisos'],
            }
            for row in tendencia_7d_raw
        ]
        tendencia_7d_json = json.dumps(tendencia_7d, default=str)
    except Exception:
        tendencia_7d_json = '[]'

    # 2. Top 5 áreas por faltas del mes calendario
    top_faltas_area = []
    top_faltas_area_json = '[]'
    try:
        qs_mes_cal = RegistroTareo.objects.filter(
            fecha__month=mes,
            fecha__year=anio,
            codigo_dia__in=['FA', 'F'],
            personal__isnull=False,
        ).exclude(condicion__in=['LOCAL', 'LIMA', ''], dia_semana=6)
        top_raw = list(
            qs_mes_cal
            .values('personal__subarea__area__nombre')
            .annotate(total=Count('id'))
            .order_by('-total')[:5]
        )
        top_faltas_area = [
            {
                'area': row['personal__subarea__area__nombre'] or 'Sin área',
                'total': row['total'],
            }
            for row in top_raw
        ]
        # Calcular ancho de barra relativo al máximo
        max_val = max((r['total'] for r in top_faltas_area), default=1)
        for r in top_faltas_area:
            r['pct'] = round(r['total'] / max_val * 100)
        top_faltas_area_json = json.dumps(top_faltas_area, default=str)
    except Exception:
        top_faltas_area = []
        top_faltas_area_json = '[]'

    # 3. HE por semana del mes (semanas del mes calendario)
    he_por_semana_json = '[]'
    try:
        qs_he_mes = RegistroTareo.objects.filter(
            fecha__month=mes,
            fecha__year=anio,
        )
        he_dias = list(
            qs_he_mes
            .values('fecha')
            .annotate(
                he25_d=Sum('he_25'),
                he35_d=Sum('he_35'),
                he100_d=Sum('he_100'),
            )
            .order_by('fecha')
        )
        # Agrupar por semana del mes (semana 1 = días 1-7, semana 2 = días 8-14, ...)
        semanas: dict[str, float] = {'S1': 0.0, 'S2': 0.0, 'S3': 0.0, 'S4': 0.0, 'S5': 0.0}
        for row in he_dias:
            dia_num = row['fecha'].day
            if dia_num <= 7:
                s_key = 'S1'
            elif dia_num <= 14:
                s_key = 'S2'
            elif dia_num <= 21:
                s_key = 'S3'
            elif dia_num <= 28:
                s_key = 'S4'
            else:
                s_key = 'S5'
            total_he = (
                float(row['he25_d'] or 0)
                + float(row['he35_d'] or 0)
                + float(row['he100_d'] or 0)
            )
            semanas[s_key] += total_he

        he_por_semana = [
            {'semana': k, 'total_he': round(v, 1)}
            for k, v in semanas.items()
            if v > 0
        ]
        he_por_semana_json = json.dumps(he_por_semana, default=str)
    except Exception:
        he_por_semana_json = '[]'

    # 4. Tasa de asistencia STAFF vs RCO del mes
    asistencia_por_grupo = []
    asistencia_por_grupo_json = '[]'
    try:
        def _tasa_grupo(grupo_nombre):
            g_qs = RegistroTareo.objects.filter(
                fecha__month=mes,
                fecha__year=anio,
                grupo=grupo_nombre,
            )
            total_g = g_qs.count()
            presentes_g = g_qs.filter(codigo_dia__in=['T', 'NOR', 'TR', 'A', 'CDT', 'CPF', 'LCG', 'ATM', 'CHE', 'LIM']).count()
            faltas_g = g_qs.filter(codigo_dia__in=['FA', 'F']).exclude(condicion__in=['LOCAL', 'LIMA', ''], dia_semana=6).count()
            tasa = round(presentes_g / total_g * 100, 1) if total_g else 0
            return {
                'grupo': grupo_nombre,
                'tasa': tasa,
                'presentes': presentes_g,
                'faltas': faltas_g,
                'total': total_g,
            }

        asistencia_por_grupo = [_tasa_grupo('STAFF'), _tasa_grupo('RCO')]
        asistencia_por_grupo_json = json.dumps(asistencia_por_grupo, default=str)
    except Exception:
        asistencia_por_grupo = []
        asistencia_por_grupo_json = '[]'

    # ── Contexto ────────────────────────────────────────────────────────────

    MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
             'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

    context = {
        'titulo': f'Dashboard KPIs — {MESES[mes-1]} {anio}',
        'anio': anio, 'mes': mes,
        'mes_nombre': MESES[mes - 1],
        'periodo_asist': f'{inicio.strftime("%d/%m/%Y")} → {fin.strftime("%d/%m/%Y")}',
        'periodo_he': f'{inicio_he.strftime("%d/%m/%Y")} → {fin_he.strftime("%d/%m/%Y")}',
        # KPIs principales
        'total_dias_prog': total_dias_prog,
        'dias_trabajados': dias_trabajados,
        'faltas': faltas,
        'vacaciones': vacaciones,
        'dm': dm,
        'dl_bajadas': dl_bajadas,
        'tasa_asistencia': tasa_asistencia,
        'tasa_absentismo': tasa_absentismo,
        # HE
        'he_25_total': he_25_total,
        'he_35_total': he_35_total,
        'he_100_total': he_100_total,
        'he_total': he_25_total + he_35_total + he_100_total,
        # Por grupo
        'staff_stats': staff_stats,
        'rco_stats': rco_stats,
        # Gráficas existentes
        'tendencia_json': tendencia,
        'top_ausentes': top_ausentes,
        # Banco
        'banco_mes': banco_mes,
        # Selectores
        'anios': list(range(hoy.year - 2, hoy.year + 1)),
        'meses': [(i, m) for i, m in enumerate(MESES, 1)],
        # ── Nuevos KPIs (JSON para Chart.js) ──
        'tendencia_7d_json': tendencia_7d_json,
        'top_faltas_area_json': top_faltas_area_json,
        'top_faltas_area': top_faltas_area,
        'he_por_semana_json': he_por_semana_json,
        'asistencia_por_grupo_json': asistencia_por_grupo_json,
        'asistencia_por_grupo': asistencia_por_grupo,
    }
    return render(request, 'asistencia/kpi_dashboard.html', context)
