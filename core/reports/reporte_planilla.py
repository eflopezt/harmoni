"""
Reporte Ejecutivo de Planilla (PDF).

Genera un resumen de la planilla de un periodo:
- KPIs: total empleados, bruto, neto, aportes
- Tabla detalle por empleado
- Fila de totales
"""
import logging
from decimal import Decimal

from core.report_engine import HarmoniReport, _fmt

logger = logging.getLogger('core.reports.planilla')

MESES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
         'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']


def generar_reporte_planilla(periodo):
    """
    Generate a payroll summary PDF for a PeriodoNomina.
    Returns PDF bytes.
    """
    from nominas.models import RegistroNomina

    registros = (
        RegistroNomina.objects
        .filter(periodo=periodo)
        .select_related('personal', 'personal__subarea', 'personal__subarea__area')
        .order_by('personal__subarea__area__nombre', 'personal__apellidos_nombres')
    )

    # Aggregates
    total_emps = registros.count()
    total_bruto = Decimal('0')
    total_desc = Decimal('0')
    total_neto = Decimal('0')
    total_aportes = Decimal('0')
    total_costo = Decimal('0')

    rows = []
    for idx, reg in enumerate(registros, 1):
        p = reg.personal
        area = ''
        try:
            area = p.subarea.area.nombre if p.subarea and p.subarea.area else ''
        except Exception:
            pass

        bruto = reg.total_ingresos or Decimal('0')
        desc = reg.total_descuentos or Decimal('0')
        neto = reg.neto_a_pagar or Decimal('0')
        essalud = reg.aporte_essalud or Decimal('0')
        costo = reg.costo_total_empresa or Decimal('0')

        total_bruto += bruto
        total_desc += desc
        total_neto += neto
        total_aportes += essalud
        total_costo += costo

        rows.append([
            str(idx),
            p.apellidos_nombres,
            area,
            f"S/ {_fmt(reg.sueldo_base)}",
            f"S/ {_fmt(bruto)}",
            f"S/ {_fmt(desc)}",
            f"S/ {_fmt(neto)}",
            f"S/ {_fmt(essalud)}",
        ])

    # Build report
    mes_str = MESES[periodo.mes] if 1 <= periodo.mes <= 12 else str(periodo.mes)
    tipo_str = periodo.get_tipo_display()

    report = HarmoniReport(
        titulo='Reporte de Planilla',
        subtitulo=f'{tipo_str} - {mes_str} {periodo.anio}',
        orientation='landscape',
    )
    report.add_header()

    # KPIs
    report.add_kpi_row([
        ('Total Empleados', str(total_emps)),
        ('Total Bruto', f'S/ {_fmt(total_bruto)}'),
        ('Total Descuentos', f'S/ {_fmt(total_desc)}'),
        ('Total Neto', f'S/ {_fmt(total_neto)}'),
        ('Aportes Empleador', f'S/ {_fmt(total_aportes)}'),
    ])

    # Period info
    report.add_text(
        f"Periodo: {periodo.fecha_inicio.strftime('%d/%m/%Y')} al "
        f"{periodo.fecha_fin.strftime('%d/%m/%Y')}  |  "
        f"Estado: {periodo.get_estado_display()}  |  "
        f"Costo total empresa: S/ {_fmt(total_costo)}"
    )

    # Table
    headers = ['N', 'Empleado', 'Area', 'Sueldo Base', 'Ingresos',
               'Descuentos', 'Neto', 'Aportes']

    usable = report.usable_w
    widths = [
        usable * 0.04,   # N
        usable * 0.25,   # Empleado
        usable * 0.14,   # Area
        usable * 0.11,   # Sueldo
        usable * 0.12,   # Ingresos
        usable * 0.12,   # Descuentos
        usable * 0.12,   # Neto
        usable * 0.10,   # Aportes
    ]

    totals = [
        '', 'TOTALES', f'{total_emps} empleados', '',
        f'S/ {_fmt(total_bruto)}',
        f'S/ {_fmt(total_desc)}',
        f'S/ {_fmt(total_neto)}',
        f'S/ {_fmt(total_aportes)}',
    ]

    report.add_table(
        headers, rows, widths=widths,
        right_align_cols={3, 4, 5, 6, 7},
        center_align_cols={0},
        totals_row=totals,
    )

    return report.generate()
