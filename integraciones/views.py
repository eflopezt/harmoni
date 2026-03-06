"""
Integraciones Peru -- Vistas.

Panel central de exportaciones hacia sistemas externos SUNAT, AFP, bancos.
"""
import io
from datetime import date

from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import LogExportacion
from .exportadores import (
    generar_t_registro_altas,
    generar_planilla_excel,
    generar_afp_net,
    generar_pago_banco,
    generar_essalud,
)

solo_admin = user_passes_test(lambda u: u.is_superuser, login_url='login')


def _periodo_actual():
    hoy = date.today()
    return f'{hoy.year}-{hoy.month:02d}'


@login_required
@solo_admin
def panel(request):
    from personal.models import Personal
    from django.db.models import Count, Q
    from django.utils import timezone as tz

    activos = Personal.objects.filter(estado='Activo').count()
    con_afp = Personal.objects.filter(estado='Activo', regimen_pension='AFP').count()
    con_onp = Personal.objects.filter(estado='Activo', regimen_pension='ONP').count()
    con_banco = Personal.objects.filter(estado='Activo', cuenta_ahorros__gt='').count()

    logs = LogExportacion.objects.select_related('generado_por')[:20]

    bancos = (
        Personal.objects
        .filter(estado='Activo', banco__gt='')
        .values_list('banco', flat=True)
        .distinct()
        .order_by('banco')
    )

    # Stats for enhanced panel
    hoy = date.today()
    primer_dia_mes = hoy.replace(day=1)
    periodo_actual = _periodo_actual()

    exports_este_mes = LogExportacion.objects.filter(
        generado_en__gte=primer_dia_mes
    ).count()

    exports_exitosos = LogExportacion.objects.filter(
        generado_en__gte=primer_dia_mes, estado='OK'
    ).count()

    exports_error = LogExportacion.objects.filter(
        generado_en__gte=primer_dia_mes, estado='ERROR'
    ).count()

    tasa_exito = 0
    if exports_este_mes > 0:
        tasa_exito = round((exports_exitosos / exports_este_mes) * 100)

    # Last successful export per type
    ultimas_exportaciones = {}
    for tipo_code, tipo_label in LogExportacion.TIPO_CHOICES:
        ultimo = LogExportacion.objects.filter(
            tipo=tipo_code, estado='OK'
        ).order_by('-generado_en').first()
        ultimas_exportaciones[tipo_code] = ultimo

    # Pending count (if you add PENDIENTE state in the future)
    pendientes = LogExportacion.objects.filter(estado='PARCIAL').count()

    context = {
        'activos': activos,
        'con_afp': con_afp,
        'con_onp': con_onp,
        'con_banco': con_banco,
        'logs': logs,
        'periodo_actual': periodo_actual,
        'bancos_disponibles': list(bancos),
        # Enhanced stats
        'exports_este_mes': exports_este_mes,
        'exports_exitosos': exports_exitosos,
        'exports_error': exports_error,
        'tasa_exito': tasa_exito,
        'pendientes': pendientes,
        'ultimas_exportaciones': ultimas_exportaciones,
    }
    return render(request, 'integraciones/panel.html', context)


@login_required
@solo_admin
def exportar_t_registro_altas(request):
    from personal.models import Personal

    periodo = request.GET.get('periodo', _periodo_actual())
    anio, mes = int(periodo[:4]), int(periodo[5:])

    qs = Personal.objects.filter(
        fecha_alta__year=anio,
        fecha_alta__month=mes,
    ).select_related('subarea__area').order_by('apellidos_nombres')

    contenido, count = generar_t_registro_altas(qs)

    LogExportacion.objects.create(
        tipo='T_REGISTRO_ALTA',
        periodo=periodo,
        estado='OK',
        registros=count,
        nombre_archivo=f'TRegistro_Altas_{periodo.replace("-","")}.txt',
        generado_por=request.user,
    )

    response = HttpResponse(contenido, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="TRegistro_Altas_{periodo.replace("-","")}.txt"'
    )
    return response

@login_required
@solo_admin
def exportar_t_registro_bajas(request):
    from personal.models import Personal
    from .exportadores import generar_t_registro_bajas

    periodo = request.GET.get('periodo', _periodo_actual())
    anio, mes = int(periodo[:4]), int(periodo[5:])

    qs = Personal.objects.filter(
        fecha_cese__year=anio,
        fecha_cese__month=mes,
        estado='Cesado',
    ).order_by('apellidos_nombres')

    contenido, count = generar_t_registro_bajas(qs)

    LogExportacion.objects.create(
        tipo='T_REGISTRO_BAJA',
        periodo=periodo,
        estado='OK',
        registros=count,
        nombre_archivo=f'TRegistro_Bajas_{periodo.replace("-","")}.txt',
        generado_por=request.user,
    )

    response = HttpResponse(contenido, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="TRegistro_Bajas_{periodo.replace("-","")}.txt"'
    )
    return response


