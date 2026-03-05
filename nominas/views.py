"""
Nóminas — vistas principales.
Cubre: panel períodos, crear período, detalle, generar, aprobar,
exportar CSV, detalle registro, editar registro, conceptos, mis recibos (portal),
resumen estadístico AJAX, descarga masiva boletas ZIP.
"""
import csv
import io
import json
import zipfile
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST, require_GET

from .models import ConceptoRemunerativo, LineaNomina, PeriodoNomina, RegistroNomina, PresupuestoPlanilla
from . import engine
from .flujo_caja_engine import proyectar_flujo_caja

solo_admin = user_passes_test(lambda u: u.is_superuser or u.is_staff)


# ─── Calendario procesos especiales ────────────────────────────────────────────

# Definición del calendario legal peruano de procesos especiales
_SCHEDULE = [
    # tipo,            mes, label,          base legal
    ('GRATIFICACION',  7,  'Gratif. Julio',  'Ley 27735'),
    ('GRATIFICACION', 12,  'Gratif. Diciembre', 'Ley 27735'),
    ('CTS',            5,  'CTS Mayo',       'D.Leg. 650'),
    ('CTS',           11,  'CTS Noviembre',  'D.Leg. 650'),
    ('UTILIDADES',     3,  'Utilidades',     'D.Leg. 892'),
]

_TIPO_META = {
    'GRATIFICACION': {'icon': 'fas fa-gift',              'color_base': '#ccfbf1', 'color_icon': '#0f766e'},
    'CTS':           {'icon': 'fas fa-piggy-bank',        'color_base': '#dbeafe', 'color_icon': '#1d4ed8'},
    'UTILIDADES':    {'icon': 'fas fa-chart-line',        'color_base': '#fef9c3', 'color_icon': '#a16207'},
    'LIQUIDACION':   {'icon': 'fas fa-file-invoice-dollar','color_base': '#fee2e2', 'color_icon': '#b91c1c'},
}

_ESTADO_META = {
    'PENDIENTE':  {'label': 'Por iniciar',  'badge': 'secondary', 'icon': 'far fa-circle'},
    'BORRADOR':   {'label': 'Borrador',     'badge': 'info',      'icon': 'fas fa-pen'},
    'CALCULADO':  {'label': 'Calculado',    'badge': 'primary',   'icon': 'fas fa-calculator'},
    'APROBADO':   {'label': 'Aprobado',     'badge': 'success',   'icon': 'fas fa-check-circle'},
    'CERRADO':    {'label': 'Cerrado',      'badge': 'dark',      'icon': 'fas fa-lock'},
    'ANULADO':    {'label': 'Anulado',      'badge': 'danger',    'icon': 'fas fa-times-circle'},
}


def _urgency(dias):
    """Clasifica urgencia por días restantes."""
    if dias < 0:
        return 'pasado'
    if dias <= 15:
        return 'critico'
    if dias <= 30:
        return 'urgente'
    if dias <= 60:
        return 'proximo'
    return 'planificado'


def _build_procesos_calendar(hoy, ultimo_regular):
    """
    Construye el calendario de procesos especiales para los últimos 3 años + siguiente.
    Devuelve dict {anio: [slot_dict, ...]} ordenado cronológicamente por año DESC.

    Cada slot tiene:
      tipo, label, ley, mes, anio, fecha_pago, dias, urgencia,
      estado, monto, monto_estimado, trabajadores, pk, creado,
      icon, color_base, color_icon, estado_label, estado_badge, estado_icon
    """
    # Estimaciones basadas en último período regular aprobado
    masa = float(ultimo_regular.total_neto or 0) if ultimo_regular else 0
    trab = int(ultimo_regular.total_trabajadores or 0) if ultimo_regular else 0
    estimados = {
        'GRATIFICACION': masa,           # equivalente a 1 sueldo mensual
        'CTS':           masa * 0.5,     # medio sueldo semestral
        'UTILIDADES':    masa * 0.18,    # ~18% de la masa (estimación conservadora)
    }

    # Índice de períodos existentes: (tipo, anio, mes) → PeriodoNomina
    existentes = {
        (p.tipo, p.anio, p.mes): p
        for p in PeriodoNomina.objects.filter(
            tipo__in=['GRATIFICACION', 'CTS', 'UTILIDADES', 'LIQUIDACION']
        ).only('tipo', 'anio', 'mes', 'estado', 'total_neto', 'total_trabajadores', 'pk')
    }

    anios = [hoy.year + 1, hoy.year, hoy.year - 1, hoy.year - 2]
    calendar = {}

    for anio in anios:
        slots = []
        for tipo, mes, label, ley in _SCHEDULE:
            try:
                fecha_pago = date(anio, mes, 15)
            except ValueError:
                fecha_pago = date(anio, mes, 28)

            dias = (fecha_pago - hoy).days
            periodo = existentes.get((tipo, anio, mes))
            meta_tipo   = _TIPO_META.get(tipo, _TIPO_META['GRATIFICACION'])
            monto_est   = estimados.get(tipo, 0)

            if periodo:
                estado = periodo.estado
                monto  = float(periodo.total_neto or 0)
                n_trab = int(periodo.total_trabajadores or trab)
                pk     = periodo.pk
                creado = True
            else:
                # Sólo mostrar años futuros o actuales como "por iniciar"
                # Años pasados sin período: mostrar igual pero como histórico perdido
                estado = 'PENDIENTE'
                monto  = 0.0
                n_trab = trab
                pk     = None
                creado = False

            meta_estado = _ESTADO_META.get(estado, _ESTADO_META['PENDIENTE'])

            slots.append({
                # Identificadores
                'tipo':          tipo,
                'mes':           mes,
                'anio':          anio,
                'label':         label,
                'ley':           ley,
                # Fechas
                'fecha_pago':    fecha_pago,
                'dias':          dias,
                'urgencia':      _urgency(dias),
                # Estado
                'estado':        estado,
                'estado_label':  meta_estado['label'],
                'estado_badge':  meta_estado['badge'],
                'estado_icon':   meta_estado['icon'],
                # Montos
                'monto':         monto,
                'monto_estimado': monto_est,
                'trabajadores':  n_trab,
                # Navegación
                'pk':            pk,
                'creado':        creado,
                # Visual
                'icon':          meta_tipo['icon'],
                'color_base':    meta_tipo['color_base'],
                'color_icon':    meta_tipo['color_icon'],
            })

        # Ordenar: primero los próximos (dias >= 0), luego los pasados
        slots.sort(key=lambda s: s['fecha_pago'])
        calendar[anio] = slots

    return calendar


