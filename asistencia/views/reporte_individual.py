"""
Reporte individual de asistencia por empleado.
STAFF: codigo diario (A, DL, V, F, DS, etc.) del ciclo 21-20.
RCO:   horas normales + HE 25/35/100% del ciclo.
Ambos incluyen papeletas del periodo.
"""
import io
import json
import calendar
import logging
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Sum
from django.views.decorators.http import require_POST

from xhtml2pdf import pisa

from asistencia.models import RegistroTareo, RegistroPapeleta, ConfiguracionSistema
from asistencia.views._common import solo_admin, _qs_staff_dedup

logger = logging.getLogger('asistencia')
from personal.models import Personal, Area

MESES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
         'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

DIAS_SEMANA = ['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom']
DIAS_CORTO = ['L', 'M', 'Mi', 'J', 'V', 'S', 'D']

PRESENCIA = {'T', 'NOR', 'TR', 'A', 'CDT', 'CPF', 'LCG', 'ATM', 'CHE', 'LIM', 'SS'}
DESCANSO = {'DS', 'B'}
LIBRE = {'DL', 'DLA'}

CODE_COLORS = {
    'A': '#c6f6d5', 'NOR': '#c6f6d5', 'T': '#c6f6d5', 'TR': '#c6f6d5', 'SS': '#c6f6d5',
    'F': '#fed7d7', 'FA': '#fed7d7', 'SAI': '#fed7d7',
    'VAC': '#bee3f8', 'V': '#bee3f8',
    'DL': '#e2e8f0', 'DLA': '#e2e8f0', 'DS': '#e2e8f0', 'B': '#e2e8f0',
    'DM': '#fefcbf', 'SUB': '#fefcbf',
    'CHE': '#feebc8', 'CDT': '#feebc8', 'CPF': '#feebc8',
    'LSG': '#e9d8fd', 'LCG': '#c4f1f9', 'LF': '#c4f1f9', 'LP': '#c4f1f9',
    'FR': '#fed7e2', 'FER': '#fed7e2', 'NA': '#edf2f7',
    'LIM': '#bee3f8', 'ATM': '#bee3f8',
}


def _get_ciclo(anio, mes):
    if mes == 1:
        inicio = date(anio - 1, 12, 21)
    else:
        inicio = date(anio, mes - 1, 21)
    return inicio, date(anio, mes, 20)


# ========== VIEWS ==========

@login_required
@solo_admin
def reporte_panel(request):
    hoy = date.today()
    anio = int(request.GET.get('anio', hoy.year))
    mes = int(request.GET.get('mes', hoy.month))
    grupo = request.GET.get('grupo', 'STAFF')
    area_id = request.GET.get('area', '')
    buscar = request.GET.get('q', '')
    inicio, fin = _get_ciclo(anio, mes)
    qs = RegistroTareo.objects.filter(fecha__gte=inicio, fecha__lte=fin, personal__isnull=False)
    if grupo != 'TODOS':
        qs = qs.filter(grupo=grupo)
    if area_id:
        qs = qs.filter(personal__subarea__area_id=area_id)
    if buscar:
        qs = qs.filter(Q(personal__apellidos_nombres__icontains=buscar) | Q(dni__icontains=buscar))
    pids = list(qs.values_list('personal_id', flat=True).distinct())
    empleados = Personal.objects.filter(id__in=pids).order_by('apellidos_nombres')
    return render(request, 'asistencia/reporte_individual_panel.html', {
        'titulo': f'Reportes Individuales - {MESES[mes]} {anio}',
        'anio': anio, 'mes': mes, 'mes_nombre': MESES[mes],
        'inicio': inicio, 'fin': fin, 'grupo': grupo, 'area_id': area_id, 'buscar': buscar,
        'empleados': empleados, 'total_empleados': empleados.count(),
        'areas': Area.objects.all().order_by('nombre'),
        'anios': list(range(hoy.year - 2, hoy.year + 1)),
        'meses_list': [(i, MESES[i]) for i in range(1, 13)],
    })


def _fuera_de_periodo(fecha, personal):
    """True si la fecha es antes del ingreso o después del cese."""
    if personal.fecha_alta and fecha < personal.fecha_alta:
        return True
    if personal.fecha_cese and fecha > personal.fecha_cese:
        return True
    return False


def _auto_ds(fecha, codigo, condicion):
    """Asignar DS automaticamente si LOCAL + Domingo sin trabajo real.

    Regla: LOCAL en domingo:
    - Sin registro o FA/F → DS (no trabajó, es su descanso obligatorio)
    - Con NOR/A/T → se mantiene (realmente trabajó ese domingo)
    - Con otro código (VAC, DM, etc.) → se mantiene
    """
    es_domingo = fecha.weekday() == 6
    es_local = condicion.upper() in ('LOCAL', 'LIMA', '')
    if es_domingo and es_local:
        if not codigo or codigo in ('FA', 'F'):
            return 'DS'
    return codigo


