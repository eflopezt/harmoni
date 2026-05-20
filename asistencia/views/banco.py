"""
Vistas del módulo Tareo — Banco de Horas.
"""
import io
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone

from xhtml2pdf import pisa

from asistencia.services.periodo_helper import get_periodo, TIPO_MES_CORTE
from asistencia.views._common import solo_admin, _papeletas_por_fecha, CODIGOS_AUSENCIA_PAGADA


MESES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
         'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

DIAS_CORTO = ['L', 'M', 'Mi', 'J', 'V', 'S', 'D']


# ---------------------------------------------------------------------------
# BANCO DE HORAS (solo STAFF)
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def banco_horas_view(request):
    """Saldo del banco de horas acumulativas por personal STAFF."""
    from asistencia.models import BancoHoras

    anio = request.GET.get('anio', timezone.now().year)
    try:
        anio = int(anio)
    except (ValueError, TypeError):
        anio = timezone.now().year

    mes = request.GET.get('mes', '')
    buscar = request.GET.get('buscar', '').strip()

    qs = BancoHoras.objects.filter(periodo_anio=anio).select_related('personal')

    if mes:
        try:
            qs = qs.filter(periodo_mes=int(mes))
        except (ValueError, TypeError):
            pass

    if buscar:
        qs = qs.filter(
            Q(personal__apellidos_nombres__icontains=buscar) |
            Q(personal__nro_doc__icontains=buscar)
        )

    qs = qs.order_by('-periodo_mes', 'personal__apellidos_nombres')

    totales = qs.aggregate(
        t_acum_25=Sum('he_25_acumuladas'),
        t_acum_35=Sum('he_35_acumuladas'),
        t_acum_100=Sum('he_100_acumuladas'),
        t_compensadas=Sum('he_compensadas'),
        t_saldo=Sum('saldo_horas'),
    )

    anios_disponibles = (
        BancoHoras.objects
        .values_list('periodo_anio', flat=True)
        .distinct()
        .order_by('-periodo_anio')
    )

    MESES_SEL = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre'),
    ]

    context = {
        'titulo': 'Banco de Horas — STAFF',
        'banco_list': qs,
        'totales': totales,
        'anio_sel': anio,
        'mes_sel': mes,
        'buscar': buscar,
        'anios': anios_disponibles,
        'meses': MESES_SEL,
        'total_personas': qs.values('personal').distinct().count(),
    }
    return render(request, 'asistencia/banco_horas.html', context)


# ---------------------------------------------------------------------------
# PDF — Banco de Horas individual (detalle diario)
# ---------------------------------------------------------------------------

def _get_ciclo(anio, mes):
    """Ciclo STAFF: usa el helper unificado de período (MES_CORTE).

    Con dia_corte=21 → ciclo 22 mes anterior → 21 mes actual.
    """
    periodo = get_periodo(TIPO_MES_CORTE, anio, mes)
    return periodo.fecha_inicio, periodo.fecha_fin


def _render_pdf(html_string):
    buffer = io.BytesIO()
    pisa_status = pisa.CreatePDF(io.StringIO(html_string), dest=buffer, encoding='utf-8')
    if pisa_status.err:
        return None
    return buffer.getvalue()


CODE_COLORS = {
    'T': '#c6f6d5', 'A': '#c6f6d5', 'NOR': '#c6f6d5', 'SS': '#c6f6d5', 'TR': '#c6f6d5',
    'FA': '#fed7d7', 'F': '#fed7d7', 'SAI': '#fed7d7',
    'VAC': '#bee3f8', 'DL': '#e2e8f0', 'DLA': '#e2e8f0', 'DS': '#e2e8f0',
    'DM': '#fefcbf', 'CHE': '#feebc8', 'CDT': '#feebc8', 'CPF': '#feebc8',
    'LSG': '#e9d8fd', 'LCG': '#c4f1f9', 'LF': '#c4f1f9', 'FER': '#fed7e2',
    'FL': '#fbb6ce', 'DSL': '#fbb6ce',
    'NA': '#edf2f7',
}

CSS = """@page{size:297mm 210mm;margin:5mm 7mm}
body{font-family:Helvetica;font-size:7pt;color:#1a202c;margin:0;padding:0}
table{border-collapse:collapse}
td,th{padding:0;text-align:center;font-size:7pt}"""