# ─── Panel principal ───────────────────────────────────────────────────────────

@login_required
@solo_admin
def nominas_panel(request):
    """Lista de períodos + estadísticas + KPIs comparativos."""
    periodos = PeriodoNomina.objects.select_related('generado_por').order_by('-anio', '-mes')

    # Filtros
    anio = request.GET.get('anio', '')
    tipo = request.GET.get('tipo', '')
    if anio:
        periodos = periodos.filter(anio=anio)
    if tipo:
        periodos = periodos.filter(tipo=tipo)

    # Stats globales del último período APROBADO/CERRADO
    ultimo = PeriodoNomina.objects.filter(
        tipo='REGULAR', estado__in=['APROBADO', 'CERRADO']
    ).order_by('-anio', '-mes').first()

    anios_disp = PeriodoNomina.objects.values_list('anio', flat=True).distinct().order_by('-anio')

    # ── KPI 1: Comparativa últimos 3 períodos regulares ───────────────────────
    comparativa_meses = []
    try:
        ultimos_3 = list(
            PeriodoNomina.objects.filter(
                tipo='REGULAR',
                estado__in=['CALCULADO', 'APROBADO', 'CERRADO'],
            ).order_by('-anio', '-mes')[:3]
        )
        for i, p in enumerate(ultimos_3):
            neto = float(p.total_neto or 0)
            variacion_pct = None
            if i < len(ultimos_3) - 1:
                neto_ant = float(ultimos_3[i + 1].total_neto or 0)
                if neto_ant > 0:
                    variacion_pct = round(((neto - neto_ant) / neto_ant) * 100, 1)
            comparativa_meses.append({
                'periodo': str(p),
                'neto': neto,
                'trabajadores': p.total_trabajadores,
                'variacion_pct': variacion_pct,
                'estado': p.estado,
                'color_estado': p.color_estado,
            })
    except Exception:
        comparativa_meses = []

    # ── KPI 2: Distribución de conceptos del último período ───────────────────
    distribucion_conceptos_json = json.dumps({
        'remuneraciones': 0, 'descuentos': 0, 'aportes_empresa': 0,
    })
    try:
        if ultimo:
            agg = ultimo.registros.aggregate(
                remuneraciones=Sum('total_ingresos'),
                descuentos=Sum('total_descuentos'),
                aportes_empresa=Sum('aporte_essalud'),
            )
            distribucion_conceptos_json = json.dumps({
                'remuneraciones': float(agg['remuneraciones'] or 0),
                'descuentos':     float(agg['descuentos'] or 0),
                'aportes_empresa': float(agg['aportes_empresa'] or 0),
            })
    except Exception:
        pass

    # ── KPI 3: Top 5 mayores netos del último período ─────────────────────────
    top_sueldos = []
    try:
        if ultimo:
            top_sueldos = list(
                RegistroNomina.objects.filter(periodo=ultimo)
                .select_related('personal')
                .order_by('-neto_a_pagar')[:5]
            )
    except Exception:
        top_sueldos = []

    # ── KPI 4: Tendencia masa salarial — últimos 6 períodos ──────────────────
    masa_salarial_json = json.dumps([])
    try:
        ultimos_6 = list(
            PeriodoNomina.objects.filter(
                tipo='REGULAR',
                estado__in=['CALCULADO', 'APROBADO', 'CERRADO'],
            ).order_by('-anio', '-mes')[:6]
        )
        # Reverse to display chronologically (oldest → newest)
        ultimos_6.reverse()
        masa_data = [
            {
                'label': f'{p.mes:02d}/{str(p.anio)[2:]}',
                'neto': float(p.total_neto or 0),
            }
            for p in ultimos_6
        ]
        masa_salarial_json = json.dumps(masa_data)
    except Exception:
        pass

    # ── Calendario de Procesos Especiales ────────────────────────────────────
    hoy_d = date.today()
    _cal_dict = _build_procesos_calendar(hoy_d, ultimo)
    # Convertir a lista de dicts para que Django templates pueda iterar sin filtros custom
    cal_anios_list = [hoy_d.year + 1, hoy_d.year, hoy_d.year - 1, hoy_d.year - 2]
    cal_data = [
        {'anio': anio_k, 'slots': _cal_dict[anio_k]}
        for anio_k in cal_anios_list
    ]

    return render(request, 'nominas/panel.html', {
        'titulo': 'Nóminas',
        'periodos': periodos,
        'ultimo': ultimo,
        'tipo_choices': PeriodoNomina.TIPO_CHOICES,
        'estado_choices': PeriodoNomina.ESTADO_CHOICES,
        'anios_disp': anios_disp,
        'anio_filtro': anio,
        'tipo_filtro': tipo,
        # KPIs comparativos
        'comparativa_meses': comparativa_meses,
        'distribucion_conceptos_json': distribucion_conceptos_json,
        'top_sueldos': top_sueldos,
        'masa_salarial_json': masa_salarial_json,
        # Calendario procesos especiales
        'cal_data': cal_data,
        'cal_anio_actual': hoy_d.year,
        'cal_anios': cal_anios_list,
    })


# ─── Período ──────────────────────────────────────────────────────────────────