def _build_staff_data(personal, inicio, fin):
    # Buscar ambos grupos
    staff_regs = list(RegistroTareo.objects.filter(
        personal=personal, fecha__gte=inicio, fecha__lte=fin, grupo='STAFF'
    ).order_by('fecha').values('fecha', 'codigo_dia'))
    rco_regs = list(RegistroTareo.objects.filter(
        personal=personal, fecha__gte=inicio, fecha__lte=fin, grupo='RCO'
    ).order_by('fecha').values('fecha', 'codigo_dia'))
    # RCO como base, STAFF sobreescribe EXCEPTO DS en domingos
    tareo_map = {}
    rco_map = {r['fecha']: r['codigo_dia'] for r in rco_regs}
    for r in rco_regs:
        tareo_map[r['fecha']] = r['codigo_dia']
    for r in staff_regs:
        fecha = r['fecha']
        # Si RCO tiene DS para este dia, mantenerlo (es mas preciso que STAFF)
        if fecha in rco_map and rco_map[fecha] in ('DS', 'DL', 'DLA'):
            continue
        tareo_map[fecha] = r['codigo_dia']

    condicion = personal.condicion or ''
    dias = []
    conteo = {}
    d = inicio
    while d <= fin:
        if _fuera_de_periodo(d, personal):
            dias.append({'fecha': d, 'dow_s': DIAS_CORTO[d.weekday()], 'codigo': 'NA', 'display': 'N/A'})
            d += timedelta(days=1)
            continue
        codigo = tareo_map.get(d, '')
        codigo = _auto_ds(d, codigo, condicion)
        if codigo in PRESENCIA:
            display = 'A'
        elif codigo in DESCANSO:
            display = 'DS'
        elif codigo in LIBRE:
            display = 'DL'
        else:
            display = codigo
        dias.append({'fecha': d, 'dow_s': DIAS_CORTO[d.weekday()], 'codigo': codigo, 'display': display})
        if display:
            conteo[display] = conteo.get(display, 0) + 1
        d += timedelta(days=1)
    return dias, conteo


def _build_rco_data(personal, inicio, fin):
    # Buscar RCO primero, luego STAFF como fallback
    rco_regs = list(RegistroTareo.objects.filter(
        personal=personal, fecha__gte=inicio, fecha__lte=fin, grupo='RCO'
    ).order_by('fecha').values('fecha', 'codigo_dia', 'horas_normales', 'he_25', 'he_35', 'he_100'))
    staff_regs = list(RegistroTareo.objects.filter(
        personal=personal, fecha__gte=inicio, fecha__lte=fin, grupo='STAFF'
    ).order_by('fecha').values('fecha', 'codigo_dia', 'horas_normales', 'he_25', 'he_35', 'he_100'))
    tareo_map = {}
    for r in staff_regs:
        tareo_map[r['fecha']] = r
    for r in rco_regs:  # RCO sobreescribe STAFF
        tareo_map[r['fecha']] = r
    condicion = personal.condicion or ''
    dias = []
    tot = {'normales': Decimal('0'), 'he_25': Decimal('0'), 'he_35': Decimal('0'), 'he_100': Decimal('0')}
    d = inicio
    while d <= fin:
        if _fuera_de_periodo(d, personal):
            dias.append({'fecha': d, 'dow_s': DIAS_CORTO[d.weekday()], 'codigo': 'NA', 'n': 0, 'h25': 0, 'h35': 0, 'h100': 0})
            d += timedelta(days=1)
            continue
        reg = tareo_map.get(d)
        if reg:
            codigo = _auto_ds(d, reg['codigo_dia'], condicion)
            dias.append({'fecha': d, 'dow_s': DIAS_CORTO[d.weekday()], 'codigo': codigo,
                         'n': float(reg['horas_normales'] or 0), 'h25': float(reg['he_25'] or 0),
                         'h35': float(reg['he_35'] or 0), 'h100': float(reg['he_100'] or 0)})
            tot['normales'] += reg['horas_normales'] or 0
            tot['he_25'] += reg['he_25'] or 0
            tot['he_35'] += reg['he_35'] or 0
            tot['he_100'] += reg['he_100'] or 0
        else:
            auto_cod = _auto_ds(d, '', condicion)
            dias.append({'fecha': d, 'dow_s': DIAS_CORTO[d.weekday()], 'codigo': auto_cod, 'n': 0, 'h25': 0, 'h35': 0, 'h100': 0})
        d += timedelta(days=1)
    return dias, {k: float(v) for k, v in tot.items()}