# Alias local para compatibilidad con código de esta vista
CODIGOS_DIA_PAGADO = CODIGOS_AUSENCIA_PAGADA

# Jornada estándar para ausencias pagadas (jornada legal 8h, no depende de condición)
JORNADA_AUSENCIA = 8.0


def _get_jornada_dia(condicion, dia_semana):
    """Jornada diaria según condición y día — misma lógica que processor."""
    from asistencia.models import ConfiguracionSistema
    config = ConfiguracionSistema.get()
    cond_norm = (condicion or '').upper().replace('Á', 'A')
    if dia_semana == 6:
        if cond_norm == 'FORANEO':
            # FORÁNEO: domingo es parte del ciclo 21×7, jornada reducida 4h
            return float(config.jornada_domingo_horas)
        # LOCAL/LIMA: domingo es descanso semanal, si labora todo al 100%
        return 0.0
    if cond_norm == 'FORANEO':
        return float(config.jornada_foraneo_horas)
    if dia_semana == 5:
        return float(config.jornada_sabado_horas)
    return float(config.jornada_local_horas)


def _build_banco_detail(personal, inicio, fin):
    """
    Construye detalle diario de horas para el banco.
    Retorna lista de dicts por día + totales.
    Aplica las mismas reglas que el processor:
    - SS: jornada completa, sin HE
    - Marcación incompleta (<jornada/2): SS implícito
    - Ausencias pagadas (DL, VAC, etc.): 8h jornada legal
    """
    from asistencia.models import RegistroTareo

    all_regs = list(RegistroTareo.objects.filter(
        personal=personal, fecha__gte=inicio, fecha__lte=fin,
    ).order_by('fecha', 'pk').values(
        'fecha', 'codigo_dia', 'fuente_codigo',
        'horas_marcadas', 'horas_normales', 'he_25', 'he_35', 'he_100',
    ))

    # Dedup: RELOJ gana
    tareo_map = {}
    for r in all_regs:
        f = r['fecha']
        ex = tareo_map.get(f)
        if ex is None:
            tareo_map[f] = r
        elif r['fuente_codigo'] == 'RELOJ':
            tareo_map[f] = r

    # Papeletas como fallback
    pap_map = _papeletas_por_fecha(personal.pk, inicio, fin)

    condicion = personal.condicion or 'LOCAL'
    dias = []
    tot = {'hn': Decimal('0'), 'h25': Decimal('0'), 'h35': Decimal('0'), 'h100': Decimal('0')}

    d = inicio
    while d <= fin:
        # Fuera de periodo laboral
        if (personal.fecha_alta and d < personal.fecha_alta) or \
           (personal.fecha_cese and d > personal.fecha_cese):
            d += timedelta(days=1)
            continue

        jornada = _get_jornada_dia(condicion, d.weekday())

        reg = tareo_map.get(d)
        if reg:
            codigo = reg['codigo_dia']
            marc = float(reg['horas_marcadas'] or 0)
            hn = float(reg['horas_normales'] or 0)
            h25 = float(reg['he_25'] or 0)
            h35 = float(reg['he_35'] or 0)
            h100 = float(reg['he_100'] or 0)

            # Marcación incompleta: horas < jornada/2 → SS implícito
            if (marc > 0 and marc < jornada / 2
                    and codigo not in CODIGOS_DIA_PAGADO
                    and codigo not in ('SS', 'FA', 'DS')):
                hn = jornada
                h25 = h35 = h100 = 0
        else:
            # Papeleta → LIMA auto-A → DS domingo → FA
            pap_cod = pap_map.get(d)
            if pap_cod:
                codigo = pap_cod
            elif d.weekday() == 6 and condicion.upper() in ('LOCAL', 'LIMA', ''):
                codigo = 'DS'
            elif condicion.upper() == 'LIMA' and d.weekday() < 6:
                codigo = 'A'
                hn = JORNADA_AUSENCIA
            else:
                codigo = 'FA'
            if codigo not in ('A',):
                hn = h25 = h35 = h100 = 0

        # Ausencias pagadas (DL, VAC, licencias, etc.) = 8h jornada legal
        if codigo in CODIGOS_DIA_PAGADO and hn == 0:
            hn = JORNADA_AUSENCIA

        he_total = h25 + h35 + h100
        dias.append({
            'fecha': d,
            'dow': DIAS_CORTO[d.weekday()],
            'codigo': codigo,
            'hn': hn, 'h25': h25, 'h35': h35, 'h100': h100,
            'he_total': he_total,
        })
        tot['hn'] += Decimal(str(hn))
        tot['h25'] += Decimal(str(h25))
        tot['h35'] += Decimal(str(h35))
        tot['h100'] += Decimal(str(h100))
        d += timedelta(days=1)

    return dias, {k: float(v) for k, v in tot.items()}


