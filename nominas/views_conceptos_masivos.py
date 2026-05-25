"""
Importar/exportar conceptos masivos por Excel para un período de nómina.

Permite al admin descargar un Excel con columnas por concepto manual
(propinas, bonificaciones, comisiones, etc.) por trabajador, llenarlo
y subirlo de vuelta para asignar montos en masa.
"""
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import models, transaction
from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect

solo_admin = user_passes_test(lambda u: u.is_superuser)

from . import engine
from .models import (
    PeriodoNomina,
    ConceptoRemunerativo,
    LineaNomina,
)


@login_required
@solo_admin
def periodo_conceptos_exportar(request, pk):
    """Exporta plantilla Excel del período con columnas por cada concepto manual.

    Estructura:
      DNI | Apellidos y Nombres | Grupo | [Concepto1] | [Concepto2] | ... | [ConceptoN]

    Fila 2 contiene los códigos de los conceptos (referencia para reimportar).
    Pre-llena con valores actuales si los hay (de RegistroNomina.conceptos_manuales).
    """
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    periodo = get_object_or_404(PeriodoNomina, pk=pk)
    registros = periodo.registros.select_related('personal').order_by(
        'personal__apellidos_nombres'
    )

    # Conceptos manuales = formula='MANUAL' o categorías editables
    conceptos = ConceptoRemunerativo.objects.filter(activo=True).filter(
        models.Q(formula='MANUAL')
        | models.Q(categoria__in=[
            'BONIFICACION', 'COMISION', 'PROPINAS',
            'MOVILIDAD', 'OTROS_ING', 'DESCUENTO',
        ])
    ).order_by('tipo', 'orden', 'nombre').distinct()

    if not conceptos.exists():
        messages.warning(
            request,
            'No hay conceptos manuales configurados. Configurá conceptos primero.'
        )
        return redirect('nominas_periodo_detalle', pk=pk)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = f'Conceptos {periodo.anio}-{periodo.mes:02d}'

    # Styles
    header_fill = PatternFill(start_color='0F766E', end_color='0F766E', fill_type='solid')
    header_font = Font(bold=True, color='FFFFFF', size=10)
    sub_fill = PatternFill(start_color='99F6E4', end_color='99F6E4', fill_type='solid')
    sub_font = Font(italic=True, color='0D2B27', size=8)
    border_thin = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1'),
    )

    # Row 1: Títulos principales
    headers_fijos = ['DNI', 'Apellidos y Nombres', 'Grupo']
    headers = headers_fijos + [c.nombre for c in conceptos]
    for col_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        cell.border = border_thin

    # Row 2: códigos (REFERENCIA para parsing en import)
    for col_idx in range(1, len(headers_fijos) + 1):
        cell = ws.cell(row=2, column=col_idx, value='')
        cell.fill = sub_fill
        cell.border = border_thin
    for col_idx, c in enumerate(conceptos, len(headers_fijos) + 1):
        cell = ws.cell(row=2, column=col_idx, value=c.codigo)
        cell.font = sub_font
        cell.fill = sub_fill
        cell.alignment = Alignment(horizontal='center')
        cell.border = border_thin

    # Row 3: tipo (INGRESO / DESCUENTO) — referencia visual
    for col_idx in range(1, len(headers_fijos) + 1):
        ws.cell(row=3, column=col_idx, value='').border = border_thin
    for col_idx, c in enumerate(conceptos, len(headers_fijos) + 1):
        tipo_label = '+ Ingreso' if c.tipo == 'INGRESO' else 'Descuento'
        cell = ws.cell(row=3, column=col_idx, value=tipo_label)
        cell.font = Font(
            italic=True, size=8,
            color='059669' if c.tipo == 'INGRESO' else 'DC2626'
        )
        cell.alignment = Alignment(horizontal='center')
        cell.border = border_thin

    # Datos: fila por trabajador (desde row=4)
    for row_idx, reg in enumerate(registros, 4):
        ws.cell(row=row_idx, column=1, value=reg.personal.nro_doc).border = border_thin
        ws.cell(row=row_idx, column=2, value=reg.personal.apellidos_nombres).border = border_thin
        ws.cell(row=row_idx, column=3, value=reg.grupo or '').border = border_thin

        cm = reg.conceptos_manuales or {}
        for col_idx, c in enumerate(conceptos, len(headers_fijos) + 1):
            valor = cm.get(c.codigo)
            try:
                valor_num = float(valor) if valor not in (None, '', 0) else None
            except (ValueError, TypeError):
                valor_num = None
            cell = ws.cell(row=row_idx, column=col_idx, value=valor_num)
            cell.number_format = '#,##0.00'
            cell.border = border_thin
            cell.alignment = Alignment(horizontal='right')

    # Anchos
    ws.column_dimensions['A'].width = 13
    ws.column_dimensions['B'].width = 32
    ws.column_dimensions['C'].width = 10
    for col_idx in range(len(headers_fijos) + 1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 14

    # Freeze panes
    ws.freeze_panes = 'D4'

    # Instrucción al final
    last_row = len(registros) + 6
    instr = ws.cell(
        row=last_row,
        column=1,
        value=(
            'Instrucciones: completá los montos en cada celda. '
            'Cargá este Excel desde "Importar conceptos masivos" en el período. '
            'La fila 2 contiene los CODIGOS de los conceptos (NO la modifiques).'
        )
    )
    instr.font = Font(italic=True, color='64748B', size=9)
    ws.merge_cells(start_row=last_row, start_column=1, end_row=last_row, end_column=len(headers))

    # Response
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    fname = f'conceptos_{periodo.anio}-{periodo.mes:02d}_{periodo.tipo or "REG"}.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{fname}"'
    wb.save(response)
    return response


@login_required
@solo_admin
def periodo_conceptos_importar(request, pk):
    """Importa Excel y aplica conceptos manuales a los registros del período."""
    import openpyxl

    periodo = get_object_or_404(PeriodoNomina, pk=pk)

    if periodo.estado in ('APROBADO', 'CERRADO', 'ANULADO'):
        messages.error(
            request,
            'El período está aprobado o cerrado. No se pueden importar conceptos.'
        )
        return redirect('nominas_periodo_detalle', pk=pk)

    if request.method != 'POST':
        return redirect('nominas_periodo_detalle', pk=pk)

    archivo = request.FILES.get('archivo')
    if not archivo:
        messages.error(request, 'Subí un archivo Excel.')
        return redirect('nominas_periodo_detalle', pk=pk)

    try:
        wb = openpyxl.load_workbook(archivo, data_only=True)
        ws = wb.active
    except Exception as e:
        messages.error(request, f'Excel inválido: {e}')
        return redirect('nominas_periodo_detalle', pk=pk)

    # Fila 2 tiene los códigos (columna >= 4)
    codigos = []
    col = 4
    while True:
        v = ws.cell(row=2, column=col).value
        if not v:
            break
        codigos.append(str(v).strip())
        col += 1

    if not codigos:
        messages.error(
            request,
            'No se detectaron códigos de conceptos en la fila 2. '
            'Descargá la plantilla del período primero.'
        )
        return redirect('nominas_periodo_detalle', pk=pk)

    # Validar códigos
    conceptos_db = {
        c.codigo: c for c in ConceptoRemunerativo.objects.filter(
            codigo__in=codigos, activo=True
        )
    }
    invalidos = [c for c in codigos if c not in conceptos_db]
    if invalidos:
        messages.warning(
            request,
            f'Códigos no encontrados (ignorados): {", ".join(invalidos)}'
        )

    # Procesar filas desde row=4
    registros_actualizados = 0
    row = 4
    while True:
        dni = ws.cell(row=row, column=1).value
        if not dni:
            break
        dni = str(dni).strip()

        reg = periodo.registros.filter(personal__nro_doc=dni).first()
        if not reg:
            row += 1
            continue

        nuevos = {}
        for idx, cod in enumerate(codigos):
            if cod not in conceptos_db:
                continue
            val = ws.cell(row=row, column=4 + idx).value
            if val is None or val == '':
                continue
            try:
                monto = Decimal(str(val))
            except (ValueError, ArithmeticError):
                continue
            if monto != 0:
                nuevos[cod] = str(monto)

        reg.conceptos_manuales = nuevos

        # Recalcular registro
        conceptos_activos = ConceptoRemunerativo.objects.filter(activo=True).order_by('tipo', 'orden')
        with transaction.atomic():
            reg.save()
            resultado = engine.calcular_registro(reg, conceptos_activos)
            reg.lineas.all().delete()
            for l in resultado['lineas']:
                LineaNomina.objects.create(
                    registro=reg,
                    concepto=l['concepto'],
                    base_calculo=l['base_calculo'],
                    porcentaje_aplicado=l['porcentaje_aplicado'],
                    monto=l['monto'],
                    observacion=l['observacion'],
                )
            reg.total_ingresos = resultado['total_ingresos']
            reg.total_descuentos = resultado['total_descuentos']
            reg.neto_a_pagar = resultado['neto_a_pagar']
            reg.aporte_essalud = resultado['aporte_essalud']
            reg.costo_total_empresa = resultado['costo_total_empresa']
            reg.estado = 'CALCULADO'
            reg.save()

        registros_actualizados += 1
        row += 1

    # Resync totales del período
    agg = periodo.registros.aggregate(
        t_bruto=Sum('total_ingresos'),
        t_desc=Sum('total_descuentos'),
        t_neto=Sum('neto_a_pagar'),
        t_costo=Sum('costo_total_empresa'),
    )
    periodo.total_bruto = agg['t_bruto'] or Decimal('0')
    periodo.total_descuentos = agg['t_desc'] or Decimal('0')
    periodo.total_neto = agg['t_neto'] or Decimal('0')
    periodo.total_costo_empresa = agg['t_costo'] or Decimal('0')
    periodo.save(update_fields=[
        'total_bruto', 'total_descuentos', 'total_neto', 'total_costo_empresa'
    ])

    messages.success(
        request,
        f'Conceptos importados correctamente para {registros_actualizados} '
        f'trabajadores. Planilla recalculada.'
    )
    return redirect('nominas_periodo_detalle', pk=pk)