@login_required
@solo_admin
def periodo_crear(request):
    """Formulario para crear un nuevo período."""
    if request.method == 'POST':
        tipo  = request.POST.get('tipo', 'REGULAR')
        anio  = int(request.POST.get('anio', timezone.now().year))
        mes   = int(request.POST.get('mes', timezone.now().month))
        desc  = request.POST.get('descripcion', '')
        fi    = request.POST.get('fecha_inicio') or None
        ff    = request.POST.get('fecha_fin') or None
        fp    = request.POST.get('fecha_pago') or None

        if PeriodoNomina.objects.filter(tipo=tipo, anio=anio, mes=mes).exists():
            messages.error(request, 'Ya existe un período con ese tipo/año/mes.')
            return redirect('nominas_panel')

        p = PeriodoNomina.objects.create(
            tipo=tipo, anio=anio, mes=mes,
            descripcion=desc,
            fecha_inicio=fi, fecha_fin=ff, fecha_pago=fp,
        )
        messages.success(request, f'Período {p.descripcion or p} creado.')
        return redirect('nominas_periodo_detalle', pk=p.pk)

    # GET
    hoy = timezone.now()
    return render(request, 'nominas/periodo_form.html', {
        'titulo': 'Nuevo período de nómina',
        'tipo_choices': PeriodoNomina.TIPO_CHOICES,
        'anio_actual': hoy.year,
        'mes_actual':  hoy.month,
        'meses': range(1, 13),
        'anios': range(hoy.year - 1, hoy.year + 2),
    })


@login_required
@solo_admin
def periodo_detalle(request, pk):
    """Detalle del período: lista de registros de nómina."""
    periodo = get_object_or_404(PeriodoNomina, pk=pk)
    registros = (
        periodo.registros
        .select_related('personal')
        .order_by('personal__apellidos_nombres')
    )

    # Filtros
    grupo = request.GET.get('grupo', '')
    q = request.GET.get('q', '')
    if grupo:
        registros = registros.filter(grupo=grupo)
    if q:
        registros = registros.filter(personal__apellidos_nombres__icontains=q)

    grupos = periodo.registros.values_list('grupo', flat=True).distinct().order_by('grupo')

    # Calcular totales de las filas visibles (tras filtros server-side)
    agg = registros.aggregate(
        sueldo_base=Sum('sueldo_base'),
        total_ingresos=Sum('total_ingresos'),
        total_descuentos=Sum('total_descuentos'),
        neto_a_pagar=Sum('neto_a_pagar'),
        costo_total_empresa=Sum('costo_total_empresa'),
    )
    totales = {
        'sueldo_base':        agg['sueldo_base'] or Decimal('0'),
        'total_ingresos':     agg['total_ingresos'] or Decimal('0'),
        'total_descuentos':   agg['total_descuentos'] or Decimal('0'),
        'neto_a_pagar':       agg['neto_a_pagar'] or Decimal('0'),
        'costo_total_empresa':agg['costo_total_empresa'] or Decimal('0'),
    }

    return render(request, 'nominas/periodo_detalle.html', {
        'titulo': f'Nómina — {periodo}',
        'periodo': periodo,
        'registros': registros,
        'grupos': grupos,
        'grupo_filtro': grupo,
        'q': q,
        'totales': totales,
        'puede_generar': periodo.estado in ('BORRADOR', 'CALCULADO'),
        'puede_aprobar': periodo.estado == 'CALCULADO',
        'puede_exportar': periodo.estado in ('CALCULADO', 'APROBADO', 'CERRADO'),
    })


@login_required
@solo_admin
@require_POST
def periodo_generar(request, pk):
    """Genera/recalcula todos los registros del período."""
    periodo = get_object_or_404(PeriodoNomina, pk=pk)
    if periodo.estado in ('APROBADO', 'CERRADO', 'ANULADO'):
        messages.error(request, 'No se puede recalcular un período aprobado o cerrado.')
        return redirect('nominas_periodo_detalle', pk=pk)

    grupo = request.POST.get('grupo') or None
    stats = engine.generar_periodo(periodo, usuario=request.user, grupo=grupo)

    if stats.get('errores'):
        messages.warning(
            request,
            f"Generado con {stats['errores']} error(es). "
            f"Generados: {stats['generados']} | Actualizados: {stats['actualizados']}. "
            f"Errores: {'; '.join(stats.get('detalle_errores', [])[:3])}"
        )
    else:
        messages.success(
            request,
            f"Período generado: {stats['generados']} nuevos + "
            f"{stats['actualizados']} actualizados. "
            f"Neto total: S/ {stats['total_neto']:,.2f}"
        )
    return redirect('nominas_periodo_detalle', pk=pk)


@login_required
@solo_admin
@require_POST
def periodo_aprobar(request, pk):
    """Aprueba el período (lo bloquea para edición)."""
    periodo = get_object_or_404(PeriodoNomina, pk=pk)
    if periodo.estado != 'CALCULADO':
        messages.error(request, 'Solo se puede aprobar un período en estado CALCULADO.')
        return redirect('nominas_periodo_detalle', pk=pk)

    periodo.estado = 'APROBADO'
    periodo.aprobado_por = request.user
    periodo.aprobado_en  = timezone.now()
    periodo.save()
    messages.success(request, f'Período {periodo} aprobado correctamente.')
    return redirect('nominas_periodo_detalle', pk=pk)