def _get_papeletas(personal, inicio, fin):
    return list(RegistroPapeleta.objects.filter(
        personal=personal, fecha_inicio__lte=fin, fecha_fin__gte=inicio
    ).order_by('fecha_inicio').values('tipo_permiso', 'fecha_inicio', 'fecha_fin', 'dias_habiles', 'estado', 'observaciones'))


def _render_pdf(html_string):
    buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_string), dest=buffer, encoding='utf-8')
    if pisa_status.err:
        return None
    return buffer.getvalue()


@login_required
@solo_admin
def reporte_individual_pdf(request, personal_id):
    personal = get_object_or_404(Personal, pk=personal_id)
    anio = int(request.GET.get('anio', date.today().year))
    mes = int(request.GET.get('mes', date.today().month))
    # Usar grupo_tareo del empleado, no del filtro
    grupo = personal.grupo_tareo or request.GET.get('grupo', 'STAFF')
    inicio, fin = _get_ciclo(anio, mes)
    papeletas = _get_papeletas(personal, inicio, fin)
    if grupo == 'RCO':
        dias, totales = _build_rco_data(personal, inicio, fin)
        html = _render_rco_html(personal, dias, totales, papeletas, inicio, fin, mes, anio)
    else:
        dias, conteo = _build_staff_data(personal, inicio, fin)
        html = _render_staff_html(personal, dias, conteo, papeletas, inicio, fin, mes, anio)
    pdf = _render_pdf(html)
    if not pdf:
        return HttpResponse('Error generando PDF', status=500)
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Asistencia_{personal.nro_doc}_{MESES[mes]}_{anio}.pdf"'
    return response


