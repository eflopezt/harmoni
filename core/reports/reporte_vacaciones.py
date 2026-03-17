"""
Reporte Ejecutivo de Vacaciones (PDF).

Genera un resumen de vacaciones:
- Dias pendientes por empleado
- Estadisticas de uso de vacaciones
"""
import logging
from decimal import Decimal

from django.db.models import Count, Sum, Q

from core.report_engine import HarmoniReport, _fmt

logger = logging.getLogger('core.reports.vacaciones')


def generar_reporte_vacaciones():
    """
    Generate a vacation summary PDF report.
    Returns PDF bytes.
    """
    from vacaciones.models import SaldoVacacional, SolicitudVacacion
    from personal.models import Personal

    # Active employees with vacation balances
    saldos = (
        SaldoVacacional.objects
        .filter(personal__estado='Activo')
        .select_related('personal', 'personal__subarea', 'personal__subarea__area')
        .order_by('personal__apellidos_nombres', '-periodo_inicio')
    )

    # Group by employee - latest saldo per employee
    emp_saldos = {}
    emp_total_pendiente = {}
    for s in saldos:
        pid = s.personal_id
        if pid not in emp_saldos:
            emp_saldos[pid] = s
        # Accumulate total pending days across all periods
        if pid not in emp_total_pendiente:
            emp_total_pendiente[pid] = 0
        emp_total_pendiente[pid] += s.dias_pendientes

    total_emps = len(emp_saldos)
    total_pendientes = sum(emp_total_pendiente.values())
    avg_pendiente = round(total_pendientes / total_emps, 1) if total_emps else 0

    # Stats from SolicitudVacacion
    total_solicitudes = SolicitudVacacion.objects.filter(
        personal__estado='Activo').count()
    aprobadas = SolicitudVacacion.objects.filter(
        personal__estado='Activo', estado='APROBADA').count()
    en_goce = SolicitudVacacion.objects.filter(
        personal__estado='Activo', estado='EN_GOCE').count()
    pendientes_aprob = SolicitudVacacion.objects.filter(
        personal__estado='Activo', estado='PENDIENTE').count()

    # Build report
    report = HarmoniReport(
        titulo='Reporte de Vacaciones',
        subtitulo='Personal Activo',
    )
    report.add_header()

    # KPIs
    report.add_kpi_row([
        ('Empleados', str(total_emps)),
        ('Dias Pendientes', str(total_pendientes)),
        ('Promedio/Empleado', f'{avg_pendiente} dias'),
        ('Solicitudes Pend.', str(pendientes_aprob)),
    ])

    # ── Section 1: Vacation Usage Stats ─────────────────────────────────
    report.add_chart_placeholder('Estadisticas de Vacaciones', [
        ('Total Solicitudes (activos)', str(total_solicitudes)),
        ('Aprobadas', str(aprobadas)),
        ('En Goce actualmente', str(en_goce)),
        ('Pendientes de Aprobacion', str(pendientes_aprob)),
        ('Dias pendientes acumulados', str(total_pendientes)),
        ('Promedio dias pendientes por empleado', str(avg_pendiente)),
    ])

    # ── Section 2: Pending Days by Employee ─────────────────────────────
    report.add_section('Dias Pendientes por Empleado')

    # Sort by most pending days
    sorted_emps = sorted(
        emp_saldos.items(),
        key=lambda x: emp_total_pendiente.get(x[0], 0),
        reverse=True,
    )

    rows = []
    for idx, (pid, saldo) in enumerate(sorted_emps, 1):
        p = saldo.personal
        area = ''
        try:
            area = p.subarea.area.nombre if p.subarea and p.subarea.area else ''
        except Exception:
            pass

        total_pend = emp_total_pendiente.get(pid, 0)
        ultimo_periodo = f'{saldo.periodo_inicio.strftime("%d/%m/%Y")} - {saldo.periodo_fin.strftime("%d/%m/%Y")}'

        rows.append([
            str(idx),
            p.apellidos_nombres,
            area,
            str(saldo.dias_derecho),
            str(saldo.dias_gozados),
            str(saldo.dias_vendidos),
            str(total_pend),
            saldo.get_estado_display(),
        ])

    usable = report.usable_w
    report.add_table(
        ['N', 'Empleado', 'Area', 'Derecho', 'Gozados', 'Vendidos',
         'Pendientes', 'Estado'],
        rows,
        widths=[usable * 0.05, usable * 0.25, usable * 0.17, usable * 0.09,
                usable * 0.10, usable * 0.10, usable * 0.12, usable * 0.12],
        right_align_cols={3, 4, 5, 6},
        center_align_cols={0, 7},
        totals_row=['', 'TOTAL', f'{total_emps} empleados', '', '', '',
                    str(total_pendientes), ''],
    )

    # ── Section 3: Employees with most pending days (risk) ──────────────
    high_risk = [
        (pid, s) for pid, s in sorted_emps
        if emp_total_pendiente.get(pid, 0) >= 30
    ]

    if high_risk:
        report.add_section('Empleados con 30+ Dias Pendientes (Riesgo)')
        report.add_text(
            f'{len(high_risk)} empleados tienen 30 o mas dias de vacaciones '
            f'pendientes acumulados. Se recomienda coordinar la programacion '
            f'de vacaciones para evitar contingencias laborales.'
        )

        risk_rows = []
        for idx, (pid, saldo) in enumerate(high_risk, 1):
            p = saldo.personal
            area = ''
            try:
                area = p.subarea.area.nombre if p.subarea and p.subarea.area else ''
            except Exception:
                pass
            risk_rows.append([
                str(idx),
                p.apellidos_nombres,
                area,
                str(emp_total_pendiente.get(pid, 0)),
            ])

        report.add_table(
            ['N', 'Empleado', 'Area', 'Dias Pendientes'],
            risk_rows,
            widths=[usable * 0.08, usable * 0.40, usable * 0.30, usable * 0.22],
            right_align_cols={3},
            center_align_cols={0},
        )

    return report.generate()