@login_required
@solo_admin
def periodo_exportar(request, pk):
    """Exporta el período a CSV compatible con Excel (BOM UTF-8)."""
    periodo = get_object_or_404(PeriodoNomina, pk=pk)
    registros = (
        periodo.registros
        .select_related('personal')
        .prefetch_related('lineas__concepto')
        .order_by('personal__apellidos_nombres')
    )

    output = io.StringIO()
    output.write('\ufeff')  # BOM para Excel
    writer = csv.writer(output)

    # Encabezado
    writer.writerow([
        'DNI', 'Apellidos y Nombres', 'Grupo', 'AFP/ONP', 'AFP',
        'Días', 'Sueldo Base',
        'Sueldo Prop.', 'Asig. Familiar', 'HE 25%', 'HE 35%', 'HE 100%',
        'Otros Ingresos', 'Total Ingresos',
        'AFP Aporte', 'AFP Comisión', 'AFP Seguro', 'ONP',
        'IR 5ta', 'Desc. Préstamo', 'Otros Descuentos', 'Total Descuentos',
        'Neto a Pagar',
        'EsSalud', 'Prov. Gratif.', 'Prov. CTS', 'Costo Empresa',
    ])

    for r in registros:
        lineas_map = {l.concepto.codigo: l for l in r.lineas.all()}

        def _m(codigo):
            l = lineas_map.get(codigo)
            return float(l.monto) if l else 0.0

        writer.writerow([
            r.personal.nro_doc or '',
            r.personal.apellidos_nombres,
            r.grupo,
            r.regimen_pension,
            r.afp or '',
            r.dias_trabajados,
            float(r.sueldo_base),
            _m('sueldo-basico'),
            _m('asig-familiar'),
            _m('he-25'),
            _m('he-35'),
            _m('he-100'),
            _m('otros-ingresos'),
            float(r.total_ingresos),
            _m('afp-aporte'),
            _m('afp-comision'),
            _m('afp-seguro'),
            _m('onp'),
            _m('ir-5ta'),
            _m('descto-prestamo'),
            _m('otros-descuentos'),
            float(r.total_descuentos),
            float(r.neto_a_pagar),
            _m('essalud'),
            _m('prov-gratificacion'),
            _m('prov-cts'),
            float(r.costo_total_empresa),
        ])

    content = output.getvalue()
    nombre = f'nomina_{periodo.anio}_{str(periodo.mes).zfill(2)}_{periodo.tipo}.csv'
    response = HttpResponse(content.encode('utf-8-sig'), content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response


# ─── Registro individual ───────────────────────────────────────────────────────

@login_required
@solo_admin
def registro_detalle(request, pk):
    """Detalle de un registro individual de nómina."""
    reg = get_object_or_404(
        RegistroNomina.objects.select_related('personal', 'periodo')
        .prefetch_related('lineas__concepto'),
        pk=pk
    )
    lineas_ing  = reg.lineas.filter(concepto__tipo='INGRESO').order_by('concepto__orden')
    lineas_desc = reg.lineas.filter(concepto__tipo='DESCUENTO').order_by('concepto__orden')
    lineas_apc  = reg.lineas.filter(concepto__tipo='APORTE_EMPLEADOR').order_by('concepto__orden')
    lineas_prov = reg.lineas.filter(concepto__subtipo='PROVISION').order_by('concepto__orden')

    return render(request, 'nominas/registro_detalle.html', {
        'titulo': f'Boleta — {reg.personal}',
        'reg': reg,
        'lineas_ing':  lineas_ing,
        'lineas_desc': lineas_desc,
        'lineas_apc':  lineas_apc,
        'lineas_prov': lineas_prov,
        'puede_editar': reg.periodo.estado in ('BORRADOR', 'CALCULADO'),
    })


@login_required
@solo_admin
def registro_editar(request, pk):
    """Editar ajustes manuales de un registro y recalcular."""
    reg = get_object_or_404(RegistroNomina, pk=pk)
    if reg.periodo.estado in ('APROBADO', 'CERRADO', 'ANULADO'):
        messages.error(request, 'El período está aprobado o cerrado, no se puede editar.')
        return redirect('nominas_registro_detalle', pk=pk)

    if request.method == 'POST':
        reg.dias_trabajados   = int(request.POST.get('dias_trabajados', 30))
        reg.horas_extra_25    = Decimal(request.POST.get('horas_extra_25', '0'))
        reg.horas_extra_35    = Decimal(request.POST.get('horas_extra_35', '0'))
        reg.horas_extra_100   = Decimal(request.POST.get('horas_extra_100', '0'))
        reg.asignacion_familiar = 'asignacion_familiar' in request.POST
        reg.otros_ingresos    = Decimal(request.POST.get('otros_ingresos', '0'))
        reg.descuento_prestamo= Decimal(request.POST.get('descuento_prestamo', '0'))
        reg.otros_descuentos  = Decimal(request.POST.get('otros_descuentos', '0'))
        reg.save()

        # Recalcular
        conceptos = ConceptoRemunerativo.objects.filter(activo=True).order_by('tipo', 'orden')
        resultado = engine.calcular_registro(reg, conceptos)

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
        reg.total_ingresos      = resultado['total_ingresos']
        reg.total_descuentos    = resultado['total_descuentos']
        reg.neto_a_pagar        = resultado['neto_a_pagar']
        reg.aporte_essalud      = resultado['aporte_essalud']
        reg.costo_total_empresa = resultado['costo_total_empresa']
        reg.estado = 'CALCULADO'
        reg.save()

        messages.success(request, 'Registro recalculado correctamente.')
        return redirect('nominas_registro_detalle', pk=pk)

    return render(request, 'nominas/registro_editar.html', {
        'titulo': f'Editar — {reg.personal}',
        'reg': reg,
    })


# ─── Conceptos remunerativos ───────────────────────────────────────────────────

@login_required
@solo_admin
def conceptos_panel(request):
    """Panel de conceptos remunerativos."""
    conceptos = ConceptoRemunerativo.objects.all().order_by('tipo', 'orden', 'nombre')
    return render(request, 'nominas/conceptos.html', {
        'titulo': 'Conceptos Remunerativos',
        'conceptos': conceptos,
        'tipo_choices': ConceptoRemunerativo.TIPO_CHOICES,
    })


@login_required
@solo_admin
@require_POST
def concepto_crear(request):
    """Crea un concepto remunerativo (AJAX)."""
    try:
        c = ConceptoRemunerativo.objects.create(
            codigo   = request.POST['codigo'].strip().lower(),
            nombre   = request.POST['nombre'].strip(),
            tipo     = request.POST.get('tipo', 'INGRESO'),
            subtipo  = request.POST.get('subtipo', 'REMUNERATIVO'),
            formula  = request.POST.get('formula', 'MANUAL'),
            porcentaje=Decimal(request.POST.get('porcentaje', '0')),
            orden    = int(request.POST.get('orden', 99)),
            activo   = True,
            es_sistema=False,
        )
        return JsonResponse({'ok': True, 'id': c.pk, 'nombre': c.nombre})
    except Exception as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)


@login_required
@solo_admin
@require_POST
def concepto_eliminar(request, pk):
    """Elimina un concepto no-sistema (AJAX)."""
    c = get_object_or_404(ConceptoRemunerativo, pk=pk)
    if c.es_sistema:
        return JsonResponse({'ok': False, 'error': 'No se puede eliminar un concepto del sistema.'}, status=400)
    nombre = c.nombre
    c.delete()
    return JsonResponse({'ok': True, 'nombre': nombre})