@login_required
@solo_admin
def exportar_planilla_excel(request):
    from personal.models import Personal

    periodo = request.GET.get('periodo', _periodo_actual())
    area_id = request.GET.get('area', '')
    grupo = request.GET.get('grupo', '')

    qs = Personal.objects.filter(
        estado='Activo'
    ).select_related('subarea__area').order_by('apellidos_nombres')

    if area_id:
        qs = qs.filter(subarea__area_id=area_id)
    if grupo:
        qs = qs.filter(grupo_tareo=grupo)

    contenido, count = generar_planilla_excel(qs, periodo)

    LogExportacion.objects.create(
        tipo='PLANILLA_EXCEL',
        periodo=periodo,
        estado='OK',
        registros=count,
        nombre_archivo=f'Planilla_{periodo.replace("-","")}.csv',
        generado_por=request.user,
    )

    response = HttpResponse(contenido, content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = (
        f'attachment; filename="Planilla_{periodo.replace("-","")}.csv"'
    )
    return response


@login_required
@solo_admin
def exportar_afp_net(request):
    from personal.models import Personal

    periodo = request.GET.get('periodo', _periodo_actual())
    afp_filtro = request.GET.get('afp', '')

    qs = Personal.objects.filter(
        estado='Activo', regimen_pension='AFP'
    ).order_by('apellidos_nombres')
    if afp_filtro:
        qs = qs.filter(afp=afp_filtro)

    contenido, count = generar_afp_net(qs, periodo.replace('-', ''))

    LogExportacion.objects.create(
        tipo='AFP_NET',
        periodo=periodo,
        estado='OK',
        registros=count,
        nombre_archivo=f'AFPNet_{afp_filtro or "TODAS"}_{periodo.replace("-","")}.txt',
        generado_por=request.user,
    )

    response = HttpResponse(contenido, content_type='text/plain; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="AFPNet_{afp_filtro or "TODAS"}_{periodo.replace("-","")}.txt"'
    )
    return response


@login_required
@solo_admin
def exportar_pago_banco(request):
    from personal.models import Personal

    banco = request.GET.get('banco', '')
    periodo = request.GET.get('periodo', _periodo_actual())

    qs = Personal.objects.filter(
        estado='Activo',
        cuenta_ahorros__gt='',
    ).order_by('apellidos_nombres')

    tipo_log = f'BANCO_{banco.upper()[:3]}' if banco else 'BANCO_BCP'
    contenido, count = generar_pago_banco(qs, banco_filtro=banco)

    validos = dict(LogExportacion.TIPO_CHOICES)
    LogExportacion.objects.create(
        tipo=tipo_log if tipo_log in validos else 'OTRO',
        periodo=periodo,
        estado='OK',
        registros=count,
        nombre_archivo=f'Pago_{banco or "TODOS"}_{periodo.replace("-","")}.csv',
        generado_por=request.user,
    )

    response = HttpResponse(contenido, content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = (
        f'attachment; filename="Pago_{banco or "TODOS"}_{periodo.replace("-","")}.csv"'
    )
    return response


@login_required
@solo_admin
def exportar_essalud(request):
    from personal.models import Personal

    periodo = request.GET.get('periodo', _periodo_actual())
    qs = Personal.objects.filter(estado='Activo').order_by('apellidos_nombres')

    contenido, count = generar_essalud(qs, periodo.replace('-', ''))

    LogExportacion.objects.create(
        tipo='ESSALUD',
        periodo=periodo,
        estado='OK',
        registros=count,
        nombre_archivo=f'ESSALUD_{periodo.replace("-","")}.csv',
        generado_por=request.user,
    )

    response = HttpResponse(contenido, content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = (
        f'attachment; filename="ESSALUD_{periodo.replace("-","")}.csv"'
    )
    return response


@login_required
@solo_admin
def preview_exportacion(request):
    from personal.models import Personal
    from decimal import Decimal
    from django.db.models import Sum

    tipo = request.GET.get('tipo', '')
    periodo = request.GET.get('periodo', _periodo_actual())
    banco = request.GET.get('banco', '')

    activos = Personal.objects.filter(estado='Activo')
    data = {}

    if tipo == 'planilla':
        data = {
            'total': activos.count(),
            'con_sueldo': activos.filter(sueldo_base__gt=0).count(),
            'sin_sueldo': activos.filter(sueldo_base__isnull=True).count(),
        }
    elif tipo == 'afp':
        afp_qs = activos.filter(regimen_pension='AFP')
        total_sueldo = afp_qs.aggregate(s=Sum('sueldo_base'))['s'] or 0
        data = {
            'total': afp_qs.count(),
            'total_aportes': float(
                (Decimal(str(total_sueldo)) * Decimal('0.13')).quantize(Decimal('0.01'))
            ),
        }
    elif tipo == 'banco':
        qs = activos.filter(cuenta_ahorros__gt='')
        if banco:
            qs = qs.filter(banco=banco)
        data = {'total': qs.count(), 'banco': banco or 'Todos'}
    elif tipo == 'treg_altas':
        anio, mes = int(periodo[:4]), int(periodo[5:])
        data = {'total': Personal.objects.filter(
            fecha_alta__year=anio, fecha_alta__month=mes
        ).count()}
    elif tipo == 'treg_bajas':
        anio, mes = int(periodo[:4]), int(periodo[5:])
        data = {'total': Personal.objects.filter(
            fecha_cese__year=anio, fecha_cese__month=mes, estado='Cesado'
        ).count()}
    elif tipo == 'essalud':
        data = {'total': activos.count()}

    return JsonResponse(data)


@login_required
@solo_admin
def exportar_plame(request):
    '''Genera archivo PLAME (PDT 601) para SUNAT.'''
    from personal.models import Personal
    from .exportadores import generar_plame

    periodo = request.GET.get('periodo', _periodo_actual())

    qs = Personal.objects.filter(
        estado='Activo'
    ).select_related('subarea__area').order_by('apellidos_nombres')

    nomina_qs = None
    try:
        from nominas.models import RegistroNomina, PeriodoNomina
        anio, mes = int(periodo[:4]), int(periodo[5:])
        periodo_obj = PeriodoNomina.objects.filter(anio=anio, mes=mes, tipo='REGULAR').first()
        if periodo_obj:
            nomina_qs = RegistroNomina.objects.filter(periodo=periodo_obj).select_related('personal')
    except Exception:
        pass

    contenido, count = generar_plame(qs, nomina_qs, periodo.replace('-', ''))

    periodo_clean = periodo.replace('-', '')
    LogExportacion.objects.create(
        tipo='PLAME',
        periodo=periodo,
        estado='OK',
        registros=count,
        nombre_archivo=f'PLAME_{periodo.replace("-","")}.txt',
        generado_por=request.user,
    )

    response = HttpResponse(contenido, content_type='text/plain; charset=utf-8')
    fn = 'PLAME_' + periodo.replace('-', '') + '.txt'
    response['Content-Disposition'] = f'attachment; filename="{fn}"'
    return response


@login_required
@solo_admin
def exportar_banco_especifico(request, banco):
    '''
    Genera archivo de pago en formato especifico del banco.
    banco: bcp | bbva | interbank | scotiabank | nacion
    '''
    from personal.models import Personal
    from .exportadores import (
        generar_bcp_telecredito, generar_bbva_net_cash,
        generar_interbank_masivo, generar_scotiabank_masivo,
        generar_banco_nacion,
    )

    periodo = request.GET.get('periodo', _periodo_actual())

    qs = Personal.objects.filter(
        estado='Activo', cuenta_ahorros__gt=''
    ).order_by('apellidos_nombres')

    BANCO_MAP = {
        'bcp':        ('BCP',        generar_bcp_telecredito,    'txt', 'text/plain'),
        'bbva':       ('BBVA',       generar_bbva_net_cash,      'txt', 'text/plain'),
        'interbank':  ('Interbank',  generar_interbank_masivo,   'txt', 'text/plain'),
        'scotiabank': ('Scotiabank', generar_scotiabank_masivo,  'csv', 'text/csv; charset=utf-8-sig'),
        'nacion':     ('Banco Nacion', generar_banco_nacion,     'txt', 'text/plain'),
    }

    if banco not in BANCO_MAP:
        from django.http import HttpResponseBadRequest
        return HttpResponseBadRequest(f'Banco no soportado: {banco}')

    nombre_banco, generador, ext, content_type = BANCO_MAP[banco]
    descripcion = 'REMUNERACION ' + periodo.replace('-', '/')
    contenido, count = generador(qs, descripcion)
    periodo_clean = periodo.replace('-', '')

    tipo_log = f'BANCO_{nombre_banco[:3].upper()}'
    validos = dict(LogExportacion.TIPO_CHOICES)
    LogExportacion.objects.create(
        tipo=tipo_log if tipo_log in validos else 'OTRO',
        periodo=periodo,
        estado='OK',
        registros=count,
        nombre_archivo=f'Pago_{nombre_banco}_{periodo_clean}.{ext}',
        generado_por=request.user,
    )

    fn = f'Pago_{nombre_banco}_{periodo_clean}.{ext}'
    response = HttpResponse(contenido, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{fn}"'
    return response



# ──────────────────────────────────────────────────────────────────────
# CONTABLES — Asientos de planilla
# ──────────────────────────────────────────────────────────────────────

@login_required
@solo_admin
def exportar_contable(request, formato):
    """
    Genera el asiento contable de un periodo de nomina.
    formato: concar | sigo | sap | sire
    Requiere ?periodo_id=<pk> del PeriodoNomina.
    """
    from django.shortcuts import get_object_or_404
    from nominas.models import PeriodoNomina
    from .contables import (
        generar_asiento_concar, generar_asiento_sigo,
        generar_asiento_sap_excel, generar_sire_libro_diario,
    )

    periodo_id = request.GET.get('periodo_id')
    if not periodo_id:
        # Si no hay periodo, usar el ultimo aprobado/cerrado
        periodo = PeriodoNomina.objects.filter(
            tipo='REGULAR', estado__in=['APROBADO', 'CERRADO']
        ).order_by('-anio', '-mes').first()
    else:
        periodo = get_object_or_404(PeriodoNomina, pk=periodo_id)

    if not periodo:
        messages.error(request, 'No hay periodos de nomina aprobados. Genera y aprueba un periodo primero.')
        return redirect('integraciones_panel')

    FORMATO_MAP = {
        'concar': ('concar', generar_asiento_concar,   'csv',  'text/csv; charset=utf-8-sig',                                           '.csv'),
        'sigo':   ('sigo',   generar_asiento_sigo,     'txt',  'text/plain; charset=utf-8',                                             '.txt'),
        'sap':    ('sap',    generar_asiento_sap_excel, 'xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',     '.xlsx'),
        'sire':   ('sire',   generar_sire_libro_diario, 'txt', 'text/plain; charset=utf-8',                                             '.txt'),
    }

    if formato not in FORMATO_MAP:
        return redirect('integraciones_panel')

    nombre_fmt, generador, ext, content_type, sufijo = FORMATO_MAP[formato]

    try:
        contenido, count = generador(periodo)
    except Exception as e:
        messages.error(request, f'Error generando asiento {formato.upper()}: {e}')
        return redirect('integraciones_panel')

    periodo_str    = f'{periodo.anio}{periodo.mes:02d}'
    nombre_archivo = f'Asiento_{nombre_fmt.upper()}_{periodo_str}{sufijo}'

    TIPO_CONTABLE = {
        'concar': 'CONCAR', 'sigo': 'SIGO',
        'sap': 'SAP_EXCEL', 'sire': 'SIRE_PLE',
    }
    LogExportacion.objects.create(
        tipo=TIPO_CONTABLE.get(formato, 'OTRO'),
        periodo=f'{periodo.anio}-{periodo.mes:02d}',
        estado='OK',
        registros=count,
        nombre_archivo=nombre_archivo,
        generado_por=request.user,
    )

    if isinstance(contenido, bytes):
        response = HttpResponse(contenido, content_type=content_type)
    else:
        encoded = contenido.encode('utf-8-sig') if 'csv' in content_type else contenido.encode('utf-8')
        response = HttpResponse(encoded, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{nombre_archivo}"'
    return response


@login_required
@solo_admin
def panel_contable(request):
    """Panel de exportaciones contables — muestra formatos disponibles y selector de periodo."""
    from nominas.models import PeriodoNomina

    periodos = PeriodoNomina.objects.filter(
        estado__in=['CALCULADO', 'APROBADO', 'CERRADO']
    ).order_by('-anio', '-mes')[:12]

    return render(request, 'integraciones/panel_contable.html', {
        'titulo': 'Integraciones Contables',
        'periodos': periodos,
    })


# ──────────────────────────────────────────────────────────────────────
# PLAME PREVIEW
# ──────────────────────────────────────────────────────────────────────

@login_required
@solo_admin
def plame_preview(request):
    """
    Vista previa de datos PLAME antes de exportar.
    Muestra tabla con DNI, nombre, sueldo base, AFP/ONP, EsSalud y totales.
    """
    from personal.models import Personal
    from decimal import Decimal
    from django.db.models import Sum

    periodo = request.GET.get('periodo', _periodo_actual())

    if request.method == 'POST':
        return redirect(f'/integraciones/plame/?periodo={periodo}')

    qs = Personal.objects.filter(
        estado='Activo'
    ).select_related('subarea__area').order_by('apellidos_nombres')

    # Try to get nomina data
    nomina_data = {}
    periodo_obj = None
    try:
        from nominas.models import RegistroNomina, PeriodoNomina
        anio, mes = int(periodo[:4]), int(periodo[5:])
        periodo_obj = PeriodoNomina.objects.filter(
            anio=anio, mes=mes, tipo='REGULAR'
        ).first()
        if periodo_obj:
            for reg in RegistroNomina.objects.filter(periodo=periodo_obj).select_related('personal'):
                nomina_data[reg.personal_id] = reg
    except Exception:
        pass

    registros = []
    total_sueldo = Decimal('0')
    total_afp = Decimal('0')
    total_onp = Decimal('0')
    total_essalud = Decimal('0')

    for p in qs:
        sueldo = p.sueldo_base or Decimal('0')
        reg = nomina_data.get(p.pk)

        if reg and hasattr(reg, 'total_remuneracion'):
            base = reg.total_remuneracion or sueldo
        else:
            base = sueldo

        es_afp = p.regimen_pension == 'AFP'
        es_onp = p.regimen_pension == 'ONP'

        aporte_afp = (base * Decimal('0.10')).quantize(Decimal('0.01')) if es_afp else Decimal('0')
        aporte_onp = (base * Decimal('0.13')).quantize(Decimal('0.01')) if es_onp else Decimal('0')
        aporte_essalud = (base * Decimal('0.09')).quantize(Decimal('0.01'))

        total_sueldo += base
        total_afp += aporte_afp
        total_onp += aporte_onp
        total_essalud += aporte_essalud

        registros.append({
            'dni': p.nro_doc,
            'nombre': p.apellidos_nombres,
            'sueldo': base,
            'regimen': p.regimen_pension or '—',
            'afp_nombre': p.afp if es_afp else '—',
            'aporte_afp': aporte_afp,
            'aporte_onp': aporte_onp,
            'aporte_essalud': aporte_essalud,
        })

    MAX_PREVIEW = 50
    hay_mas = len(registros) > MAX_PREVIEW
    registros_preview = registros[:MAX_PREVIEW]
    total_registros = len(registros)

    context = {
        'titulo': 'Vista Previa PLAME',
        'periodo': periodo,
        'periodo_obj': periodo_obj,
        'registros': registros_preview,
        'hay_mas': hay_mas,
        'total_registros': total_registros,
        'total_sueldo': total_sueldo,
        'total_afp': total_afp,
        'total_onp': total_onp,
        'total_essalud': total_essalud,
        'total_planilla': total_sueldo + total_essalud,
    }
    return render(request, 'integraciones/plame_preview.html', context)


# ──────────────────────────────────────────────────────────────────────
# AFP NET PANEL
# ──────────────────────────────────────────────────────────────────────

@login_required
@solo_admin
def afp_net_panel(request):
    """
    Panel de exportacion AFP Net por AFP.
    Muestra empleados agrupados por AFP con fecha de ultimo export.
    """
    from personal.models import Personal
    from django.db.models import Sum

    periodo = request.GET.get('periodo', _periodo_actual())

    AFP_LIST = [
        ('Habitat',   'bg-success',  'fas fa-leaf'),
        ('Integra',   'bg-primary',  'fas fa-shield-alt'),
        ('Prima',     'bg-warning',  'fas fa-star'),
        ('Profuturo', 'bg-info',     'fas fa-rocket'),
    ]

    afp_data = []
    for afp_nombre, bg_class, icon in AFP_LIST:
        empleados = Personal.objects.filter(
            estado='Activo', regimen_pension='AFP', afp=afp_nombre
        ).order_by('apellidos_nombres').values(
            'nro_doc', 'apellidos_nombres', 'sueldo_base', 'afp'
        )[:20]

        total_empleados = Personal.objects.filter(
            estado='Activo', regimen_pension='AFP', afp=afp_nombre
        ).count()

        total_aporte = Personal.objects.filter(
            estado='Activo', regimen_pension='AFP', afp=afp_nombre
        ).aggregate(s=Sum('sueldo_base'))['s'] or 0

        from decimal import Decimal
        aporte_estimado = (total_aporte * Decimal('0.13')) if total_aporte else Decimal('0')

        ultimo_export = LogExportacion.objects.filter(
            tipo='AFP_NET', estado='OK'
        ).order_by('-generado_en').first()

        hay_mas = total_empleados > 20

        afp_data.append({
            'nombre': afp_nombre,
            'bg_class': bg_class,
            'icon': icon,
            'total_empleados': total_empleados,
            'empleados': list(empleados),
            'hay_mas': hay_mas,
            'aporte_estimado': round(aporte_estimado, 2),
            'ultimo_export': ultimo_export,
        })

    total_afp = Personal.objects.filter(estado='Activo', regimen_pension='AFP').count()

    context = {
        'titulo': 'AFP Net — Panel de Exportación',
        'afp_data': afp_data,
        'total_afp': total_afp,
        'periodo': periodo,
        'periodo_actual': _periodo_actual(),
    }
    return render(request, 'integraciones/afp_net_panel.html', context)


# ──────────────────────────────────────────────────────────────────────
# BIOMETRICO IMPORT
# ──────────────────────────────────────────────────────────────────────

@login_required
@solo_admin
def biometrico_import(request):
    """
    Importacion de marcaciones desde reloj biometrico ZKTeco.
    Formato: TAB ID DATE TIME STATUS (cada linea)
    Ejemplo: 1\t001\t2026-03-01\t08:05:33\t0
    """
    registros = []
    errores = []
    archivo_nombre = ''

    if request.method == 'POST':
        archivo = request.FILES.get('archivo')
        if not archivo:
            messages.error(request, 'Debe seleccionar un archivo.')
            return render(request, 'integraciones/biometrico_import.html', {
                'titulo': 'Importar Biométrico',
                'registros': [],
                'errores': [],
            })

        archivo_nombre = archivo.name
        contenido_bytes = archivo.read()

        # Try different encodings common in ZKTeco exports
        for encoding in ('utf-8', 'latin-1', 'cp1252'):
            try:
                contenido = contenido_bytes.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            contenido = contenido_bytes.decode('utf-8', errors='replace')

        lineas = contenido.splitlines()
        for i, linea in enumerate(lineas, 1):
            linea = linea.strip()
            if not linea:
                continue

            # Try tab-separated first, then space-separated
            partes = linea.split('\t') if '\t' in linea else linea.split()

            if len(partes) >= 4:
                try:
                    tab_id = partes[0].strip()
                    emp_id = partes[1].strip()
                    fecha_str = partes[2].strip()
                    hora_str = partes[3].strip()
                    status = partes[4].strip() if len(partes) > 4 else '0'

                    # Validate date and time
                    import re
                    fecha_ok = bool(re.match(r'\d{4}-\d{2}-\d{2}', fecha_str))
                    hora_ok = bool(re.match(r'\d{2}:\d{2}', hora_str))

                    if fecha_ok and hora_ok:
                        registros.append({
                            'linea': i,
                            'tab_id': tab_id,
                            'emp_id': emp_id,
                            'fecha': fecha_str,
                            'hora': hora_str,
                            'status': status,
                            'valido': True,
                        })
                    else:
                        errores.append(f'Línea {i}: formato de fecha/hora inválido — {linea[:60]}')
                except Exception as e:
                    errores.append(f'Línea {i}: error al parsear — {str(e)[:80]}')
            else:
                if len(partes) > 1:  # Skip completely empty or single-field lines
                    errores.append(f'Línea {i}: columnas insuficientes ({len(partes)}) — {linea[:60]}')

        if registros:
            messages.success(request, f'Se encontraron {len(registros)} marcaciones válidas.')
        if errores:
            messages.warning(request, f'{len(errores)} línea(s) con errores.')

    context = {
        'titulo': 'Importar Marcaciones Biométrico',
        'registros': registros[:200],
        'total_registros': len(registros),
        'hay_mas': len(registros) > 200,
        'errores': errores[:50],
        'archivo_nombre': archivo_nombre,
        'periodo_actual': _periodo_actual(),
    }
    return render(request, 'integraciones/biometrico_import.html', context)


# ──────────────────────────────────────────────────────────────────────
# CONFIGURACION DEL SISTEMA
# ──────────────────────────────────────────────────────────────────────

@login_required
@solo_admin
def configuracion_sistema(request):
    """
    Vista de configuracion del sistema con tabs.
    Tabs: General, Modulos, Nomina, Integraciones, IA
    Soporta POST via AJAX (retorna JSON) o POST normal.
    """
    from asistencia.models import ConfiguracionSistema

    config = ConfiguracionSistema.get()

    if request.method == 'POST':
        tab = request.POST.get('tab', 'general')
        es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        try:
            if tab == 'general':
                config.empresa_nombre = request.POST.get('empresa_nombre', config.empresa_nombre)
                config.ruc = request.POST.get('ruc', config.ruc)
                config.empresa_email = request.POST.get('empresa_email', config.empresa_email)
                config.empresa_telefono = request.POST.get('empresa_telefono', config.empresa_telefono)
                config.empresa_direccion = request.POST.get('empresa_direccion', config.empresa_direccion)
                config.empresa_web = request.POST.get('empresa_web', config.empresa_web)
                config.modo_sistema = request.POST.get('modo_sistema', config.modo_sistema)
                config.firma_nombre = request.POST.get('firma_nombre', config.firma_nombre)
                config.firma_cargo = request.POST.get('firma_cargo', config.firma_cargo)
                config.membrete_color = request.POST.get('membrete_color', config.membrete_color)
                config.membrete_mostrar = 'membrete_mostrar' in request.POST

            elif tab == 'modulos':
                config.mod_prestamos = 'mod_prestamos' in request.POST
                config.mod_viaticos = 'mod_viaticos' in request.POST
                config.mod_documentos = 'mod_documentos' in request.POST
                config.mod_evaluaciones = 'mod_evaluaciones' in request.POST
                config.mod_capacitaciones = 'mod_capacitaciones' in request.POST
                config.mod_reclutamiento = 'mod_reclutamiento' in request.POST
                config.mod_encuestas = 'mod_encuestas' in request.POST
                config.mod_salarios = 'mod_salarios' in request.POST

            elif tab == 'nomina':
                dia_corte = request.POST.get('dia_corte_planilla', '')
                if dia_corte.isdigit():
                    config.dia_corte_planilla = int(dia_corte)
                config.regularizacion_activa = 'regularizacion_activa' in request.POST
                config.he_requiere_solicitud = 'he_requiere_solicitud' in request.POST
                config.he_tipo_default = request.POST.get('he_tipo_default', config.he_tipo_default)
                config.export_formato = request.POST.get('export_formato', config.export_formato)
                config.export_incluir_sueldo = 'export_incluir_sueldo' in request.POST
                config.export_incluir_faltas = 'export_incluir_faltas' in request.POST
                config.export_incluir_banco_horas = 'export_incluir_banco_horas' in request.POST
                config.export_separar_staff_rco = 'export_separar_staff_rco' in request.POST
                jornada_local = request.POST.get('jornada_local_horas', '')
                jornada_foraneo = request.POST.get('jornada_foraneo_horas', '')
                if jornada_local:
                    try:
                        from decimal import Decimal
                        config.jornada_local_horas = Decimal(jornada_local)
                    except Exception:
                        pass
                if jornada_foraneo:
                    try:
                        from decimal import Decimal
                        config.jornada_foraneo_horas = Decimal(jornada_foraneo)
                    except Exception:
                        pass

            elif tab == 'integraciones':
                config.programa_nomina = request.POST.get('programa_nomina', config.programa_nomina)
                config.programa_nomina_nombre = request.POST.get('programa_nomina_nombre', config.programa_nomina_nombre)
                config.email_habilitado = 'email_habilitado' in request.POST
                config.email_desde = request.POST.get('email_desde', config.email_desde)
                config.email_asunto_semanal = request.POST.get('email_asunto_semanal', config.email_asunto_semanal)
                dia_envio = request.POST.get('email_dia_envio', '')
                if dia_envio.isdigit():
                    config.email_dia_envio = int(dia_envio)
                config.zapsign_activo = 'zapsign_activo' in request.POST
                zapsign_key = request.POST.get('zapsign_api_key', '')
                if zapsign_key:
                    config.zapsign_api_key = zapsign_key
                # Telegram Bot — solo actualizar token si se proporcionó (seguridad)
                tg_token = request.POST.get('telegram_bot_token', '').strip()
                if tg_token:
                    config.telegram_bot_token = tg_token
                config.telegram_channel_id = request.POST.get('telegram_channel_id', '').strip()
                # WhatsApp Business Cloud API
                wa_phone_id = request.POST.get('whatsapp_phone_number_id', '').strip()
                wa_token    = request.POST.get('whatsapp_access_token', '').strip()
                if wa_phone_id:
                    config.whatsapp_phone_number_id = wa_phone_id
                if wa_token:
                    config.whatsapp_access_token = wa_token
                config.whatsapp_to_number = request.POST.get('whatsapp_to_number', '').strip()

            elif tab == 'ia':
                config.ia_provider = request.POST.get('ia_provider', config.ia_provider)
                # API key para proveedores cloud — solo actualizar si se proporcionó
                api_key = request.POST.get('ia_api_key', '').strip()
                if api_key:
                    config.ia_api_key = api_key
                config.ia_endpoint = request.POST.get('ia_endpoint', config.ia_endpoint)
                config.ia_modelo = request.POST.get('ia_modelo', config.ia_modelo)
                config.ia_ocr_provider = request.POST.get('ia_ocr_provider', config.ia_ocr_provider)
                # Key Gemini dedicada para OCR (permite DeepSeek chat + Gemini OCR)
                gemini_key = request.POST.get('ia_gemini_api_key', '').strip()
                if gemini_key:
                    config.ia_gemini_api_key = gemini_key
                config.ia_mapeo_activo = 'ia_mapeo_activo' in request.POST
                # Invalidar caché del servicio IA para que tome la nueva config
                try:
                    from asistencia.services.ai_service import _ia_cache
                    _ia_cache.clear()
                except Exception:
                    pass

            config.actualizado_por = request.user
            config.save()

            if es_ajax:
                return JsonResponse({'ok': True, 'mensaje': 'Configuración guardada correctamente.'})

            messages.success(request, 'Configuración guardada correctamente.')

        except Exception as e:
            if es_ajax:
                return JsonResponse({'ok': False, 'mensaje': f'Error al guardar: {str(e)}'}, status=400)
            messages.error(request, f'Error al guardar: {str(e)}')

        return redirect('configuracion_sistema')

    context = {
        'titulo': 'Configuración del Sistema',
        'config': config,
        'modo_choices': ConfiguracionSistema.MODO_SISTEMA_CHOICES,
        'programa_choices': ConfiguracionSistema.PROGRAMA_NOMINA_CHOICES,
        'ia_choices':     ConfiguracionSistema.IA_PROVIDER_CHOICES,
        'ia_ocr_choices': ConfiguracionSistema.IA_OCR_PROVIDER_CHOICES,
        'he_tipo_choices': ConfiguracionSistema.HE_TIPO_CHOICES,
        'export_formato_choices': ConfiguracionSistema.EXPORT_FORMATO_CHOICES,
        'tab_activo': request.GET.get('tab', 'general'),
    }
    return render(request, 'configuracion/configuracion_sistema.html', context)


# ══════════════════════════════════════════════════════════════════════════════
# SCTR — SEGURO COMPLEMENTARIO DE TRABAJO DE RIESGO
# ══════════════════════════════════════════════════════════════════════════════

@login_required
def sctr_panel(request):
    """Panel principal de pólizas SCTR con alertas de vencimiento."""
    from .models import PolizaSCTR
    from django.utils import timezone
    hoy = timezone.localdate()

    polizas = PolizaSCTR.objects.all().order_by('fecha_fin', 'tipo')

    # Estadísticas
    vigentes     = [p for p in polizas if p.estado == 'VIGENTE' and not p.esta_vencida]
    por_vencer   = [p for p in vigentes if p.esta_proxima_a_vencer]
    vencidas     = [p for p in polizas if p.esta_vencida or p.estado == 'VENCIDA']

    # Auto-actualizar estado si venció
    for p in polizas:
        if p.esta_vencida and p.estado == 'VIGENTE':
            p.estado = 'VENCIDA'
            p.save(update_fields=['estado'])

    polizas = PolizaSCTR.objects.all().order_by('fecha_fin', 'tipo')

    return render(request, 'integraciones/sctr_panel.html', {
        'titulo':       'Control SCTR — Pólizas y Vencimientos',
        'polizas':      polizas,
        'vigentes':     len([p for p in polizas if p.estado == 'VIGENTE']),
        'por_vencer':   len([p for p in polizas if p.esta_proxima_a_vencer and p.estado == 'VIGENTE']),
        'vencidas':     len([p for p in polizas if p.esta_vencida or p.estado == 'VENCIDA']),
        'hoy':          hoy,
        'tipo_choices': PolizaSCTR.TIPO_CHOICES,
        'prov_choices': PolizaSCTR.PROVEEDOR_CHOICES,
        'estado_choices': PolizaSCTR.ESTADO_CHOICES,
    })


@login_required
def sctr_crear(request):
    """Crear nueva póliza SCTR."""
    from .models import PolizaSCTR
    if request.method == 'POST':
        tipo      = request.POST.get('tipo', '')
        numero    = request.POST.get('numero_poliza', '').strip()
        proveedor = request.POST.get('proveedor', '')
        prov_otro = request.POST.get('proveedor_otro', '').strip()
        fecha_ini = request.POST.get('fecha_inicio', '')
        fecha_fin = request.POST.get('fecha_fin', '')
        monto     = request.POST.get('monto_asegurado', '0').strip()
        aporte    = request.POST.get('aporte_pct', '0').strip()
        cubiertos = request.POST.get('trabajadores_cubiertos', '0').strip()
        dias_alerta = request.POST.get('dias_alerta', '30').strip()
        renovacion  = 'renovacion_auto' in request.POST
        obs       = request.POST.get('observaciones', '').strip()

        if not all([tipo, numero, proveedor, fecha_ini, fecha_fin]):
            messages.error(request, 'Tipo, número, proveedor y fechas son obligatorios.')
            return redirect('sctr_crear')

        try:
            from datetime import datetime
            fi = datetime.strptime(fecha_ini, '%Y-%m-%d').date()
            ff = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, 'Fechas inválidas.')
            return redirect('sctr_crear')

        from decimal import Decimal
        poliza = PolizaSCTR.objects.create(
            tipo                   = tipo,
            numero_poliza          = numero,
            proveedor              = proveedor,
            proveedor_otro         = prov_otro,
            fecha_inicio           = fi,
            fecha_fin              = ff,
            monto_asegurado        = Decimal(monto or '0'),
            aporte_pct             = Decimal(aporte or '0'),
            trabajadores_cubiertos = int(cubiertos or 0),
            dias_alerta            = int(dias_alerta or 30),
            renovacion_auto        = renovacion,
            observaciones          = obs,
            estado                 = 'VIGENTE',
            activa                 = True,
            creado_por             = request.user,
        )
        # Subir archivo si hay
        if request.FILES.get('archivo'):
            poliza.archivo = request.FILES['archivo']
            poliza.save(update_fields=['archivo'])

        messages.success(request, f'Póliza {numero} creada exitosamente.')
        return redirect('sctr_panel')

    from .models import PolizaSCTR
    return render(request, 'integraciones/sctr_form.html', {
        'titulo':       'Nueva Póliza SCTR',
        'tipo_choices': PolizaSCTR.TIPO_CHOICES,
        'prov_choices': PolizaSCTR.PROVEEDOR_CHOICES,
        'accion':       'crear',
    })


@login_required
def sctr_editar(request, pk):
    """Editar póliza SCTR existente."""
    from .models import PolizaSCTR
    poliza = get_object_or_404(PolizaSCTR, pk=pk)

    if request.method == 'POST':
        poliza.tipo                   = request.POST.get('tipo', poliza.tipo)
        poliza.numero_poliza          = request.POST.get('numero_poliza', poliza.numero_poliza).strip()
        poliza.proveedor              = request.POST.get('proveedor', poliza.proveedor)
        poliza.proveedor_otro         = request.POST.get('proveedor_otro', poliza.proveedor_otro).strip()
        poliza.observaciones          = request.POST.get('observaciones', poliza.observaciones).strip()
        poliza.renovacion_auto        = 'renovacion_auto' in request.POST
        poliza.activa                 = 'activa' in request.POST

        try:
            from datetime import datetime
            poliza.fecha_inicio = datetime.strptime(request.POST['fecha_inicio'], '%Y-%m-%d').date()
            poliza.fecha_fin    = datetime.strptime(request.POST['fecha_fin'],    '%Y-%m-%d').date()
        except (KeyError, ValueError):
            pass

        try:
            from decimal import Decimal
            poliza.monto_asegurado        = Decimal(request.POST.get('monto_asegurado', '0'))
            poliza.aporte_pct             = Decimal(request.POST.get('aporte_pct', '0'))
            poliza.trabajadores_cubiertos = int(request.POST.get('trabajadores_cubiertos', '0'))
            poliza.dias_alerta            = int(request.POST.get('dias_alerta', '30'))
        except (ValueError, Exception):
            pass

        if request.FILES.get('archivo'):
            poliza.archivo = request.FILES['archivo']

        poliza.save()
        messages.success(request, f'Póliza {poliza.numero_poliza} actualizada.')
        return redirect('sctr_panel')

    return render(request, 'integraciones/sctr_form.html', {
        'titulo':       f'Editar Póliza — {poliza.numero_poliza}',
        'poliza':       poliza,
        'tipo_choices': PolizaSCTR.TIPO_CHOICES,
        'prov_choices': PolizaSCTR.PROVEEDOR_CHOICES,
        'accion':       'editar',
    })


@login_required
@require_POST
def sctr_estado(request, pk):
    """Toggle estado de póliza (activa/cancelada/renovacion)."""
    from .models import PolizaSCTR
    poliza = get_object_or_404(PolizaSCTR, pk=pk)
    nuevo_estado = request.POST.get('estado', '')
    if nuevo_estado in dict(PolizaSCTR.ESTADO_CHOICES):
        poliza.estado = nuevo_estado
        poliza.activa = nuevo_estado not in ('CANCELADA', 'VENCIDA')
        poliza.save(update_fields=['estado', 'activa'])
        messages.success(request, f'Estado de póliza {poliza.numero_poliza} actualizado a {poliza.get_estado_display()}.')
    return redirect('sctr_panel')
