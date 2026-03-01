"""
Vistas del módulo Tareo.
"""
import calendar
import os
import tempfile
from datetime import date
from decimal import Decimal
from io import BytesIO, StringIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Avg, Count, OuterRef, Q, Subquery, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

solo_admin = user_passes_test(lambda u: u.is_superuser, login_url='login')


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _get_importacion_activa(tipo='RELOJ', importacion_id=None):
    """Devuelve la importación activa (por ID o la última completada de ese tipo)."""
    from tareo.models import TareoImportacion
    if importacion_id:
        try:
            return TareoImportacion.objects.get(pk=importacion_id)
        except TareoImportacion.DoesNotExist:
            pass
    return (
        TareoImportacion.objects
        .filter(tipo=tipo, estado__in=['COMPLETADO', 'COMPLETADO_CON_ERRORES'])
        .order_by('-creado_en')
        .first()
    )


def _lista_importaciones(tipo='RELOJ'):
    """Lista de importaciones completadas para selector."""
    from tareo.models import TareoImportacion
    return (
        TareoImportacion.objects
        .filter(tipo=tipo, estado__in=['COMPLETADO', 'COMPLETADO_CON_ERRORES'])
        .order_by('-creado_en')[:30]
    )


def _qs_staff_dedup(mes_ini, mes_fin):
    """
    Queryset de RegistroTareo STAFF para el rango de fechas dado,
    deduplicado: un solo registro por (personal, fecha), eligiendo
    siempre el de mayor importacion_id (importación más reciente).

    Evita doble-conteo cuando el mismo período fue importado varias veces
    (ej. import #1 SYNKRO y #5 RELOJ cubren el mismo rango de fechas).
    """
    from tareo.models import RegistroTareo

    # Subquery: para cada (personal_id, fecha) STAFF, devuelve el id
    # del registro con el mayor importacion_id (el más reciente).
    latest_id = (
        RegistroTareo.objects
        .filter(
            personal_id=OuterRef('personal_id'),
            fecha=OuterRef('fecha'),
            grupo='STAFF',
        )
        .order_by('-importacion_id')
        .values('id')[:1]
    )

    return RegistroTareo.objects.filter(
        grupo='STAFF',
        fecha__gte=mes_ini,
        fecha__lte=mes_fin,
        personal__isnull=False,
        id=Subquery(latest_id),
    )


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def tareo_dashboard(request):
    """Panel principal del módulo Tareo (solo admin)."""
    from personal.models import Personal
    from tareo.models import BancoHoras, RegistroTareo, TareoImportacion

    # ── Selector de mes ──────────────────────────────────────────
    MESES_ES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
                'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
    MESES = [(i + 1, nombre) for i, nombre in enumerate(MESES_ES)]

    hoy = date.today()
    anio_sel = int(request.GET.get('anio', hoy.year))
    mes_sel  = int(request.GET.get('mes',  hoy.month))
    mes_nombre = MESES_ES[mes_sel - 1]

    _anios_banco = set(BancoHoras.objects.values_list('periodo_anio', flat=True))
    _anios_reg   = set(RegistroTareo.objects.values_list('fecha__year', flat=True))
    anios_disponibles = sorted(_anios_banco | _anios_reg | {hoy.year}, reverse=True)

    # ── Stats de Personal ────────────────────────────────────────
    total_staff = Personal.objects.filter(grupo_tareo='STAFF', estado='Activo').count()
    total_rco   = Personal.objects.filter(grupo_tareo='RCO',   estado='Activo').count()

    # ── Mes calendario (para stats de display) ───────────────────
    mes_ini = date(anio_sel, mes_sel, 1)
    mes_fin = date(anio_sel, mes_sel, calendar.monthrange(anio_sel, mes_sel)[1])

    # Ciclo HE (referencia: 21 mes anterior → fin del mes) ────────
    if mes_sel == 1:
        mes_ant, anio_ant = 12, anio_sel - 1
    else:
        mes_ant, anio_ant = mes_sel - 1, anio_sel
    ciclo_ini = date(anio_ant, mes_ant, 21)
    ciclo_fin = mes_fin

    # Stats filtrados por mes calendario (no ciclo HE)
    # STAFF: deduplicado por (personal, fecha) → importación más reciente
    # RCO: sin duplicados (solo tiene una importación por período)
    qs_staff_dedup = _qs_staff_dedup(mes_ini, mes_fin)
    qs_rco = RegistroTareo.objects.filter(grupo='RCO', fecha__gte=mes_ini, fecha__lte=mes_fin)

    staff_stats = qs_staff_dedup.aggregate(
        personas    = Count('dni', distinct=True),
        he_25       = Sum('he_25'),
        he_35       = Sum('he_35'),
        he_100      = Sum('he_100'),
        faltas      = Count('id', filter=Q(codigo_dia__in=['F', 'FA', 'LSG'])),
        ss_count    = Count('id', filter=Q(codigo_dia='SS')),
    )
    rco_stats = qs_rco.aggregate(
        personas    = Count('dni', distinct=True),
        he_25       = Sum('he_25'),
        he_35       = Sum('he_35'),
        he_100      = Sum('he_100'),
        faltas      = Count('id', filter=Q(codigo_dia__in=['F', 'FA', 'LSG'])),
        ss_count    = Count('id', filter=Q(codigo_dia='SS')),
    )

    def _d(v): return v or Decimal('0')
    stats = {
        'staff_personas':  staff_stats['personas'] or 0,
        'rco_personas':    rco_stats['personas']   or 0,
        'he_25_total':     _d(staff_stats['he_25'])  + _d(rco_stats['he_25']),
        'he_35_total':     _d(staff_stats['he_35'])  + _d(rco_stats['he_35']),
        'he_100_total':    _d(staff_stats['he_100']) + _d(rco_stats['he_100']),
        'faltas':          (staff_stats['faltas']  or 0) + (rco_stats['faltas']  or 0),
        'ss_count':        (staff_stats['ss_count'] or 0) + (rco_stats['ss_count'] or 0),
        'total_registros': qs_staff_dedup.count() + qs_rco.count(),
    }
    stats['he_25_total']  = stats['he_25_total']  or Decimal('0')
    stats['he_35_total']  = stats['he_35_total']  or Decimal('0')
    stats['he_100_total'] = stats['he_100_total'] or Decimal('0')
    stats['he_total'] = stats['he_25_total'] + stats['he_35_total'] + stats['he_100_total']
    stats['total_staff_bd'] = total_staff
    # Si Personal no tiene grupo_tareo='RCO' configurado, usar conteo de RegistroTareo
    stats['total_rco_bd'] = total_rco if total_rco > 0 else (stats['rco_personas'] or 0)

    # ── Banco de horas del mes seleccionado ──────────────────────
    banco_qs = BancoHoras.objects.filter(periodo_anio=anio_sel, periodo_mes=mes_sel)
    banco_stats = banco_qs.aggregate(
        personas      = Count('personal', distinct=True),
        saldo_total   = Sum('saldo_horas'),
        acumulado_25  = Sum('he_25_acumuladas'),
        acumulado_35  = Sum('he_35_acumuladas'),
        acumulado_100 = Sum('he_100_acumuladas'),
        compensado    = Sum('he_compensadas'),
    )

    ultimas_imports = TareoImportacion.objects.order_by('-creado_en')[:8]

    context = {
        'titulo': 'Módulo Tareo',
        'anio_sel': anio_sel,
        'mes_sel': mes_sel,
        'mes_nombre': mes_nombre,
        'meses': MESES,
        'anios_disponibles': anios_disponibles,
        'stats': stats,
        'banco_stats': banco_stats,
        'ultimas_imports': ultimas_imports,
        'mes_ini': mes_ini,
        'mes_fin': mes_fin,
        'ciclo_ini': ciclo_ini,
        'ciclo_fin': ciclo_fin,
    }
    return render(request, 'tareo/dashboard.html', context)


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
    from tareo.models import BancoHoras, RegistroTareo

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
    qs_resumen = (
        _qs_staff_dedup(mes_ini, mes_fin)
        .values('personal_id', 'personal__apellidos_nombres', 'personal__nro_doc',
                'personal__condicion', 'dni')
        .annotate(
            dias_trabajados = Count('id', filter=Q(codigo_dia__in=['T', 'NOR', 'TR', 'LCG', 'ATM', 'CDT', 'CPF', 'SS'])),
            dias_ss         = Count('id', filter=Q(codigo_dia='SS')),
            dias_dl         = Count('id', filter=Q(codigo_dia__in=['DL', 'DLA'])),
            dias_che        = Count('id', filter=Q(codigo_dia='CHE')),
            dias_vac        = Count('id', filter=Q(codigo_dia__in=['VAC', 'V'])),
            dias_dm         = Count('id', filter=Q(codigo_dia='DM')),
            dias_lsg        = Count('id', filter=Q(codigo_dia='LSG')),
            dias_fa         = Count('id', filter=Q(codigo_dia__in=['FA', 'F'])),
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
    return render(request, 'tareo/vista_staff.html', context)


# ---------------------------------------------------------------------------
# VISTA RCO — Tabla detalle con HE 25/35/100
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def vista_rco(request):
    """Tabla detalle de horas extra para personal RCO (navegación por período mes/año)."""
    from tareo.models import RegistroTareo

    MESES_ES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
                'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
    MESES = [(i + 1, nombre) for i, nombre in enumerate(MESES_ES)]

    hoy = date.today()
    anio_sel = int(request.GET.get('anio', hoy.year))
    mes_sel  = int(request.GET.get('mes',  hoy.month))

    anios_disponibles = sorted(
        set(RegistroTareo.objects.filter(grupo='RCO')
            .values_list('fecha__year', flat=True)),
        reverse=True
    ) or [hoy.year]

    mes_ini = date(anio_sel, mes_sel, 1)
    mes_fin = date(anio_sel, mes_sel, calendar.monthrange(anio_sel, mes_sel)[1])

    buscar  = request.GET.get('buscar', '').strip()
    solo_he = request.GET.get('solo_he', '') == '1'

    # Base queryset for the selected period
    qs_base = RegistroTareo.objects.filter(
        grupo='RCO', fecha__gte=mes_ini, fecha__lte=mes_fin
    )

    # KPIs from full period (no text filter)
    kpi = qs_base.aggregate(
        personas   = Count('dni', distinct=True),
        he_25_sum  = Sum('he_25'),
        he_35_sum  = Sum('he_35'),
        he_100_sum = Sum('he_100'),
        dias_reg   = Count('id'),
    )
    kpi['he_25_sum']  = kpi['he_25_sum']  or Decimal('0')
    kpi['he_35_sum']  = kpi['he_35_sum']  or Decimal('0')
    kpi['he_100_sum'] = kpi['he_100_sum'] or Decimal('0')
    kpi['he_total']   = kpi['he_25_sum'] + kpi['he_35_sum'] + kpi['he_100_sum']

    # Apply text search filter for tables
    qs_filtrado = qs_base
    if buscar:
        qs_filtrado = qs_filtrado.filter(
            Q(dni__icontains=buscar) | Q(nombre_archivo__icontains=buscar)
        )

    # Detail rows (+ solo_he filter)
    qs = qs_filtrado.order_by('nombre_archivo', 'fecha')
    if solo_he:
        qs = qs.filter(Q(he_25__gt=0) | Q(he_35__gt=0) | Q(he_100__gt=0))

    # Summary by person (buscar applied, solo_he NOT applied to keep all totals)
    resumen = list(
        qs_filtrado
        .values('dni', 'nombre_archivo')
        .annotate(
            total_he_25=Sum('he_25'),
            total_he_35=Sum('he_35'),
            total_he_100=Sum('he_100'),
            total_horas=Sum('horas_marcadas'),
            dias_trabajados=Count('id'),
        )
        .order_by('nombre_archivo')
    )
    for r in resumen:
        r['total_he'] = (r['total_he_25'] or Decimal('0')) + \
                        (r['total_he_35'] or Decimal('0')) + \
                        (r['total_he_100'] or Decimal('0'))

    totales = qs_filtrado.aggregate(
        t_he_25=Sum('he_25'),
        t_he_35=Sum('he_35'),
        t_he_100=Sum('he_100'),
        t_horas=Sum('horas_marcadas'),
    )
    totales['t_he_total'] = (totales['t_he_25'] or Decimal('0')) + \
                             (totales['t_he_35'] or Decimal('0')) + \
                             (totales['t_he_100'] or Decimal('0'))

    context = {
        'titulo': f'RCO — Horas Extra {MESES_ES[mes_sel-1]} {anio_sel}',
        'anio_sel': anio_sel,
        'mes_sel': mes_sel,
        'mes_nombre': MESES_ES[mes_sel - 1],
        'meses': MESES,
        'anios_disponibles': anios_disponibles,
        'mes_ini': mes_ini,
        'mes_fin': mes_fin,
        'kpi': kpi,
        'registros': qs,
        'resumen': resumen,
        'totales': totales,
        'buscar': buscar,
        'solo_he': solo_he,
        'total_registros': qs.count(),
    }
    return render(request, 'tareo/vista_rco.html', context)


# ---------------------------------------------------------------------------
# BANCO DE HORAS (solo STAFF)
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def banco_horas_view(request):
    """Saldo del banco de horas acumulativas por personal STAFF."""
    from tareo.models import BancoHoras

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

    MESES = [
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
        'meses': MESES,
        'total_personas': qs.values('personal').distinct().count(),
    }
    return render(request, 'tareo/banco_horas.html', context)


# ---------------------------------------------------------------------------
# IMPORTAR (upload web)
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def importar_view(request):
    """Formulario web para importar archivo Excel de tareo."""
    from tareo.models import TareoImportacion

    if request.method == 'POST':
        archivo = request.FILES.get('archivo_excel')
        tipo_import = request.POST.get('tipo_import', 'RELOJ')
        dry_run = request.POST.get('dry_run') == '1'
        force = request.POST.get('force') == '1'

        if not archivo:
            messages.error(request, 'Debes seleccionar un archivo Excel.')
            return redirect('tareo_importar')

        if not archivo.name.lower().endswith(('.xlsx', '.xls')):
            messages.error(request, 'El archivo debe ser formato Excel (.xlsx o .xls).')
            return redirect('tareo_importar')

        suffix = '.xlsx' if archivo.name.lower().endswith('.xlsx') else '.xls'
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            for chunk in archivo.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            out = StringIO()
            kwargs = {'archivo': tmp_path, 'stdout': out, 'stderr': out}
            if dry_run:
                kwargs['dry_run'] = True
            if force:
                kwargs['force'] = True

            call_command('importar_tareo_excel', **kwargs)
            output = out.getvalue()

            if dry_run:
                messages.info(request, f'[DRY-RUN] Simulación completada. Revisa los logs del servidor para detalles.')
            else:
                messages.success(request, 'Importación completada correctamente.')

        except Exception as e:
            messages.error(request, f'Error durante la importación: {e}')
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        return redirect('tareo_dashboard')

    # GET — mostrar formulario
    ultimas = TareoImportacion.objects.order_by('-creado_en')[:5]
    context = {
        'titulo': 'Importar Tareo Excel',
        'ultimas_imports': ultimas,
    }
    return render(request, 'tareo/importar.html', context)


# ---------------------------------------------------------------------------
# PARÁMETROS / CONFIGURACIÓN
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def parametros_view(request):
    """Vista de parámetros y configuración del módulo Tareo."""
    from tareo.models import (
        FeriadoCalendario, HomologacionCodigo,
        RegimenTurno, TipoHorario,
    )

    context = {
        'titulo': 'Parámetros del Módulo Tareo',
        'regimenes': RegimenTurno.objects.all().order_by('nombre'),
        'horarios': TipoHorario.objects.all().order_by('nombre'),
        'feriados': FeriadoCalendario.objects.all().order_by('fecha'),
        'homologaciones': HomologacionCodigo.objects.all().order_by('prioridad', 'codigo_origen'),
    }
    return render(request, 'tareo/parametros.html', context)


# ---------------------------------------------------------------------------
# AJAX ENDPOINTS
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def ajax_staff_data(request):
    """JSON con datos STAFF para la matriz."""
    from tareo.models import RegistroTareo

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


@login_required
@solo_admin
def ajax_rco_data(request):
    """JSON con resumen HE por persona para personal RCO."""
    from tareo.models import RegistroTareo

    importacion_id = request.GET.get('importacion')
    importacion = _get_importacion_activa('RELOJ', importacion_id)

    if not importacion:
        return JsonResponse({'error': 'Sin importación activa'}, status=404)

    data = list(
        RegistroTareo.objects
        .filter(importacion=importacion, grupo='RCO')
        .values('dni', 'nombre_archivo')
        .annotate(
            total_he_25=Sum('he_25'),
            total_he_35=Sum('he_35'),
            total_he_100=Sum('he_100'),
            total_horas=Sum('horas_marcadas'),
        )
        .order_by('nombre_archivo')
    )

    for row in data:
        row['total_he_25'] = float(row['total_he_25'] or 0)
        row['total_he_35'] = float(row['total_he_35'] or 0)
        row['total_he_100'] = float(row['total_he_100'] or 0)
        row['total_horas'] = float(row['total_horas'] or 0)
        row['total_he'] = row['total_he_25'] + row['total_he_35'] + row['total_he_100']

    return JsonResponse({'total': len(data), 'data': data})


@login_required
@solo_admin
def ajax_importaciones(request):
    """JSON lista de importaciones completadas."""
    from tareo.models import TareoImportacion

    tipo = request.GET.get('tipo', 'RELOJ')
    imports = list(
        TareoImportacion.objects
        .filter(tipo=tipo, estado__in=['COMPLETADO', 'COMPLETADO_CON_ERRORES'])
        .order_by('-creado_en')
        .values('id', 'tipo', 'estado', 'periodo_inicio', 'periodo_fin',
                'total_registros', 'registros_error', 'creado_en')[:30]
    )

    for row in imports:
        row['periodo_inicio'] = row['periodo_inicio'].isoformat() if row['periodo_inicio'] else None
        row['periodo_fin'] = row['periodo_fin'].isoformat() if row['periodo_fin'] else None
        row['creado_en'] = row['creado_en'].strftime('%d/%m/%Y %H:%M')

    return JsonResponse({'tipo': tipo, 'total': len(imports), 'data': imports})


# ---------------------------------------------------------------------------
# IMPORTAR SYNKRO (Reloj + Papeletas combinado)
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def importar_synkro_view(request):
    """Importa archivo Synkro (contiene hojas Reloj y/o Papeletas)."""
    from tareo.models import ConfiguracionSistema, TareoImportacion
    from tareo.services.synkro import SynkroParser
    from tareo.services.processor import TareoProcessor

    config = ConfiguracionSistema.get()

    if request.method == 'POST':
        archivo = request.FILES.get('archivo')
        periodo_inicio = request.POST.get('periodo_inicio')
        periodo_fin = request.POST.get('periodo_fin')
        grupo_default = request.POST.get('grupo_default', 'STAFF')
        dry_run = request.POST.get('dry_run') == '1'

        if not archivo:
            messages.error(request, 'Debes seleccionar un archivo.')
            return redirect('tareo_importar_synkro')

        suffix = '.xlsx' if archivo.name.lower().endswith('.xlsx') else '.xls'
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            for chunk in archivo.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        try:
            from datetime import datetime as dt
            p_ini = dt.strptime(periodo_inicio, '%Y-%m-%d').date() if periodo_inicio else None
            p_fin = dt.strptime(periodo_fin, '%Y-%m-%d').date() if periodo_fin else None

            parser = SynkroParser(tmp_path, config)
            hojas = parser.hojas_disponibles()

            # Parsear Reloj
            resultado_reloj = parser.parse_reloj()
            # Parsear Papeletas
            resultado_pap = parser.parse_papeletas()

            if dry_run:
                messages.info(
                    request,
                    f'[DRY-RUN] Reloj: {len(resultado_reloj["registros"])} registros, '
                    f'Papeletas: {len(resultado_pap["papeletas"])} registros. '
                    f'Fechas: {len(resultado_reloj["fechas"])}. '
                    f'Hojas detectadas: {hojas}')
                return redirect('tareo_importar_synkro')

            # Crear importación
            importacion = TareoImportacion.objects.create(
                tipo='RELOJ',
                periodo_inicio=p_ini or (resultado_reloj['fechas'][0] if resultado_reloj['fechas'] else date.today()),
                periodo_fin=p_fin or (resultado_reloj['fechas'][-1] if resultado_reloj['fechas'] else date.today()),
                archivo_nombre=archivo.name,
                estado='PROCESANDO',
                usuario=request.user,
                metadata={'hojas': hojas, 'archivo': archivo.name},
            )

            proc = TareoProcessor(importacion, config)
            resultado = proc.procesar(
                resultado_reloj['registros'],
                resultado_pap['papeletas'],
                grupo_default=grupo_default,
            )

            # Advertencias de parseo
            todas_adv = resultado_reloj['advertencias'] + resultado_pap['advertencias']
            if todas_adv:
                importacion.advertencias = (importacion.advertencias or []) + todas_adv
                importacion.save(update_fields=['advertencias'])

            msg = (f'Importación completada: {resultado["creados"]} nuevos, '
                   f'{resultado["actualizados"]} actualizados, '
                   f'{resultado["sin_match"]} sin match en BD.')
            if resultado['errores']:
                messages.warning(request, msg)
            else:
                messages.success(request, msg)

        except Exception as e:
            messages.error(request, f'Error durante la importación: {e}')
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        return redirect('tareo_dashboard')

    # GET
    context = {
        'titulo': 'Importar Synkro (Reloj + Papeletas)',
        'config': config,
        'ultimas': TareoImportacion.objects.order_by('-creado_en')[:5],
    }
    return render(request, 'tareo/importar_synkro.html', context)


# ---------------------------------------------------------------------------
# IMPORTAR SUNAT TR5
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def importar_sunat_view(request):
    """Importa el archivo TR5 de SUNAT T-Registro."""
    from tareo.models import TareoImportacion
    from tareo.services.sunat_importer import importar_tr5

    if request.method == 'POST':
        archivo = request.FILES.get('archivo')
        periodo_inicio = request.POST.get('periodo_inicio')
        actualizar_personal = request.POST.get('actualizar_personal') == '1'

        if not archivo:
            messages.error(request, 'Debes seleccionar el archivo TR5.')
            return redirect('tareo_importar_sunat')

        from datetime import datetime as dt
        p_ini = dt.strptime(periodo_inicio, '%Y-%m-%d').date() if periodo_inicio else date.today()

        suffix = '.txt' if archivo.name.lower().endswith('.txt') else ''
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            for chunk in archivo.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        importacion = TareoImportacion.objects.create(
            tipo='SUNAT',
            periodo_inicio=p_ini,
            periodo_fin=p_ini,
            archivo_nombre=archivo.name,
            estado='PROCESANDO',
            usuario=request.user,
        )

        try:
            resultado = importar_tr5(tmp_path, importacion,
                                     actualizar_personal=actualizar_personal)
            messages.success(
                request,
                f'TR5 importado: {resultado["creados"]} trabajadores, '
                f'{resultado["sin_match"]} sin match en BD.')
        except Exception as e:
            importacion.estado = 'FALLIDO'
            importacion.save()
            messages.error(request, f'Error: {e}')
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        return redirect('tareo_dashboard')

    context = {
        'titulo': 'Importar SUNAT TR5',
        'ultimas': TareoImportacion.objects.filter(tipo='SUNAT').order_by('-creado_en')[:5],
    }
    return render(request, 'tareo/importar_sunat.html', context)


# ---------------------------------------------------------------------------
# IMPORTAR S10
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def importar_s10_view(request):
    """Importa el reporte de personal del sistema S10."""
    from tareo.models import TareoImportacion
    from tareo.services.s10_importer import importar_s10

    if request.method == 'POST':
        archivo = request.FILES.get('archivo')
        periodo_inicio = request.POST.get('periodo_inicio')
        actualizar_personal = request.POST.get('actualizar_personal') == '1'
        usar_ia = request.POST.get('usar_ia') == '1'

        if not archivo:
            messages.error(request, 'Debes seleccionar el archivo S10.')
            return redirect('tareo_importar_s10')

        from datetime import datetime as dt
        p_ini = dt.strptime(periodo_inicio, '%Y-%m-%d').date() if periodo_inicio else date.today()

        suffix = '.xlsx'
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            for chunk in archivo.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        importacion = TareoImportacion.objects.create(
            tipo='S10',
            periodo_inicio=p_ini,
            periodo_fin=p_ini,
            archivo_nombre=archivo.name,
            estado='PROCESANDO',
            usuario=request.user,
        )

        try:
            resultado = importar_s10(tmp_path, importacion,
                                     actualizar_personal=actualizar_personal,
                                     usar_ia=usar_ia)
            msg = (f'S10 importado: {resultado["creados"]} registros, '
                   f'{resultado["sin_match"]} sin match.')
            if resultado.get('advertencias'):
                msg += f' Advertencias: {len(resultado["advertencias"])}.'
            messages.success(request, msg)
        except Exception as e:
            importacion.estado = 'FALLIDO'
            importacion.save()
            messages.error(request, f'Error: {e}')
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        return redirect('tareo_dashboard')

    context = {
        'titulo': 'Importar Reporte S10',
        'ultimas': TareoImportacion.objects.filter(tipo='S10').order_by('-creado_en')[:5],
    }
    return render(request, 'tareo/importar_s10.html', context)


# ---------------------------------------------------------------------------
# EXPORTAR CARGA S10
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def exportar_carga_s10_view(request):
    """Genera y descarga el archivo CargaS10 para importar en el sistema S10."""
    from tareo.services.exporters import CargaS10Exporter

    anio = int(request.GET.get('anio', date.today().year))
    mes = int(request.GET.get('mes', date.today().month))

    try:
        exporter = CargaS10Exporter(anio, mes)
        buffer = exporter.generar()

        MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
        filename = f'CargaS10_{MESES[mes-1]}_{anio}.xlsx'

        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        messages.error(request, f'Error generando CargaS10: {e}')
        return redirect('tareo_dashboard')


# ---------------------------------------------------------------------------
# EXPORTAR REPORTE CIERRE
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def exportar_cierre_view(request):
    """Genera el reporte de cierre de mes."""
    from tareo.services.exporters import ReporteCierreExporter

    anio = int(request.GET.get('anio', date.today().year))
    mes = int(request.GET.get('mes', date.today().month))

    try:
        exporter = ReporteCierreExporter(anio, mes)
        buffer = exporter.generar()

        MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
        filename = f'Cierre_{MESES[mes-1]}_{anio}.xlsx'

        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        messages.error(request, f'Error generando reporte de cierre: {e}')
        return redirect('tareo_dashboard')


# ---------------------------------------------------------------------------
# CONFIGURACIÓN DEL SISTEMA
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def configuracion_view(request):
    """Vista de configuración del sistema (ConfiguracionSistema)."""
    from tareo.models import ConfiguracionSistema

    config = ConfiguracionSistema.get()

    if request.method == 'POST':
        # Campos básicos
        config.empresa_nombre = request.POST.get('empresa_nombre', config.empresa_nombre)
        config.ruc = request.POST.get('ruc', config.ruc)
        config.dia_corte_planilla = int(request.POST.get('dia_corte_planilla', config.dia_corte_planilla))
        config.regularizacion_activa = request.POST.get('regularizacion_activa') == '1'

        # Jornadas
        from decimal import Decimal as D
        config.jornada_local_horas = D(request.POST.get('jornada_local_horas', str(config.jornada_local_horas)))
        config.jornada_foraneo_horas = D(request.POST.get('jornada_foraneo_horas', str(config.jornada_foraneo_horas)))

        # Synkro
        config.synkro_hoja_reloj = request.POST.get('synkro_hoja_reloj', config.synkro_hoja_reloj)
        config.synkro_hoja_papeletas = request.POST.get('synkro_hoja_papeletas', config.synkro_hoja_papeletas)
        config.reloj_col_dni = int(request.POST.get('reloj_col_dni', config.reloj_col_dni))
        config.reloj_col_nombre = int(request.POST.get('reloj_col_nombre', config.reloj_col_nombre))
        config.reloj_col_condicion = int(request.POST.get('reloj_col_condicion', config.reloj_col_condicion))
        config.reloj_col_inicio_dias = int(request.POST.get('reloj_col_inicio_dias', config.reloj_col_inicio_dias))

        # Email
        config.email_habilitado = request.POST.get('email_habilitado') == '1'
        config.email_desde = request.POST.get('email_desde', config.email_desde)
        config.email_asunto_semanal = request.POST.get('email_asunto_semanal', config.email_asunto_semanal)
        config.email_dia_envio = int(request.POST.get('email_dia_envio', config.email_dia_envio))

        # IA
        config.ia_mapeo_activo = request.POST.get('ia_mapeo_activo') == '1'
        api_key = request.POST.get('anthropic_api_key', '').strip()
        if api_key:
            config.anthropic_api_key = api_key

        # S10
        config.s10_nombre_concepto_he25 = request.POST.get('s10_nombre_concepto_he25', config.s10_nombre_concepto_he25)
        config.s10_nombre_concepto_he35 = request.POST.get('s10_nombre_concepto_he35', config.s10_nombre_concepto_he35)
        config.s10_nombre_concepto_he100 = request.POST.get('s10_nombre_concepto_he100', config.s10_nombre_concepto_he100)

        config.actualizado_por = request.user
        config.save()
        messages.success(request, 'Configuración guardada correctamente.')
        return redirect('tareo_configuracion')

    # Calcular preview del ciclo actual
    hoy = date.today()
    inicio_he, fin_he = config.get_ciclo_he(hoy.year, hoy.month)
    inicio_asist, fin_asist = config.get_ciclo_asistencia(hoy.year, hoy.month)

    context = {
        'titulo': 'Configuración del Sistema',
        'config': config,
        'preview_ciclo_he': f'{inicio_he.strftime("%d/%m/%Y")} → {fin_he.strftime("%d/%m/%Y")}',
        'preview_asistencia': f'{inicio_asist.strftime("%d/%m/%Y")} → {fin_asist.strftime("%d/%m/%Y")}',
        'dias_semana': [
            (0, 'Lunes'), (1, 'Martes'), (2, 'Miércoles'), (3, 'Jueves'),
            (4, 'Viernes'), (5, 'Sábado'), (6, 'Domingo'),
        ],
    }
    return render(request, 'tareo/configuracion.html', context)


# ---------------------------------------------------------------------------
# DASHBOARD KPIs (mejorado)
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def kpi_dashboard_view(request):
    """Dashboard de KPIs de asistencia con gráficas."""
    from tareo.models import BancoHoras, RegistroTareo, TareoImportacion

    hoy = date.today()
    anio = int(request.GET.get('anio', hoy.year))
    mes = int(request.GET.get('mes', hoy.month))

    from tareo.models import ConfiguracionSistema
    config = ConfiguracionSistema.get()
    inicio, fin = config.get_ciclo_asistencia(anio, mes)

    qs = RegistroTareo.objects.filter(fecha__gte=inicio, fecha__lte=fin)

    # KPIs principales
    total_dias_prog = qs.count()
    dias_trabajados = qs.filter(codigo_dia__in=['T', 'NOR', 'TR']).count()
    faltas = qs.filter(codigo_dia='FA').count()
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
        faltas=Count('id', filter=Q(codigo_dia='FA')),
        he25=Sum('he_25'), he35=Sum('he_35'),
    )
    rco_stats = qs.filter(grupo='RCO').aggregate(
        dias=Count('id'),
        faltas=Count('id', filter=Q(codigo_dia='FA')),
        he25=Sum('he_25'), he35=Sum('he_35'), he100=Sum('he_100'),
    )

    # Tendencia diaria (para gráfica de línea)
    tendencia = list(
        qs.values('fecha')
        .annotate(
            trabajados=Count('id', filter=Q(codigo_dia__in=['T', 'NOR', 'TR'])),
            ausentes=Count('id', filter=Q(codigo_dia='FA')),
        )
        .order_by('fecha')
    )
    for t in tendencia:
        t['fecha'] = t['fecha'].strftime('%d/%m')

    # Top 10 ausentes del mes
    top_ausentes = list(
        qs.filter(codigo_dia='FA')
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

    MESES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
             'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

    context = {
        'titulo': f'Dashboard KPIs — {MESES[mes-1]} {anio}',
        'anio': anio, 'mes': mes,
        'mes_nombre': MESES[mes - 1],
        'periodo_asist': f'{inicio.strftime("%d/%m/%Y")} → {fin.strftime("%d/%m/%Y")}',
        'periodo_he': f'{inicio_he.strftime("%d/%m/%Y")} → {fin_he.strftime("%d/%m/%Y")}',
        # KPIs
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
        # Gráficas
        'tendencia_json': tendencia,
        'top_ausentes': top_ausentes,
        # Banco
        'banco_mes': banco_mes,
        # Selectores
        'anios': list(range(hoy.year - 2, hoy.year + 1)),
        'meses': [(i, m) for i, m in enumerate(MESES, 1)],
    }
    return render(request, 'tareo/kpi_dashboard.html', context)