# ─── Portal: Mis Recibos ───────────────────────────────────────────────────────

@login_required
def mis_recibos(request):
    """Portal del trabajador: historial de recibos de nómina."""
    from personal.models import Personal
    try:
        empleado = Personal.objects.get(usuario=request.user)
    except Personal.DoesNotExist:
        empleado = None

    registros = []
    if empleado:
        registros = (
            RegistroNomina.objects
            .filter(personal=empleado, periodo__estado__in=['APROBADO', 'CERRADO'])
            .select_related('periodo')
            .order_by('-periodo__anio', '-periodo__mes')
        )

    return render(request, 'nominas/mis_recibos.html', {
        'titulo': 'Mis Recibos de Nómina',
        'empleado': empleado,
        'registros': registros,
    })


# ─── Resumen estadístico AJAX ──────────────────────────────────────────────────

@login_required
@solo_admin
def periodo_resumen_ajax(request, pk):
    """
    Devuelve JSON con estadísticas resumidas del período de nómina.
    Útil para mostrar el panel de resumen en la vista de detalle sin recargar.
    """
    periodo = get_object_or_404(PeriodoNomina, pk=pk)
    registros = periodo.registros.select_related('personal')

    # Totales globales del período
    agg = registros.aggregate(
        total_bruto=Sum('total_ingresos'),
        total_neto=Sum('neto_a_pagar'),
        total_essalud=Sum('aporte_essalud'),
    )

    # AFP y ONP: sumar montos de líneas por fórmula del concepto
    total_afp = Decimal('0')
    total_onp = Decimal('0')
    for reg in registros.prefetch_related('lineas__concepto'):
        for linea in reg.lineas.all():
            formula = linea.concepto.formula
            if formula in ('AFP_APORTE', 'AFP_COMISION', 'AFP_SEGURO'):
                total_afp += linea.monto or Decimal('0')
            elif formula == 'ONP':
                total_onp += linea.monto or Decimal('0')

    # Distribución por régimen pensionario
    from django.db.models import Count
    por_regimen_qs = (
        registros.values('regimen_pension')
        .annotate(total=Count('id'))
        .order_by('regimen_pension')
    )
    por_regimen = {item['regimen_pension']: item['total'] for item in por_regimen_qs}

    # Distribución por grupo
    por_grupo_qs = (
        registros.values('grupo')
        .annotate(total=Count('id'))
        .order_by('grupo')
    )
    por_grupo = {(item['grupo'] or '—'): item['total'] for item in por_grupo_qs}

    return JsonResponse({
        'trabajadores':  registros.count(),
        'total_bruto':   float(agg['total_bruto'] or 0),
        'total_neto':    float(agg['total_neto'] or 0),
        'total_essalud': float(agg['total_essalud'] or 0),
        'total_afp':     float(total_afp),
        'total_onp':     float(total_onp),
        'por_regimen':   por_regimen,
        'por_grupo':     por_grupo,
    })


# ─── Boletas ZIP masivo ─────────────────────────────────────────────────────────