def _render_banco_html(personal, banco, dias, totales, papeletas, mes, anio):
    """Genera HTML del reporte PDF de Banco de Horas."""
    from asistencia.views.reporte_individual import _header, _papeletas_sec, _firma, _footer

    inicio, fin = _get_ciclo(anio, mes)
    header = _header(personal, inicio, fin, mes, anio, 'BANCO DE HORAS')

    # Resumen banco
    he_total = totales['h25'] + totales['h35'] + totales['h100']
    compensadas = float(banco.he_compensadas) if banco else 0
    saldo = he_total - compensadas

    resumen = '<table style="margin-bottom:4px"><tr>'
    resumen += '<td style="background-color:#14532d;color:white;padding:5px 10px;font-size:8pt;font-weight:bold">BANCO DE HORAS</td>'
    resumen += f'<td style="background-color:#dbeafe;padding:5px 8px;font-size:8pt;border:1px solid #93c5fd"><b style="color:#1e40af">HE 25%: {totales["h25"]:.2f}h</b></td>'
    resumen += f'<td style="background-color:#fed7aa;padding:5px 8px;font-size:8pt;border:1px solid #fdba74"><b style="color:#9a3412">HE 35%: {totales["h35"]:.2f}h</b></td>'
    resumen += f'<td style="background-color:#fecaca;padding:5px 8px;font-size:8pt;border:1px solid #fca5a5"><b style="color:#991b1b">HE 100%: {totales["h100"]:.2f}h</b></td>'
    resumen += f'<td style="background-color:#fef9c3;padding:5px 8px;font-size:8pt;border:1px solid #fde047"><b style="color:#854d0e">Total HE: {he_total:.2f}h</b></td>'
    resumen += f'<td style="background-color:#fce7f3;padding:5px 8px;font-size:8pt;border:1px solid #f9a8d4"><b style="color:#9d174d">Compensadas: {compensadas:.2f}h</b></td>'
    saldo_color = '#14532d' if saldo >= 0 else '#991b1b'
    saldo_bg = '#dcfce7' if saldo >= 0 else '#fecaca'
    resumen += f'<td style="background-color:{saldo_bg};padding:5px 10px;font-size:9pt;border:1px solid #86efac"><b style="color:{saldo_color}">SALDO: {saldo:.2f}h</b></td>'
    resumen += '</tr></table>'

    # Tabla detalle diario — landscape, misma estructura que lista PDF (que sí funciona)
    H = 'background-color:#334155;color:white;padding:4px 8px;font-size:7.5pt;font-weight:bold'
    tbl = '<table width="100%" style="margin-bottom:4px">'
    tbl += '<tr>'
    tbl += f'<td style="{H};text-align:left">Fecha</td>'
    tbl += f'<td style="{H}">Dia</td>'
    tbl += f'<td style="{H}">Codigo</td>'
    tbl += f'<td style="{H}">H.Normal</td>'
    tbl += f'<td style="{H};background:#1e40af">HE 25%</td>'
    tbl += f'<td style="{H};background:#9a3412">HE 35%</td>'
    tbl += f'<td style="{H};background:#991b1b">HE 100%</td>'
    tbl += f'<td style="{H};background:#854d0e">Total HE</td>'
    tbl += '</tr>'

    for idx, d in enumerate(dias):
        bg = '#ffffff' if idx % 2 == 0 else '#f8fafc'
        if d['fecha'].weekday() >= 5:
            bg = '#f0f4ff' if idx % 2 == 0 else '#e8edff'

        cod_bg = CODE_COLORS.get(d['codigo'], bg)
        c = f'border-bottom:1px solid #e2e8f0;padding:3px 8px;font-size:7.5pt'

        hn_s = f'{d["hn"]:.1f}' if d['hn'] else '-'
        # Celdas vacías con &nbsp; para que no colapsen
        h25_s = f'{d["h25"]:.1f}' if d['h25'] else '&nbsp;'
        h35_s = f'{d["h35"]:.1f}' if d['h35'] else '&nbsp;'
        h100_s = f'{d["h100"]:.1f}' if d['h100'] else '&nbsp;'
        het_s = f'{d["he_total"]:.1f}' if d['he_total'] else '&nbsp;'

        tbl += f'<tr>'
        tbl += f'<td style="{c};background:{bg};text-align:left">{d["fecha"].strftime("%d/%m")}</td>'
        tbl += f'<td style="{c};background:{bg}">{d["dow"]}</td>'
        tbl += f'<td style="{c};background:{cod_bg};font-weight:bold">{d["codigo"]}</td>'
        tbl += f'<td style="{c};background:{bg};font-weight:bold">{hn_s}</td>'
        tbl += f'<td style="{c};background:{"#dbeafe" if d["h25"] else bg};color:#1e40af;font-weight:bold">{h25_s}</td>'
        tbl += f'<td style="{c};background:{"#fed7aa" if d["h35"] else bg};color:#9a3412;font-weight:bold">{h35_s}</td>'
        tbl += f'<td style="{c};background:{"#fecaca" if d["h100"] else bg};color:#991b1b;font-weight:bold">{h100_s}</td>'
        tbl += f'<td style="{c};background:{"#fef9c3" if d["he_total"] else bg};color:#854d0e;font-weight:bold">{het_s}</td>'
        tbl += f'</tr>'

    # Fila totales
    he_t = totales['h25'] + totales['h35'] + totales['h100']
    T = 'padding:4px 8px;font-size:8pt;font-weight:bold;border-top:2px solid #334155'
    tbl += '<tr>'
    tbl += f'<td colspan="3" style="{T};background:#1e293b;color:white;text-align:left">TOTALES</td>'
    tbl += f'<td style="{T};background:#dcfce7;color:#14532d">{totales["hn"]:.1f}</td>'
    tbl += f'<td style="{T};background:#dbeafe;color:#1e40af">{totales["h25"]:.1f}</td>'
    tbl += f'<td style="{T};background:#fed7aa;color:#9a3412">{totales["h35"]:.1f}</td>'
    tbl += f'<td style="{T};background:#fecaca;color:#991b1b">{totales["h100"]:.1f}</td>'
    tbl += f'<td style="{T};background:#fef9c3;color:#854d0e">{he_t:.1f}</td>'
    tbl += '</tr></table>'

    papeletas_html = _papeletas_sec(papeletas) if papeletas else ''

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
{header}
{resumen}
{tbl}
{papeletas_html}
{_firma()}
{_footer()}
</body></html>"""


@login_required
@solo_admin
def banco_horas_pdf(request, personal_id):
    """Genera PDF del banco de horas de un empleado para un periodo."""
    from asistencia.models import BancoHoras, RegistroPapeleta
    from personal.models import Personal

    personal = get_object_or_404(Personal, pk=personal_id)
    anio = int(request.GET.get('anio', date.today().year))
    mes = int(request.GET.get('mes', date.today().month))

    inicio, fin = _get_ciclo(anio, mes)

    # Banco de este periodo
    banco = BancoHoras.objects.filter(
        personal=personal, periodo_anio=anio, periodo_mes=mes
    ).first()

    # Detalle diario
    dias, totales = _build_banco_detail(personal, inicio, fin)

    # Papeletas — calcular días si dias_habiles es 0 o None
    papeletas = list(RegistroPapeleta.objects.filter(
        personal=personal, fecha_inicio__lte=fin, fecha_fin__gte=inicio
    ).order_by('fecha_inicio').values(
        'tipo_permiso', 'fecha_inicio', 'fecha_fin', 'dias_habiles', 'estado', 'observaciones'
    ))
    for p in papeletas:
        if not p['dias_habiles']:
            p['dias_habiles'] = (p['fecha_fin'] - p['fecha_inicio']).days + 1

    html = _render_banco_html(personal, banco, dias, totales, papeletas, mes, anio)
    pdf = _render_pdf(html)
    if not pdf:
        return HttpResponse('Error generando PDF', status=500)

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'inline; filename="BancoHoras_{personal.nro_doc}_{MESES[mes]}_{anio}.pdf"'
    )
    return response


# ---------------------------------------------------------------------------
# PDF — Listado Banco de Horas (tabla resumen filtrada)
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def banco_horas_lista_pdf(request):
    """PDF del listado de banco de horas con los mismos filtros de la vista web."""
    from asistencia.models import BancoHoras
    from asistencia.views.reporte_individual import _footer

    anio = int(request.GET.get('anio', date.today().year))
    mes_param = request.GET.get('mes', '')
    buscar = request.GET.get('buscar', '').strip()

    qs = BancoHoras.objects.filter(periodo_anio=anio).select_related('personal')

    mes_num = None
    if mes_param:
        try:
            mes_num = int(mes_param)
            qs = qs.filter(periodo_mes=mes_num)
        except (ValueError, TypeError):
            pass

    if buscar:
        qs = qs.filter(
            Q(personal__apellidos_nombres__icontains=buscar) |
            Q(personal__nro_doc__icontains=buscar)
        )

    qs = qs.order_by('personal__apellidos_nombres', 'periodo_mes')

    totales = qs.aggregate(
        t_25=Sum('he_25_acumuladas'),
        t_35=Sum('he_35_acumuladas'),
        t_100=Sum('he_100_acumuladas'),
        t_comp=Sum('he_compensadas'),
        t_saldo=Sum('saldo_horas'),
    )

    # Subtitulo
    filtro_txt = f'{anio}'
    if mes_num:
        filtro_txt = f'{MESES[mes_num]} {anio}'
    if buscar:
        filtro_txt += f' — "{buscar}"'

    try:
        from asistencia.membrete_b64 import HEADER_IMG
    except ImportError:
        HEADER_IMG = ''

    # Nombre de empresa: ConfiguracionSistema.empresa_nombre (multi-tenant
    # safe). Si no hay nombre configurado, fallback genérico (NO hardcodear
    # ningún cliente específico).
    nombre_emp = ''
    try:
        from asistencia.models import ConfiguracionSistema
        _cfg = ConfiguracionSistema.get()
        nombre_emp = (_cfg.empresa_nombre or '').strip()
    except Exception:
        nombre_emp = ''

    if HEADER_IMG:
        logo = f'<p style="text-align:center;margin:0 0 6px 0"><img src="{HEADER_IMG}" height="50"></p>'
    elif nombre_emp:
        logo = f'<p style="text-align:center;font-size:10pt;font-weight:bold;color:#0f766e;margin:0 0 6px 0">{nombre_emp}</p>'
    else:
        logo = '<p style="text-align:center;font-size:10pt;font-weight:bold;color:#0f766e;margin:0 0 6px 0">Reporte de Asistencia</p>'

    # Header
    hdr = f"""{logo}
