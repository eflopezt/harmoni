"""
Reporte Ejecutivo de Asistencia (PDF).

Genera un resumen mensual de asistencia:
- KPIs: asistencia promedio, tardanzas, faltas
- Resumen por area
- Horas extras por area
"""
import logging
from collections import defaultdict
from decimal import Decimal

from core.report_engine import HarmoniReport, _fmt

logger = logging.getLogger('core.reports.asistencia')

MESES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
         'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

CODIGOS_ASISTENCIA = {'A', 'NOR', 'CHE', 'TE', 'FL', 'DM', 'VAC', 'SS', 'DL'}
CODIGOS_FALTA = {'F'}
CODIGOS_HABILES = {'A', 'NOR', 'CHE', 'F', 'TE', 'DM'}
CODIGOS_TARDANZA = {'TE'}


def generar_reporte_asistencia(anio, mes):
    """
    Generate a monthly attendance summary PDF.
    Returns PDF bytes.
    """
    from asistencia.models import RegistroTareo

    registros = (
        RegistroTareo.objects
        .filter(fecha__year=anio, fecha__month=mes)
        .select_related('personal', 'personal__subarea', 'personal__subarea__area')
        .order_by('personal__apellidos_nombres', 'fecha')
    )

    # Aggregate by employee
    empleados = defaultdict(lambda: {
        'nombre': '',
        'area': '',
        'grupo': '',
        'dias_habiles': 0,
        'dias_asistio': 0,
        'dias_falta': 0,
        'dias_tardanza': 0,
        'he_25': Decimal('0'),
        'he_35': Decimal('0'),
        'he_100': Decimal('0'),
    })

    for reg in registros:
        dni = reg.dni
        emp = empleados[dni]
        if not emp['nombre']:
            if reg.personal:
                emp['nombre'] = reg.personal.apellidos_nombres
                emp['area'] = (
                    reg.personal.subarea.area.nombre
                    if reg.personal.subarea and reg.personal.subarea.area
                    else 'Sin Area'
                )
            else:
                emp['nombre'] = reg.nombre_archivo or dni
                emp['area'] = 'Sin Area'
        emp['grupo'] = reg.grupo

        codigo = (reg.codigo_dia or '').strip().upper()
        if codigo in CODIGOS_HABILES:
            emp['dias_habiles'] += 1
        if codigo in CODIGOS_ASISTENCIA:
            emp['dias_asistio'] += 1
        if codigo in CODIGOS_FALTA:
            emp['dias_falta'] += 1
        if codigo in CODIGOS_TARDANZA:
            emp['dias_tardanza'] += 1

        emp['he_25'] += reg.he_25 or Decimal('0')
        emp['he_35'] += reg.he_35 or Decimal('0')
        emp['he_100'] += reg.he_100 or Decimal('0')

    # Aggregate by area
    areas_data = defaultdict(lambda: {
        'empleados': 0,
        'dias_habiles': 0,
        'dias_asistio': 0,
        'dias_falta': 0,
        'dias_tardanza': 0,
        'he_25': Decimal('0'),
        'he_35': Decimal('0'),
        'he_100': Decimal('0'),
    })

    total_emps = len(empleados)
    total_habiles = 0
    total_asistio = 0
    total_faltas = 0
    total_tardanzas = 0
    total_he = Decimal('0')

    for dni, emp in empleados.items():
        area = emp['area']
        a = areas_data[area]
        a['empleados'] += 1
        a['dias_habiles'] += emp['dias_habiles']
        a['dias_asistio'] += emp['dias_asistio']
        a['dias_falta'] += emp['dias_falta']
        a['dias_tardanza'] += emp['dias_tardanza']
        a['he_25'] += emp['he_25']
        a['he_35'] += emp['he_35']
        a['he_100'] += emp['he_100']

        total_habiles += emp['dias_habiles']
        total_asistio += emp['dias_asistio']
        total_faltas += emp['dias_falta']
        total_tardanzas += emp['dias_tardanza']
        total_he += emp['he_25'] + emp['he_35'] + emp['he_100']

    pct_global = round(total_asistio / total_habiles * 100, 1) if total_habiles else 0

    # Build report
    mes_str = MESES[mes] if 1 <= mes <= 12 else str(mes)

    report = HarmoniReport(
        titulo='Reporte de Asistencia',
        subtitulo=f'{mes_str} {anio}',
    )
    report.add_header()

    # KPIs
    report.add_kpi_row([
        ('Empleados', str(total_emps)),
        ('% Asistencia', f'{pct_global}%'),
        ('Faltas', str(total_faltas)),
        ('Tardanzas', str(total_tardanzas)),
        ('Horas Extra', _fmt(total_he)),
    ])

    # ── Section 1: Summary by Area ──────────────────────────────────────
    report.add_section('Asistencia por Area')

    area_rows = []
    for area_name in sorted(areas_data.keys()):
        a = areas_data[area_name]
        pct = round(a['dias_asistio'] / a['dias_habiles'] * 100, 1) if a['dias_habiles'] else 0
        area_rows.append([
            area_name,
            str(a['empleados']),
            str(a['dias_habiles']),
            str(a['dias_asistio']),
            str(a['dias_falta']),
            str(a['dias_tardanza']),
            f'{pct}%',
        ])

    usable = report.usable_w
    report.add_table(
        ['Area', 'Emps', 'D. Habiles', 'D. Asistio', 'Faltas', 'Tardanzas', '% Asist.'],
        area_rows,
        widths=[usable * 0.25, usable * 0.10, usable * 0.13, usable * 0.13,
                usable * 0.11, usable * 0.13, usable * 0.15],
        right_align_cols={1, 2, 3, 4, 5},
        center_align_cols={6},
        totals_row=[
            'TOTAL', str(total_emps), str(total_habiles), str(total_asistio),
            str(total_faltas), str(total_tardanzas), f'{pct_global}%',
        ],
    )

    # ── Section 2: Overtime by Area ─────────────────────────────────────
    report.add_section('Horas Extra por Area')

    he_rows = []
    for area_name in sorted(areas_data.keys()):
        a = areas_data[area_name]
        he_total = a['he_25'] + a['he_35'] + a['he_100']
        if he_total > 0:
            he_rows.append([
                area_name,
                _fmt(a['he_25']),
                _fmt(a['he_35']),
                _fmt(a['he_100']),
                _fmt(he_total),
            ])

    if he_rows:
        grand_he_25 = sum(areas_data[a]['he_25'] for a in areas_data)
        grand_he_35 = sum(areas_data[a]['he_35'] for a in areas_data)
        grand_he_100 = sum(areas_data[a]['he_100'] for a in areas_data)

        report.add_table(
            ['Area', 'HE 25%', 'HE 35%', 'HE 100%', 'Total HE'],
            he_rows,
            widths=[usable * 0.30, usable * 0.17, usable * 0.17,
                    usable * 0.17, usable * 0.19],
            right_align_cols={1, 2, 3, 4},
            totals_row=[
                'TOTAL', _fmt(grand_he_25), _fmt(grand_he_35),
                _fmt(grand_he_100), _fmt(total_he),
            ],
        )
    else:
        report.add_text('No se registraron horas extra en este periodo.')

    # ── Section 3: Employee detail (top faltas/tardanzas) ───────────────
    report.add_section('Empleados con Mayor Inasistencia')

    sorted_emps = sorted(
        empleados.items(),
        key=lambda x: (x[1]['dias_falta'] + x[1]['dias_tardanza']),
        reverse=True,
    )
    top_emps = [e for e in sorted_emps if e[1]['dias_falta'] + e[1]['dias_tardanza'] > 0][:20]

    if top_emps:
        emp_rows = []
        for idx, (dni, emp) in enumerate(top_emps, 1):
            pct = round(emp['dias_asistio'] / emp['dias_habiles'] * 100, 1) if emp['dias_habiles'] else 0
            emp_rows.append([
                str(idx),
                emp['nombre'],
                emp['area'],
                str(emp['dias_falta']),
                str(emp['dias_tardanza']),
                f'{pct}%',
            ])

        report.add_table(
            ['N', 'Empleado', 'Area', 'Faltas', 'Tardanzas', '% Asist.'],
            emp_rows,
            widths=[usable * 0.06, usable * 0.30, usable * 0.24,
                    usable * 0.12, usable * 0.14, usable * 0.14],
            right_align_cols={3, 4},
            center_align_cols={0, 5},
        )
    else:
        report.add_text('No se registraron faltas ni tardanzas en este periodo.')

    return report.generate()