@login_required
@solo_admin
def periodo_boletas_zip(request, pk):
    """
    Genera un archivo ZIP con todas las boletas PDF del período.
    Solo disponible para períodos en estado CALCULADO, APROBADO o CERRADO.
    """
    periodo = get_object_or_404(PeriodoNomina, pk=pk)

    if periodo.estado not in ('CALCULADO', 'APROBADO', 'CERRADO'):
        messages.error(request, 'Solo se pueden descargar boletas de períodos calculados o aprobados.')
        return redirect('nominas_periodo_detalle', pk=pk)

    registros = (
        periodo.registros
        .select_related('personal')
        .prefetch_related('lineas__concepto')
        .order_by('personal__apellidos_nombres')
    )

    try:
        from .pdf import generar_boleta_pdf
    except ImportError:
        messages.error(request, 'El módulo de PDF no está disponible.')
        return redirect('nominas_periodo_detalle', pk=pk)

    zip_buffer = io.BytesIO()
    errores = []

    with zipfile.ZipFile(zip_buffer, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for reg in registros:
            try:
                pdf_bytes = generar_boleta_pdf(reg)
                nro_doc = reg.personal.nro_doc or f'reg{reg.pk}'
                nombre_archivo = (
                    f'Boleta_{nro_doc}_'
                    f'{periodo.anio}{str(periodo.mes).zfill(2)}.pdf'
                )
                zf.writestr(nombre_archivo, pdf_bytes)
            except Exception as e:
                errores.append(f'{reg.personal}: {e}')

    if errores:
        messages.warning(
            request,
            f'Se generaron las boletas con {len(errores)} error(es): '
            + '; '.join(errores[:5])
        )

    zip_buffer.seek(0)
    nombre_zip = f'Boletas_{periodo.anio}{str(periodo.mes).zfill(2)}_{periodo.tipo}.zip'
    response = HttpResponse(zip_buffer.read(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{nombre_zip}"'
    return response


# ─── Boleta PDF ────────────────────────────────────────────────────────────────

@login_required
def boleta_pdf(request, pk):
    """
    Descarga la boleta de pago en PDF para un RegistroNomina.
    - Superusers/staff pueden ver cualquier boleta.
    - Trabajadores solo pueden ver sus propias boletas (via portal).
    """
    registro = get_object_or_404(
        RegistroNomina.objects.select_related('personal', 'periodo'),
        pk=pk,
    )

    # Control acceso: solo admin o el propio trabajador
    if not (request.user.is_superuser or request.user.is_staff):
        if not hasattr(request.user, 'personal') or request.user.personal != registro.personal:
            from django.http import HttpResponseForbidden
            return HttpResponseForbidden('No tienes permiso para ver esta boleta.')

    try:
        from .pdf import generar_boleta_pdf
        pdf_bytes = generar_boleta_pdf(registro)
    except Exception as e:
        messages.error(request, f'Error generando PDF: {e}')
        return redirect('nominas_registro_detalle', pk=pk)

    nombre = (
        f'Boleta_{registro.personal.nro_doc}_'
        f'{registro.periodo.anio}{registro.periodo.mes:02d}.pdf'
    )
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{nombre}"'
    return response


# ─── Gratificaciones Panel ─────────────────────────────────────────────────────

@login_required
@solo_admin
def gratificacion_panel(request):
    """Redirige al panel principal con la sección de procesos especiales."""
    return redirect('/nominas/#gratificaciones')


# ─── Crear Período Especial (Gratificación / CTS) ─────────────────────────────

@login_required
@solo_admin
@require_POST
def crear_periodo_especial(request):
    """
    Crea un período especial de tipo GRATIFICACION o CTS con las fechas
    legalmente correctas según el mes/año indicado.

    Para GRATIFICACION:
      - mes=7  (Julio):    período June 1 – June 30, pago July 15
      - mes=12 (Dic):      período Dec 1 – Dec 15,   pago Dec 15

    Para CTS:
      - mes=5  (Mayo):     período Nov 1 año ant – Apr 30 año act, pago May 15
      - mes=11 (Nov):      período May 1 – Oct 31, pago Nov 15
    """
    tipo = request.POST.get('tipo', '').upper()
    try:
        anio = int(request.POST.get('anio', timezone.now().year))
        mes  = int(request.POST.get('mes', 7))
    except (ValueError, TypeError):
        messages.error(request, 'Año o mes inválido.')
        return redirect('nominas_gratificaciones')

    if tipo not in ('GRATIFICACION', 'CTS'):
        messages.error(request, 'Tipo de período inválido.')
        return redirect('nominas_gratificaciones')

    # Calcular fechas según tipo y mes
    if tipo == 'GRATIFICACION':
        if mes == 7:
            fecha_inicio = date(anio, 6, 1)
            fecha_fin    = date(anio, 6, 30)
            fecha_pago   = date(anio, 7, 15)
            descripcion  = f'Gratificación Julio {anio}'
        else:
            # Diciembre: período Dec 1 - Dec 15
            fecha_inicio = date(anio, 12, 1)
            fecha_fin    = date(anio, 12, 15)
            fecha_pago   = date(anio, 12, 15)
            descripcion  = f'Gratificación Diciembre {anio}'
    else:
        # CTS
        if mes == 5:
            # Mayo: período Nov 1 (año ant) – Apr 30 (año act)
            fecha_inicio = date(anio - 1, 11, 1)
            fecha_fin    = date(anio, 4, 30)
            fecha_pago   = date(anio, 5, 15)
            descripcion  = f'CTS Mayo {anio} (Nov {anio-1}–Abr {anio})'
        else:
            # Noviembre: período May 1 – Oct 31
            fecha_inicio = date(anio, 5, 1)
            fecha_fin    = date(anio, 10, 31)
            fecha_pago   = date(anio, 11, 15)
            descripcion  = f'CTS Noviembre {anio} (May–Oct {anio})'

    # Verificar que no exista ya
    if PeriodoNomina.objects.filter(tipo=tipo, anio=anio, mes=mes).exists():
        messages.warning(
            request,
            f'Ya existe un período de {tipo} para {anio}/{mes:02d}. '
            f'Revisa la lista de períodos.'
        )
        redirect_url = 'nominas_gratificaciones' if tipo == 'GRATIFICACION' else 'nominas_panel'
        return redirect(redirect_url)

    periodo = PeriodoNomina.objects.create(
        tipo=tipo,
        anio=anio,
        mes=mes,
        descripcion=descripcion,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        fecha_pago=fecha_pago,
    )

    messages.success(
        request,
        f'Período "{descripcion}" creado correctamente. '
        f'Período: {fecha_inicio.strftime("%d/%m/%Y")} al {fecha_fin.strftime("%d/%m/%Y")}. '
        f'Fecha de pago: {fecha_pago.strftime("%d/%m/%Y")}. '
        f'Haz clic en "Generar planilla" para calcular los montos.'
    )
    return redirect('nominas_periodo_detalle', pk=periodo.pk)


# ─── IR 5ta Panel ──────────────────────────────────────────────────────────────

@login_required
@solo_admin
def ir5ta_panel(request):
    """
    Panel de IR 5ta Categoría — Perú 2026.
    Muestra la escala de retención y proyección anual por empleado activo.
    Base legal: Art. 53° + 75° TUO LIR — escala progresiva, 7 UIT deducción.
    """
    from personal.models import Personal

    uit = engine.UIT_2026  # S/ 5,350
    deduccion = engine.IR_5TA_DEDUCCION_UITS * uit  # 7 × 5,350 = S/ 37,450

    # Escala IR 5ta con límites en soles para la tabla visual
    # Tramos acumulativos: (limite_acum_uits, tasa%)
    # 0-5 UIT → 8%  |  5-20 UIT → 14%  |  20-35 UIT → 17%
    # 35-45 UIT → 20%  |  >45 UIT → 30%
    escala_visual = [
        {'tramo': 'Hasta 5 UIT',   'uits': '0 — 5',   'limite_s': uit * 5,  'tasa': Decimal('8'),  'color': 'success'},
        {'tramo': '5 a 20 UIT',    'uits': '5 — 20',  'limite_s': uit * 20, 'tasa': Decimal('14'), 'color': 'info'},
        {'tramo': '20 a 35 UIT',   'uits': '20 — 35', 'limite_s': uit * 35, 'tasa': Decimal('17'), 'color': 'warning'},
        {'tramo': '35 a 45 UIT',   'uits': '35 — 45', 'limite_s': uit * 45, 'tasa': Decimal('20'), 'color': 'orange'},
        {'tramo': 'Más de 45 UIT', 'uits': '> 45',    'limite_s': None,     'tasa': Decimal('30'), 'color': 'danger'},
    ]

    # Empleados activos con sueldo_base > 0
    empleados_qs = (
        Personal.objects
        .filter(estado='Activo', sueldo_base__isnull=False, sueldo_base__gt=0)
        .order_by('-sueldo_base', 'apellidos_nombres')
        .values(
            'pk', 'apellidos_nombres', 'nro_doc', 'sueldo_base',
            'grupo_tareo', 'asignacion_familiar',
            # nuevos campos nómina
            'tiene_eps', 'eps_descuento_mensual', 'viaticos_mensual',
        )
    )

    asig_fam_monto = engine.ASIG_FAM  # S/ 102.50

    empleados = []
    total_ir_mensual = Decimal('0')

    for emp in empleados_qs:
        sueldo = Decimal(str(emp['sueldo_base']))
        asig   = asig_fam_monto if emp.get('asignacion_familiar') else Decimal('0')
        rem_computable = sueldo + asig

        # Proyección anual = sueldo computable × 14
        # (12 meses + gratificación julio + gratificación diciembre)
        anual = rem_computable * Decimal('14')

        # EPS: co-pago anual del trabajador (deducible del base IR 5ta)
        tiene_eps         = bool(emp.get('tiene_eps', False))
        eps_mensual       = Decimal(str(emp.get('eps_descuento_mensual') or '0'))
        eps_anual         = eps_mensual * Decimal('12')

        # Viáticos: monto mensual fijo (NO remunerativo, excluido de base IR 5ta)
        viaticos_mensual  = Decimal(str(emp.get('viaticos_mensual') or '0'))

        # Renta neta imponible = anual - EPS anual - 7 UIT
        rni = max(anual - eps_anual - deduccion, Decimal('0'))

        # IR anual y mensual (pasando deducción EPS al engine)
        ir_mensual = engine.calcular_ir_5ta_mensual(anual, deduccion_eps_anual=eps_anual)
        ir_anual   = ir_mensual * Decimal('12')

        # Clasificar para color de fila
        if ir_mensual == 0:
            fila_clase = 'no-ir'
        elif rni <= uit * 5:
            fila_clase = 'ir-8'
        elif rni <= uit * 20:
            fila_clase = 'ir-14'
        else:
            fila_clase = 'ir-alto'

        empleados.append({
            'pk':               emp['pk'],
            'apellidos_nombres':emp['apellidos_nombres'],
            'numero_documento': emp['nro_doc'],
            'sueldo_base':      sueldo,
            'asig_fam':         asig,
            'asignacion_familiar': bool(emp.get('asignacion_familiar')),
            'rem_computable':   rem_computable,
            'grupo':            emp.get('grupo_tareo', ''),
            'anual_proyectado': anual,
            'rni':              rni,
            'ir_anual':         ir_anual,
            'ir_mensual':       ir_mensual,
            'fila_clase':       fila_clase,
            # EPS / viáticos
            'tiene_eps':        tiene_eps,
            'eps_mensual':      eps_mensual,
            'eps_anual':        eps_anual,
            'viaticos_mensual': viaticos_mensual,
        })
        total_ir_mensual += ir_mensual

    # ── Resumen por tramo (para cards de distribución) ──────────────────────
    resumen = {
        'sin_ir':     sum(1 for e in empleados if e['ir_mensual'] == 0),
        'tramo_8':    sum(1 for e in empleados if e['fila_clase'] == 'ir-8'),
        'tramo_14':   sum(1 for e in empleados if e['fila_clase'] == 'ir-14'),
        'tramo_17_mas': sum(1 for e in empleados if e['fila_clase'] == 'ir-alto'),
        'total_con_ir': sum(1 for e in empleados if e['ir_mensual'] > 0),
        'con_eps':    sum(1 for e in empleados if e['tiene_eps']),
        'con_viaticos': sum(1 for e in empleados if e['viaticos_mensual'] > 0),
    }

    return render(request, 'nominas/ir5ta_panel.html', {
        'titulo': 'IR 5ta Categoría — 2026',
        'uit': uit,
        'deduccion': deduccion,
        'escala_visual': escala_visual,
        'empleados': empleados,
        'total_ir_mensual': total_ir_mensual,
        'total_empleados': len(empleados),
        'pagan_ir': sum(1 for e in empleados if e['ir_mensual'] > 0),
        'resumen': resumen,
    })


# ─── IR 5ta AJAX por RegistroNomina ───────────────────────────────────────────

@login_required
@solo_admin
def registro_ir5ta_ajax(request, pk):
    """
    Devuelve JSON con el desglose de IR 5ta para un RegistroNomina específico.
    Útil para mostrar detalles en modal desde la vista de período.
    """
    reg = get_object_or_404(
        RegistroNomina.objects.select_related('personal', 'periodo'),
        pk=pk
    )

    uit = engine.UIT_2026
    deduccion_uits = engine.IR_5TA_DEDUCCION_UITS

    # Remuneración computable mensual y proyección anual
    sueldo = reg.sueldo_base
    asig_fam = engine.ASIG_FAM if reg.asignacion_familiar else Decimal('0')
    rem_computable = sueldo + asig_fam

    # Proyección anual (mismo criterio que el engine)
    rem_anual = rem_computable * Decimal('12')

    deduccion = deduccion_uits * uit
    rni = max(rem_anual - deduccion, Decimal('0'))
    ir_anual = engine.calcular_ir_5ta_mensual(rem_anual) * Decimal('12')
    ir_mensual = engine.calcular_ir_5ta_mensual(rem_anual)

    # Desglose por tramos para transparencia
    tramos = []
    anterior = Decimal('0')
    for limite_uits, tasa in engine.IR_5TA_ESCALA:
        if rni <= 0:
            break
        if limite_uits is None:
            limite_s = None
            exceso = max(rni - anterior, Decimal('0'))
            label = f'> {int(anterior / uit)} UIT'
        else:
            limite_s = limite_uits * uit
            exceso = max(min(rni, limite_s) - anterior, Decimal('0'))
            label = f'{int(anterior / uit) if anterior > 0 else 0}–{int(limite_uits)} UIT'

        if exceso > 0:
            impuesto_tramo = (exceso * tasa / Decimal('100')).quantize(Decimal('0.01'))
            tramos.append({
                'tramo': label,
                'base': float(exceso),
                'tasa': float(tasa),
                'impuesto': float(impuesto_tramo),
            })

        if limite_uits is None:
            break
        anterior = limite_s
        if rni <= anterior:
            break

    return JsonResponse({
        'trabajador':        str(reg.personal),
        'sueldo_base':       float(sueldo),
        'asig_familiar':     float(asig_fam),
        'rem_computable':    float(rem_computable),
        'rem_anual':         float(rem_anual),
        'uit':               float(uit),
        'deduccion_7uits':   float(deduccion),
        'rni':               float(rni),
        'ir_anual':          float(ir_anual),
        'ir_mensual':        float(ir_mensual),
        'tramos':            tramos,
    })


# ─── Flujo de Caja de Planilla ─────────────────────────────────────────────────

@login_required
@solo_admin
def flujo_caja_panel(request):
    """
    Panel de proyección de flujo de caja de planilla.
    Muestra proyección mensual de todos los desembolsos de RR.HH.
    vs. presupuesto aprobado (si existe).
    """
    n_meses = int(request.GET.get('meses', 18))
    n_meses = max(6, min(n_meses, 36))

    meses, empleados = proyectar_flujo_caja(n_meses=n_meses)

    # Enriquecer con presupuesto si existe
    presupuestos = PresupuestoPlanilla.objects.all()
    presup_map = {(p.anio, p.mes): p for p in presupuestos}
    tiene_presupuesto = False
    for mes in meses:
        key = (mes['fecha'].year, mes['fecha'].month)
        presup = presup_map.get(key)
        if presup:
            tiene_presupuesto = True
            mes['presup_total'] = presup.presup_total
            mes['variacion']    = mes['total_desembolso'] - presup.presup_total
            mes['variacion_pct'] = (
                mes['variacion'] / presup.presup_total * 100
                if presup.presup_total else None
            )

    # Totales de resumen
    total_18m         = sum(m['total_desembolso'] for m in meses)
    promedio_mensual  = total_18m / len(meses) if meses else Decimal('0')
    headcount_actual  = meses[0]['headcount'] if meses else 0
    meses_con_vencimientos = sum(1 for m in meses if m['liquidaciones'] > 0)
    # Empleados cuyo contrato vence dentro del horizonte proyectado
    from decimal import Decimal as _D
    from datetime import date as _date
    from dateutil.relativedelta import relativedelta as _rd
    _hoy = _date.today()
    _horizon = _hoy.replace(day=1) + _rd(months=n_meses)
    empleados_por_vencer = sum(
        1 for e in empleados
        if e.get('fecha_fin_contrato') and _hoy.replace(day=1) <= e['fecha_fin_contrato'] < _horizon
    )

    # Datos para Chart.js
    chart_labels   = json.dumps([m['mes_label'] for m in meses])
    chart_neto     = json.dumps([float(m['neto'])          for m in meses])
    chart_cond     = json.dumps([float(m['cond_trabajo'])   for m in meses])
    chart_alim     = json.dumps([float(m['alimentacion'])   for m in meses])
    chart_essalud  = json.dumps([float(m['essalud'])        for m in meses])
    chart_gratif   = json.dumps([float(m['gratificaciones']) for m in meses])
    chart_cts      = json.dumps([float(m['cts'])            for m in meses])
    chart_liq      = json.dumps([float(m['liquidaciones'])  for m in meses])
    chart_headcount = json.dumps([m['headcount']            for m in meses])
    chart_total    = json.dumps([float(m['total_desembolso']) for m in meses])
    chart_presup   = json.dumps([
        float(m['presup_total']) if m['presup_total'] is not None else None
        for m in meses
    ])

    return render(request, 'nominas/flujo_caja.html', {
        'meses':            meses,
        'empleados':        empleados,
        'n_meses':          n_meses,
        'tiene_presupuesto':      tiene_presupuesto,
        'total_18m':              total_18m,
        'promedio_mensual':       promedio_mensual,
        'headcount_actual':       headcount_actual,
        'meses_con_vencimientos': meses_con_vencimientos,
        'empleados_por_vencer':   empleados_por_vencer,
        # Charts
        'chart_labels':    chart_labels,
        'chart_neto':      chart_neto,
        'chart_cond':      chart_cond,
        'chart_alim':      chart_alim,
        'chart_essalud':   chart_essalud,
        'chart_gratif':    chart_gratif,
        'chart_cts':       chart_cts,
        'chart_liq':       chart_liq,
        'chart_headcount': chart_headcount,
        'chart_total':     chart_total,
        'chart_presup':    chart_presup,
    })


@login_required
@solo_admin
def presupuesto_guardar(request):
    """
    API — guarda o actualiza el presupuesto de un mes.
    POST JSON: {anio, mes, presup_total, presup_rem_bruta?,
                presup_cond_trabajo?, presup_alimentacion?,
                presup_essalud?, presup_gratif?, presup_cts?,
                presup_liquidaciones?, observaciones?}
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
        anio = int(data['anio'])
        mes  = int(data['mes'])

        def _d(key, default='0'):
            return Decimal(str(data.get(key, default) or '0'))

        presup, created = PresupuestoPlanilla.objects.update_or_create(
            anio=anio, mes=mes, empresa=None,
            defaults={
                'presup_rem_bruta':     _d('presup_rem_bruta'),
                'presup_cond_trabajo':  _d('presup_cond_trabajo'),
                'presup_alimentacion':  _d('presup_alimentacion'),
                'presup_essalud':       _d('presup_essalud'),
                'presup_gratif':        _d('presup_gratif'),
                'presup_cts':           _d('presup_cts'),
                'presup_liquidaciones': _d('presup_liquidaciones'),
                'presup_total':         _d('presup_total'),
                'observaciones':        data.get('observaciones', ''),
                'creado_por':           request.user,
            }
        )
        return JsonResponse({'ok': True, 'created': created, 'id': presup.pk})

    except (KeyError, ValueError, Exception) as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@solo_admin
def presupuesto_eliminar(request, anio, mes):
    """Elimina el presupuesto de un mes específico."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    deleted, _ = PresupuestoPlanilla.objects.filter(anio=anio, mes=mes, empresa=None).delete()
    return JsonResponse({'ok': True, 'deleted': deleted})
