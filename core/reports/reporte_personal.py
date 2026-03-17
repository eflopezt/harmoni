"""
Reporte Ejecutivo de Personal (PDF).

Genera un resumen de la plantilla:
- Headcount por area
- Distribucion por tipo de contrato
- Distribucion por genero
- Bandas salariales
"""
import logging
from decimal import Decimal

from django.db.models import Count, Sum, Q, Avg, Min, Max

from core.report_engine import HarmoniReport, _fmt, C_TEAL, C_RED_H, C_BLUE_H

logger = logging.getLogger('core.reports.personal')


def generar_reporte_personal(filtro_estado='Activo'):
    """
    Generate an HR summary PDF report.
    Returns PDF bytes.
    """
    from personal.models import Personal, Area

    qs = Personal.objects.select_related('subarea', 'subarea__area')
    if filtro_estado:
        qs = qs.filter(estado=filtro_estado)

    total = qs.count()
    masa_total = qs.aggregate(total=Sum('sueldo_base'))['total'] or Decimal('0')
    sueldo_prom = qs.aggregate(avg=Avg('sueldo_base'))['avg'] or Decimal('0')
    sueldo_min = qs.aggregate(mn=Min('sueldo_base'))['mn'] or Decimal('0')
    sueldo_max = qs.aggregate(mx=Max('sueldo_base'))['mx'] or Decimal('0')

    report = HarmoniReport(
        titulo='Reporte de Personal',
        subtitulo=f'Estado: {filtro_estado}' if filtro_estado else 'Todos',
    )
    report.add_header()

    # KPIs
    staff_count = qs.filter(grupo_tareo='STAFF').count()
    rco_count = qs.filter(grupo_tareo='RCO').count()
    report.add_kpi_row([
        ('Total Personal', str(total)),
        ('STAFF', str(staff_count)),
        ('RCO', str(rco_count)),
        ('Masa Salarial', f'S/ {_fmt(masa_total)}'),
    ])

    # ── Section 1: Headcount by Area ────────────────────────────────────
    report.add_section('Distribucion por Area')

    por_area = (
        qs.values('subarea__area__nombre')
        .annotate(total=Count('id'), masa=Sum('sueldo_base'))
        .order_by('-total')
    )

    area_rows = []
    for item in por_area:
        area_name = item['subarea__area__nombre'] or 'Sin Area'
        cnt = item['total']
        pct = round(cnt / total * 100, 1) if total else 0
        masa = item['masa'] or Decimal('0')
        area_rows.append([area_name, str(cnt), f'{pct}%', f'S/ {_fmt(masa)}'])

    usable = report.usable_w
    report.add_table(
        ['Area', 'Empleados', '% del Total', 'Masa Salarial'],
        area_rows,
        widths=[usable * 0.35, usable * 0.15, usable * 0.15, usable * 0.35],
        right_align_cols={1, 3},
        center_align_cols={2},
        totals_row=['TOTAL', str(total), '100%', f'S/ {_fmt(masa_total)}'],
    )

    # ── Section 2: Contract Types ───────────────────────────────────────
    report.add_section('Tipo de Contrato')

    por_contrato = (
        qs.values('tipo_contrato')
        .annotate(total=Count('id'))
        .order_by('-total')
    )

    contrato_rows = []
    for item in por_contrato:
        tc = item['tipo_contrato'] or 'No especificado'
        cnt = item['total']
        pct = round(cnt / total * 100, 1) if total else 0
        contrato_rows.append([tc, str(cnt), f'{pct}%'])

    report.add_table(
        ['Tipo Contrato', 'Cantidad', '% del Total'],
        contrato_rows,
        widths=[usable * 0.50, usable * 0.25, usable * 0.25],
        right_align_cols={1},
        center_align_cols={2},
    )

    # ── Section 3: Gender Distribution ──────────────────────────────────
    report.add_section('Distribucion por Genero')

    m_count = qs.filter(sexo='M').count()
    f_count = qs.filter(sexo='F').count()
    other = total - m_count - f_count

    gender_rows = [
        ['Masculino', str(m_count), f'{round(m_count/total*100,1) if total else 0}%'],
        ['Femenino', str(f_count), f'{round(f_count/total*100,1) if total else 0}%'],
    ]
    if other > 0:
        gender_rows.append(
            ['No especificado', str(other),
             f'{round(other/total*100,1) if total else 0}%'])

    report.add_table(
        ['Genero', 'Cantidad', '% del Total'],
        gender_rows,
        widths=[usable * 0.50, usable * 0.25, usable * 0.25],
        right_align_cols={1},
        center_align_cols={2},
    )

    # ── Section 4: Salary Bands ─────────────────────────────────────────
    report.add_section('Bandas Salariales')

    bands = [
        ('Hasta S/ 1,130 (RMV)', Decimal('0'), Decimal('1130')),
        ('S/ 1,131 - S/ 2,000',  Decimal('1131'), Decimal('2000')),
        ('S/ 2,001 - S/ 4,000',  Decimal('2001'), Decimal('4000')),
        ('S/ 4,001 - S/ 7,000',  Decimal('4001'), Decimal('7000')),
        ('S/ 7,001 - S/ 12,000', Decimal('7001'), Decimal('12000')),
        ('Mas de S/ 12,000',     Decimal('12001'), Decimal('999999')),
    ]

    band_rows = []
    for label, low, high in bands:
        cnt = qs.filter(sueldo_base__gte=low, sueldo_base__lte=high).count()
        pct = round(cnt / total * 100, 1) if total else 0
        band_rows.append([label, str(cnt), f'{pct}%'])

    report.add_table(
        ['Banda Salarial', 'Empleados', '% del Total'],
        band_rows,
        widths=[usable * 0.50, usable * 0.25, usable * 0.25],
        right_align_cols={1},
        center_align_cols={2},
    )

    # Salary summary
    report.add_chart_placeholder('Resumen Salarial', [
        ('Sueldo Promedio', f'S/ {_fmt(sueldo_prom)}'),
        ('Sueldo Minimo', f'S/ {_fmt(sueldo_min)}'),
        ('Sueldo Maximo', f'S/ {_fmt(sueldo_max)}'),
        ('Masa Salarial Total', f'S/ {_fmt(masa_total)}'),
    ])

    return report.generate()