<table style="margin-bottom:6px">
<tr>
<td style="background-color:#0f766e;color:white;padding:6px 12px;text-align:left;font-size:11pt;font-weight:bold">BANCO DE HORAS — STAFF</td>
<td style="background-color:#134e4a;color:white;padding:6px 12px;text-align:right;font-size:10pt;font-weight:bold">{filtro_txt}</td>
</tr>
</table>"""

    # Resumen
    t_25 = float(totales['t_25'] or 0)
    t_35 = float(totales['t_35'] or 0)
    t_100 = float(totales['t_100'] or 0)
    t_comp = float(totales['t_comp'] or 0)
    t_saldo = float(totales['t_saldo'] or 0)
    t_total = t_25 + t_35 + t_100

    resumen = '<table style="margin-bottom:4px"><tr>'
    resumen += f'<td style="background-color:#dbeafe;padding:4px 8px;font-size:7pt;border:1px solid #93c5fd"><b style="color:#1e40af">HE 25%: {t_25:.2f}h</b></td>'
    resumen += f'<td style="background-color:#fed7aa;padding:4px 8px;font-size:7pt;border:1px solid #fdba74"><b style="color:#9a3412">HE 35%: {t_35:.2f}h</b></td>'
    resumen += f'<td style="background-color:#fecaca;padding:4px 8px;font-size:7pt;border:1px solid #fca5a5"><b style="color:#991b1b">HE 100%: {t_100:.2f}h</b></td>'
    resumen += f'<td style="background-color:#fef9c3;padding:4px 8px;font-size:7pt;border:1px solid #fde047"><b style="color:#854d0e">Total: {t_total:.2f}h</b></td>'
    resumen += f'<td style="background-color:#fce7f3;padding:4px 8px;font-size:7pt;border:1px solid #f9a8d4"><b style="color:#9d174d">Comp: {t_comp:.2f}h</b></td>'
    saldo_bg = '#dcfce7' if t_saldo >= 0 else '#fecaca'
    saldo_color = '#14532d' if t_saldo >= 0 else '#991b1b'
    resumen += f'<td style="background-color:{saldo_bg};padding:4px 10px;font-size:8pt;border:1px solid #86efac"><b style="color:{saldo_color}">Saldo: {t_saldo:.2f}h</b></td>'
    resumen += '</tr></table>'

    # Tabla
    hs = 'background-color:#334155;color:white;padding:4px 6px;font-size:6.5pt;font-weight:bold'
    tbl = '<table style="margin-bottom:4px"><tr>'
    tbl += f'<td style="{hs};text-align:left;min-width:150px">Persona</td>'
    tbl += f'<td style="{hs};min-width:55px">DNI</td>'
    tbl += f'<td style="{hs};min-width:65px">Periodo</td>'
    tbl += f'<td style="{hs};min-width:40px">HE 25%</td>'
    tbl += f'<td style="{hs};min-width:40px">HE 35%</td>'
    tbl += f'<td style="{hs};min-width:40px">HE 100%</td>'
    tbl += f'<td style="{hs};min-width:45px">Comp.</td>'
    tbl += f'<td style="{hs};min-width:45px">Saldo</td>'
    tbl += '</tr>'

    for idx, b in enumerate(qs):
        bg = '#f8fafc' if idx % 2 == 0 else '#f1f5f9'
        cell = f'border-bottom:1px solid #e2e8f0;padding:3px 6px;font-size:6.5pt;background-color:{bg}'
        saldo = float(b.saldo_horas)
        s_color = '#14532d' if saldo > 0 else ('#991b1b' if saldo < 0 else '#64748b')

        tbl += '<tr>'
        tbl += f'<td style="{cell};text-align:left;font-weight:bold">{b.personal.apellidos_nombres}</td>'
        tbl += f'<td style="{cell}">{b.personal.nro_doc}</td>'
        tbl += f'<td style="{cell};font-weight:bold">{MESES[b.periodo_mes]} {b.periodo_anio}</td>'
        tbl += f'<td style="{cell};color:#1e40af">{b.he_25_acumuladas:.2f}</td>'
        tbl += f'<td style="{cell};color:#9a3412">{b.he_35_acumuladas:.2f}</td>'
        tbl += f'<td style="{cell};color:#991b1b">{b.he_100_acumuladas:.2f}</td>'
        comp_val = float(b.he_compensadas)
        tbl += f'<td style="{cell};color:#9d174d">{comp_val:.2f}</td>'
        tbl += f'<td style="{cell};color:{s_color};font-weight:bold">{saldo:.2f}</td>'
        tbl += '</tr>'

    # Footer totales
    ts = 'padding:4px 6px;font-size:7pt;font-weight:bold;border-top:2px solid #334155'
    tbl += '<tr>'
    tbl += f'<td style="{ts};background-color:#1e293b;color:white;text-align:left" colspan="3">TOTALES ({qs.count()} registros)</td>'
    tbl += f'<td style="{ts};background-color:#dbeafe;color:#1e40af">{t_25:.2f}</td>'
    tbl += f'<td style="{ts};background-color:#fed7aa;color:#9a3412">{t_35:.2f}</td>'
    tbl += f'<td style="{ts};background-color:#fecaca;color:#991b1b">{t_100:.2f}</td>'
    tbl += f'<td style="{ts};background-color:#fce7f3;color:#9d174d">{t_comp:.2f}</td>'
    tbl += f'<td style="{ts};background-color:{saldo_bg};color:{saldo_color}">{t_saldo:.2f}</td>'
    tbl += '</tr></table>'

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body>
{hdr}
{resumen}
{tbl}
{_footer()}
</body></html>"""

    pdf = _render_pdf(html)
    if not pdf:
        return HttpResponse('Error generando PDF', status=500)

    fname = f'BancoHoras_{anio}'
    if mes_num:
        fname += f'_{MESES[mes_num]}'
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{fname}.pdf"'
    return response