@login_required
@solo_admin
def reporte_masivo_pdf(request):
    from zipfile import ZipFile
    anio = int(request.GET.get('anio', date.today().year))
    mes = int(request.GET.get('mes', date.today().month))
    grupo = request.GET.get('grupo', 'STAFF')
    area_id = request.GET.get('area', '')
    inicio, fin = _get_ciclo(anio, mes)
    qs = RegistroTareo.objects.filter(fecha__gte=inicio, fecha__lte=fin, personal__isnull=False)
    if grupo != 'TODOS':
        qs = qs.filter(grupo=grupo)
    if area_id:
        qs = qs.filter(personal__subarea__area_id=area_id)
    pids = list(qs.values_list('personal_id', flat=True).distinct())
    empleados = Personal.objects.filter(id__in=pids).order_by('apellidos_nombres')
    zip_buffer = io.BytesIO()
    with ZipFile(zip_buffer, 'w') as zf:
        for p in empleados:
            pap = _get_papeletas(p, inicio, fin)
            # Usar grupo_tareo del empleado
            g = p.grupo_tareo or grupo
            if g == 'RCO':
                d, t = _build_rco_data(p, inicio, fin)
                h = _render_rco_html(p, d, t, pap, inicio, fin, mes, anio)
            else:
                d, c = _build_staff_data(p, inicio, fin)
                h = _render_staff_html(p, d, c, pap, inicio, fin, mes, anio)
            pdf = _render_pdf(h)
            if pdf:
                zf.writestr(f'{p.nro_doc}_{p.apellidos_nombres.replace(",","").replace(" ","_")}.pdf', pdf)
    zip_buffer.seek(0)
    response = HttpResponse(zip_buffer.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="Reportes_{grupo}_{MESES[mes]}_{anio}.zip"'
    return response


def _generar_pdf_empleado(personal, anio, mes, grupo):
    """Genera bytes del PDF de reporte para un empleado."""
    # Usar grupo_tareo del empleado si está configurado
    grupo = personal.grupo_tareo or grupo
    inicio, fin = _get_ciclo(anio, mes)
    papeletas = _get_papeletas(personal, inicio, fin)
    if grupo == 'RCO':
        dias, totales = _build_rco_data(personal, inicio, fin)
        html = _render_rco_html(personal, dias, totales, papeletas, inicio, fin, mes, anio)
    else:
        dias, conteo = _build_staff_data(personal, inicio, fin)
        html = _render_staff_html(personal, dias, conteo, papeletas, inicio, fin, mes, anio)
    return _render_pdf(html)


def _get_email_empleado(personal):
    """Retorna el mejor email disponible del empleado."""
    return personal.correo_corporativo or personal.correo_personal or ''


def _cuerpo_reporte(nombre, mes_nombre, anio):
    """Genera el cuerpo del correo de reporte de asistencia."""
    return (
        f'Estimado(a) {nombre},\n'
        f'\n'
        f'Como parte del proceso de mejora en el control de asistencia, estamos '
        f'implementando el envio automatizado de reportes individuales. Adjunto '
        f'encontrara su reporte correspondiente al periodo {mes_nombre} {anio}.\n'
        f'\n'
        f'Le pedimos revisarlo con atencion. Si identifica alguna diferencia en sus '
        f'marcaciones, papeletas no registradas o cualquier dato que requiera '
        f'correccion, por favor comuniquelo a la brevedad a cualquiera de los '
        f'siguientes correos para su regularizacion:\n'
        f'\n'
        f'    - jochoa@consorciosrt.com\n'
        f'    - eflopez@consorciosrt.com\n'
        f'    - randrade@consorciosrt.com\n'
        f'\n'
        f'Esta informacion sera utilizada para el calculo de la nomina del periodo, '
        f'por lo que es importante contar con datos actualizados.\n'
        f'\n'
        f'Agradecemos su colaboracion.\n'
        f'\n'
        f'Saludos cordiales,\n'
        f'Area de Recursos Humanos\n'
        f'Consorcio SRT'
    )


def _enviar_reporte(personal, anio, mes, grupo):
    """Genera y envía el reporte PDF al correo del empleado.
    Retorna (ok, email_o_error)."""
    email_dest = _get_email_empleado(personal)
    if not email_dest:
        return False, 'sin_correo'

    pdf = _generar_pdf_empleado(personal, anio, mes, grupo)
    if not pdf:
        return False, 'error_pdf'

    filename = f'Asistencia_{personal.nro_doc}_{MESES[mes]}_{anio}.pdf'
    asunto = f'Reporte de Asistencia - {MESES[mes]} {anio}'
    cuerpo = _cuerpo_reporte(personal.apellidos_nombres, MESES[mes], anio)

    try:
        email = EmailMessage(
            subject=asunto,
            body=cuerpo,
            to=[email_dest],
        )
        email.attach(filename, pdf, 'application/pdf')
        email.send()
        logger.info('Reporte enviado a %s (%s)', personal.nro_doc, email_dest)
        return True, email_dest
    except Exception as e:
        logger.exception('Error enviando reporte a %s', personal.nro_doc)
        return False, str(e)


@login_required
@solo_admin
@require_POST
def enviar_reporte_email(request, personal_id):
    """Envía reporte individual por correo al empleado."""
    personal = get_object_or_404(Personal, pk=personal_id)
    anio = int(request.GET.get('anio', date.today().year))
    mes = int(request.GET.get('mes', date.today().month))
    grupo = request.GET.get('grupo', 'STAFF')

    email_dest = _get_email_empleado(personal)
    if not email_dest:
        return JsonResponse({'ok': False, 'error': f'{personal.apellidos_nombres} no tiene correo registrado.'}, status=400)

    ok, resultado = _enviar_reporte(personal, anio, mes, grupo)
    if ok:
        return JsonResponse({'ok': True, 'email': resultado})
    return JsonResponse({'ok': False, 'error': resultado}, status=500)


@login_required
@solo_admin
@require_POST
def enviar_reportes_masivo_email(request):
    """Envía reportes por correo a múltiples empleados seleccionados."""
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Datos inválidos.'}, status=400)

    ids = body.get('ids', [])
    anio = int(body.get('anio', date.today().year))
    mes = int(body.get('mes', date.today().month))
    grupo = body.get('grupo', 'STAFF')

    if not ids:
        return JsonResponse({'ok': False, 'error': 'No se seleccionaron empleados.'}, status=400)

    empleados = Personal.objects.filter(id__in=ids)
    enviados = []
    sin_correo = []
    errores = []

    for personal in empleados:
        ok, resultado = _enviar_reporte(personal, anio, mes, grupo)
        if ok:
            enviados.append(personal.apellidos_nombres)
        elif resultado == 'sin_correo':
            sin_correo.append(personal.apellidos_nombres)
        else:
            errores.append(personal.apellidos_nombres)

    return JsonResponse({
        'ok': True,
        'enviados': len(enviados),
        'sin_correo': sin_correo,
        'errores': errores,
    })


# ========== HTML BUILDERS ==========

CSS = """@page{size:297mm 250mm;margin:5mm 7mm}
body{font-family:Helvetica;font-size:7pt;color:#1a202c;margin:0;padding:0}
table{border-collapse:collapse}
td,th{padding:0;text-align:center;font-size:6pt}"""


def _header(p, inicio, fin, mes, anio, tipo):
    try:
        from asistencia.membrete_b64 import HEADER_IMG
    except ImportError:
        HEADER_IMG = ''
    area = p.subarea.area.nombre if p.subarea else '-'
    fecha_ing = p.fecha_alta.strftime('%d/%m/%Y') if p.fecha_alta else '-'
    regimen = p.regimen_pension or '-'
    afp = p.afp or ''
    pension = f'{regimen} {afp}'.strip() or '-'

    if HEADER_IMG:
        logo_html = f'<p style="text-align:center;margin:0 0 6px 0"><img src="{HEADER_IMG}" height="50"></p>'
    else:
        logo_html = '<p style="text-align:center;font-size:10pt;font-weight:bold;color:#0f766e;margin:0 0 6px 0">CONSORCIO STILER - RIPCONCIV - TECNOEDIL</p>'

    return f"""{logo_html}
<table style="margin-bottom:3px">
<tr>
<td style="background-color:#0f766e;color:white;padding:4px 10px;text-align:left;font-size:10pt;font-weight:bold">CONTROL DE ASISTENCIA - {tipo}</td>
<td style="background-color:#0f766e;color:white;padding:4px 10px;text-align:left;font-size:10pt;font-weight:bold">{p.apellidos_nombres}</td>
<td style="background-color:#134e4a;color:white;padding:4px 10px;text-align:right;font-size:10pt;font-weight:bold">{MESES[mes].upper()} {anio}</td>
</tr>
</table>
<table style="margin-bottom:3px">
<tr>
<td style="background-color:#f1f5f9;padding:2px 6px;text-align:left;font-size:6.5pt;font-weight:bold;color:#64748b;border:1px solid #e2e8f0">DNI</td>
<td style="padding:2px 6px;text-align:left;font-size:7.5pt;font-weight:bold;border:1px solid #e2e8f0">{p.nro_doc}</td>
<td style="background-color:#f1f5f9;padding:2px 6px;text-align:left;font-size:6.5pt;font-weight:bold;color:#64748b;border:1px solid #e2e8f0">Cargo</td>
<td style="padding:2px 6px;text-align:left;font-size:7.5pt;border:1px solid #e2e8f0">{p.cargo}</td>
<td style="background-color:#f1f5f9;padding:2px 6px;text-align:left;font-size:6.5pt;font-weight:bold;color:#64748b;border:1px solid #e2e8f0">Area</td>
<td style="padding:2px 6px;text-align:left;font-size:7.5pt;border:1px solid #e2e8f0">{area}</td>
</tr>
<tr>
<td style="background-color:#f1f5f9;padding:2px 6px;text-align:left;font-size:6.5pt;font-weight:bold;color:#64748b;border:1px solid #e2e8f0">Condicion</td>
<td style="padding:2px 6px;text-align:left;font-size:7.5pt;border:1px solid #e2e8f0">{p.condicion}</td>
<td style="background-color:#f1f5f9;padding:2px 6px;text-align:left;font-size:6.5pt;font-weight:bold;color:#64748b;border:1px solid #e2e8f0">F.Ingreso</td>
<td style="padding:2px 6px;text-align:left;font-size:7.5pt;border:1px solid #e2e8f0">{fecha_ing}</td>
<td style="background-color:#f1f5f9;padding:2px 6px;text-align:left;font-size:6.5pt;font-weight:bold;color:#64748b;border:1px solid #e2e8f0">Pension</td>
<td style="padding:2px 6px;text-align:left;font-size:7.5pt;border:1px solid #e2e8f0">{pension}</td>
</tr>
</table>"""


def _resumen_staff(conteo):
    """Render resumen as a proper table for STAFF."""
    total = sum(conteo.values())
    sorted_items = sorted(conteo.items(), key=lambda x: -x[1])
    r = '<table style="margin-bottom:4px"><tr>'
    r += f'<td style="background-color:#14532d;color:white;padding:5px 10px;font-size:8pt;font-weight:bold">RESUMEN: {total} dias</td>'
    for code, count in sorted_items:
        bg = CODE_COLORS.get(code, '#f1f5f9')
        r += f'<td style="background-color:{bg};padding:5px 8px;font-size:8pt;font-weight:bold;border:1px solid #cbd5e0">{code} = {count}</td>'
    r += '</tr></table>'
    return r


def _resumen_rco(totales):
    """Render resumen as a proper table for RCO."""
    he_t = totales['he_25'] + totales['he_35'] + totales['he_100']
    total_all = totales['normales'] + he_t
    r = '<table style="margin-bottom:4px"><tr>'
    r += '<td style="background-color:#14532d;color:white;padding:5px 10px;font-size:8pt;font-weight:bold">RESUMEN HORAS</td>'
    r += f'<td style="background-color:#dcfce7;padding:5px 8px;font-size:8pt;border:1px solid #86efac"><b style="color:#14532d">Normal: {totales["normales"]:.1f}h</b></td>'
    r += f'<td style="background-color:#dbeafe;padding:5px 8px;font-size:8pt;border:1px solid #93c5fd"><b style="color:#1e40af">HE 25%: {totales["he_25"]:.1f}h</b></td>'
    r += f'<td style="background-color:#fed7aa;padding:5px 8px;font-size:8pt;border:1px solid #fdba74"><b style="color:#9a3412">HE 35%: {totales["he_35"]:.1f}h</b></td>'
    r += f'<td style="background-color:#fecaca;padding:5px 8px;font-size:8pt;border:1px solid #fca5a5"><b style="color:#991b1b">HE 100%: {totales["he_100"]:.1f}h</b></td>'
    r += f'<td style="background-color:#fef9c3;padding:5px 8px;font-size:8pt;border:1px solid #fde047"><b style="color:#854d0e">Total HE: {he_t:.1f}h</b></td>'
    r += f'<td style="background-color:#f0fdf4;padding:5px 8px;font-size:8pt;border:1px solid #86efac"><b style="color:#14532d">TOTAL: {total_all:.1f}h</b></td>'
    r += '</tr></table>'
    return r


def _papeletas_sec(papeletas):
    if not papeletas:
        return ''
    r = '<table style="margin-top:4px">'
    # Title row
    r += '<tr>'
    r += '<td style="background-color:#14532d;color:white;padding:5px 10px;text-align:left;font-size:8pt;font-weight:bold">PAPELETAS DEL PERIODO</td>'
    r += '<td style="background-color:#14532d;padding:5px 8px">&nbsp;</td>'
    r += '<td style="background-color:#14532d;padding:5px 8px">&nbsp;</td>'
    r += '<td style="background-color:#14532d;padding:5px 8px">&nbsp;</td>'
    r += '<td style="background-color:#14532d;padding:5px 8px">&nbsp;</td>'
    r += '</tr>'
    # Column headers
    r += '<tr>'
    r += '<td style="background-color:#334155;color:white;padding:4px 10px;text-align:left;font-size:7pt;font-weight:bold">Tipo de Permiso</td>'
    r += '<td style="background-color:#334155;color:white;padding:4px 8px;font-size:7pt;font-weight:bold">Inicio</td>'
    r += '<td style="background-color:#334155;color:white;padding:4px 8px;font-size:7pt;font-weight:bold">Fin</td>'
    r += '<td style="background-color:#334155;color:white;padding:4px 8px;font-size:7pt;font-weight:bold">Dias</td>'
    r += '<td style="background-color:#334155;color:white;padding:4px 8px;font-size:7pt;font-weight:bold">Estado</td>'
    r += '</tr>'
    for idx, p in enumerate(papeletas):
        bg = '#f8fafc' if idx % 2 == 0 else '#f1f5f9'
        estado = p["estado"] or '-'
        if estado.lower() == 'aprobado':
            estado_color = '#16a34a'
        elif estado.lower() == 'rechazado':
            estado_color = '#dc2626'
        else:
            estado_color = '#64748b'
        r += '<tr>'
        r += f'<td style="background-color:{bg};text-align:left;padding:4px 10px;font-size:7pt;border-bottom:1px solid #e2e8f0">{p["tipo_permiso"].replace("_"," ").title()}</td>'
        r += f'<td style="background-color:{bg};padding:4px 8px;font-size:7pt;border-bottom:1px solid #e2e8f0">{p["fecha_inicio"].strftime("%d/%m/%Y")}</td>'
        r += f'<td style="background-color:{bg};padding:4px 8px;font-size:7pt;border-bottom:1px solid #e2e8f0">{p["fecha_fin"].strftime("%d/%m/%Y")}</td>'
        r += f'<td style="background-color:{bg};padding:4px 8px;font-size:7pt;font-weight:bold;border-bottom:1px solid #e2e8f0">{p["dias_habiles"]}</td>'
        r += f'<td style="background-color:{bg};padding:4px 8px;font-size:7pt;font-weight:bold;color:{estado_color};border-bottom:1px solid #e2e8f0">{estado}</td>'
        r += '</tr>'
    r += '</table>'
    return r


def _firma():
    return """<table style="margin-top:4px">
<tr>
<td style="padding:8px 40px 0 20px;text-align:center;font-size:6pt">&nbsp;</td>
<td style="padding:8px 40px;text-align:center;font-size:6pt">&nbsp;</td>
</tr>
<tr>
<td style="padding:2px 40px 0 20px;border-top:1px solid #334155;text-align:center;font-size:7pt;font-weight:bold;color:#334155">Firma del Trabajador</td>
<td style="padding:2px 40px;border-top:1px solid #334155;text-align:center;font-size:7pt;font-weight:bold;color:#334155">Recursos Humanos</td>
</tr>
</table>"""


def _footer():
    return f'<p style="font-size:5pt;color:#94a3b8;text-align:center;margin-top:6px;border-top:1px solid #e2e8f0;padding-top:2px">Harmoni ERP - {date.today().strftime("%d/%m/%Y %H:%M")}</p>'


def _group_weeks(dias):
    """Group days into weeks (Mon=0 to Sun=6)."""
    semanas = []
    sem = [None] * 7
    for d in dias:
        dow = d['fecha'].weekday()
        sem[dow] = d
        if dow == 6:
            semanas.append(sem)
            sem = [None] * 7
    if any(x is not None for x in sem):
        semanas.append(sem)
    return semanas


def _render_staff_html(personal, dias, conteo, papeletas, inicio, fin, mes, anio):
    """STAFF: calendario semanal. Each day: small date + large code in single cell."""
    semanas = _group_weeks(dias)

    # Week day header row
    hdr = '<tr>'
    for i, ds in enumerate(['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo']):
        if i == 6:
            bg = '#1e293b'
        elif i == 5:
            bg = '#334155'
        else:
            bg = '#475569'
        hdr += f'<td style="background-color:{bg};color:white;font-weight:bold;padding:5px 8px;font-size:7pt">{ds}</td>'
    hdr += '</tr>'

    # Build week rows: fecha row + code row (NO nested tables)
    weeks_html = ''
    for sem in semanas:
        # Row 1: fechas
        frow = '<tr>'
        for i, cell in enumerate(sem):
            bg = '#edf2f7' if i < 5 else '#e2e8f0'
            if cell:
                frow += f'<td style="background-color:{bg};font-size:7pt;font-weight:bold;color:#1e293b;padding:2px 4px;border:1px solid #cbd5e0;text-decoration:underline">{cell["fecha"].strftime("%d/%m")}</td>'
            else:
                frow += f'<td style="background-color:#f1f5f9;padding:2px 4px;border:1px solid #e2e8f0">&nbsp;</td>'
        frow += '</tr>'

        # Row 2: codigos
        crow = '<tr>'
        for i, cell in enumerate(sem):
            if cell and cell['display']:
                bg = CODE_COLORS.get(cell['codigo'], '#f7fafc')
                crow += f'<td style="background-color:{bg};font-size:13pt;font-weight:bold;color:#1e293b;padding:6px 4px;border:1px solid #cbd5e0">{cell["display"]}</td>'
            elif cell:
                crow += f'<td style="background-color:#f8fafc;font-size:13pt;color:#d1d5db;padding:6px 4px;border:1px solid #e2e8f0">-</td>'
            else:
                crow += '<td style="background-color:#f1f5f9;padding:6px 4px;border:1px solid #e2e8f0">&nbsp;</td>'
        crow += '</tr>'

        weeks_html += frow + crow

    # Legend as colored cells
    legend_items = [
        ('A', 'Asistencia'), ('DS', 'Desc.Semanal'), ('DL', 'Dia Libre'),
        ('VAC', 'Vacaciones'), ('F', 'Falta'), ('DM', 'D.Medico'),
        ('CHE', 'Compensacion'), ('LSG', 'Lic.S/Goce'), ('FR', 'Feriado'),
    ]
    legend = '<table style="margin-top:4px"><tr>'
    for code, label in legend_items:
        bg = CODE_COLORS.get(code, '#f1f5f9')
        legend += f'<td style="background-color:{bg};padding:2px 5px;font-size:5pt;border:1px solid #e2e8f0"><b>{code}</b>={label}</td>'
    legend += '</tr></table>'

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
{_header(personal, inicio, fin, mes, anio, 'STAFF')}
{_resumen_staff(conteo)}
<table>
{hdr}
{weeks_html}
</table>
{legend}
{_papeletas_sec(papeletas)}
{_firma()}
{_footer()}
</body></html>"""


def _render_rco_html(personal, dias, totales, papeletas, inicio, fin, mes, anio):
    """RCO: calendario semanal. Each cell: date+code top, structured hours below."""
    semanas = _group_weeks(dias)

    # Week day header
    hdr = '<tr>'
    for i, ds in enumerate(['Lunes', 'Martes', 'Miercoles', 'Jueves', 'Viernes', 'Sabado', 'Domingo']):
        if i == 6:
            bg = '#1e293b'
        elif i == 5:
            bg = '#334155'
        else:
            bg = '#475569'
        hdr += f'<td style="background-color:{bg};color:white;font-weight:bold;padding:5px 8px;font-size:7pt">{ds}</td>'
    hdr += '</tr>'

    weeks_html = ''
    for sem in semanas:
        # Fila 1: fecha + codigo
        r1 = '<tr>'
        for cell in sem:
            if cell:
                bg = CODE_COLORS.get(cell['codigo'], '#f7fafc')
                cod = cell['codigo'] if cell['codigo'] else '-'
                r1 += f'<td style="background-color:{bg};border:1px solid #cbd5e0;padding:2px 3px;vertical-align:top"><span style="font-size:6.5pt;color:#334155;text-decoration:underline">{cell["fecha"].strftime("%d/%m")}</span> <span style="font-size:10pt;font-weight:bold;color:#1e293b">{cod}</span></td>'
            else:
                r1 += '<td style="background-color:#f1f5f9;border:1px solid #e2e8f0;padding:2px 3px">&nbsp;</td>'
        r1 += '</tr>'

        # Fila 2: Hrs normal
        r2 = '<tr>'
        for cell in sem:
            if cell and cell['n']:
                r2 += f'<td style="border:1px solid #e2e8f0;padding:1px 3px;font-size:6pt;background-color:#f0fff4"><span style="color:#64748b">Hrs:</span> <span style="font-weight:bold;color:#0f766e;font-size:7pt">{cell["n"]:.1f}</span></td>'
            else:
                r2 += '<td style="border:1px solid #e2e8f0;padding:1px 3px;background-color:#fafafa">&nbsp;</td>'
        r2 += '</tr>'

        # Fila 3: HE 25%
        r3 = '<tr>'
        for cell in sem:
            if cell and cell['h25']:
                r3 += f'<td style="border:1px solid #e2e8f0;padding:1px 3px;font-size:6pt;background-color:#eff6ff"><span style="color:#64748b">HE25:</span> <span style="font-weight:bold;color:#1e40af;font-size:7pt">{cell["h25"]:.1f}</span></td>'
            else:
                r3 += '<td style="border:1px solid #e2e8f0;padding:1px 3px;background-color:#fafafa">&nbsp;</td>'
        r3 += '</tr>'

        # Fila 4: HE 35%
        r4 = '<tr>'
        for cell in sem:
            if cell and cell['h35']:
                r4 += f'<td style="border:1px solid #e2e8f0;padding:1px 3px;font-size:6pt;background-color:#fffbeb"><span style="color:#64748b">HE35:</span> <span style="font-weight:bold;color:#9a3412;font-size:7pt">{cell["h35"]:.1f}</span></td>'
            else:
                r4 += '<td style="border:1px solid #e2e8f0;padding:1px 3px;background-color:#fafafa">&nbsp;</td>'
        r4 += '</tr>'

        # Fila 5: HE 100%
        r5 = '<tr>'
        for cell in sem:
            if cell and cell['h100']:
                r5 += f'<td style="border:1px solid #e2e8f0;padding:1px 3px;font-size:6pt;background-color:#fef2f2"><span style="color:#64748b">H100:</span> <span style="font-weight:bold;color:#991b1b;font-size:7pt">{cell["h100"]:.1f}</span></td>'
            else:
                r5 += '<td style="border:1px solid #e2e8f0;padding:1px 3px;background-color:#fafafa">&nbsp;</td>'
        r5 += '</tr>'

        weeks_html += r1 + r2 + r3 + r4 + r5

    # Hours legend
    legend = '<table style="margin-top:4px"><tr>'
    legend += '<td style="background-color:#dcfce7;padding:3px 8px;font-size:5.5pt;border:1px solid #bbf7d0"><b style="color:#0f766e">Hrs</b> = Normal</td>'
    legend += '<td style="background-color:#dbeafe;padding:3px 8px;font-size:5.5pt;border:1px solid #93c5fd"><b style="color:#1e40af">HE25</b> = Extra 25%</td>'
    legend += '<td style="background-color:#fed7aa;padding:3px 8px;font-size:5.5pt;border:1px solid #fdba74"><b style="color:#9a3412">HE35</b> = Extra 35%</td>'
    legend += '<td style="background-color:#fecaca;padding:3px 8px;font-size:5.5pt;border:1px solid #fca5a5"><b style="color:#991b1b">H100</b> = Extra 100%</td>'
    legend += '</tr></table>'

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
{_header(personal, inicio, fin, mes, anio, 'RCO')}
{_resumen_rco(totales)}
<table>
{hdr}
{weeks_html}
</table>
{legend}
{_papeletas_sec(papeletas)}
{_firma()}
{_footer()}
</body></html>"""
