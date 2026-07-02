"""
Cierre Mensual — Vistas.
"""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.contrib import messages

import calendar
from datetime import date

from asistencia.views._common import solo_admin
from cierre.models import PeriodoCierre, PasoCierre
from cierre.engine import inicializar_pasos, ejecutar_paso, PASOS_ORDENADOS


@login_required
@solo_admin
def cierre_lista(request):
    """Lista de todos los períodos de cierre."""
    from datetime import date
    hoy = date.today()

    periodos = PeriodoCierre.objects.prefetch_related('pasos').all()

    # Crear período actual si no existe
    periodo_actual = PeriodoCierre.objects.filter(
        anio=hoy.year, mes=hoy.month,
    ).first()

    context = {
        'periodos': periodos,
        'periodo_actual': periodo_actual,
        'anio_actual': hoy.year,
        'mes_actual': hoy.month,
    }
    return render(request, 'cierre/lista.html', context)


@login_required
@solo_admin
def cierre_wizard(request, pk):
    """Wizard de cierre para un período específico."""
    periodo = get_object_or_404(PeriodoCierre, pk=pk)
    inicializar_pasos(periodo)

    pasos = periodo.pasos.all()

    # Determinar el paso actual (primer PENDIENTE o ERROR)
    paso_actual = pasos.filter(estado__in=['PENDIENTE', 'ERROR']).first()

    context = {
        'periodo': periodo,
        'pasos': pasos,
        'paso_actual': paso_actual,
        'puede_ejecutar': not periodo.esta_cerrado,
    }
    return render(request, 'cierre/wizard.html', context)


@login_required
@solo_admin
def cierre_crear(request):
    """Crea un nuevo período de cierre."""
    if request.method == 'POST':
        try:
            anio = int(request.POST.get('anio', 0))
            mes = int(request.POST.get('mes', 0))
        except (ValueError, TypeError):
            anio, mes = 0, 0

        if not (1 <= mes <= 12 and anio >= 2020):
            messages.error(request, 'Año o mes inválido.')
            return redirect('cierre_lista')

        periodo, created = PeriodoCierre.objects.get_or_create(
            anio=anio, mes=mes,
        )
        if not created:
            messages.info(request, f'El período {periodo} ya existe.')
        else:
            messages.success(request, f'Período {periodo} creado.')

        inicializar_pasos(periodo)
        return redirect('cierre_wizard', pk=periodo.pk)

    return redirect('cierre_lista')


@login_required
@solo_admin
def cierre_ejecutar_paso(request, pk, codigo):
    """AJAX: ejecuta un paso del wizard y devuelve el resultado."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    periodo = get_object_or_404(PeriodoCierre, pk=pk)

    if periodo.esta_cerrado and codigo != 'BLOQUEAR_PERIODO':
        return JsonResponse({'error': 'Período ya cerrado'}, status=400)

    resultado = ejecutar_paso(periodo, codigo)

    # Actualizar estado del período si se está iniciando el proceso
    if periodo.estado == 'ABIERTO':
        periodo.estado = 'EN_CIERRE'
        periodo.save(update_fields=['estado'])

    # Recalcular avance
    periodo.refresh_from_db()

    return JsonResponse({
        'estado':   resultado['estado'],
        'mensaje':  resultado['mensaje'],
        'detalles': resultado['detalles'],
        'datos':    resultado.get('datos', {}),
        'avance':   periodo.porcentaje_avance,
        'periodo_estado': periodo.estado,
    })


@login_required
@solo_admin
def cierre_ejecutar_todos(request, pk):
    """AJAX: ejecuta todos los pasos pendientes en secuencia."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    periodo = get_object_or_404(PeriodoCierre, pk=pk)

    if periodo.estado == 'ABIERTO':
        periodo.estado = 'EN_CIERRE'
        periodo.save(update_fields=['estado'])

    inicializar_pasos(periodo)
    resultados = []

    for codigo, _ in PASOS_ORDENADOS:
        paso = PasoCierre.objects.get(periodo=periodo, codigo=codigo)
        if paso.estado in ('OK', 'OMITIDO'):
            resultados.append({'codigo': codigo, 'estado': 'OK', 'omitido': True})
            continue

        resultado = ejecutar_paso(periodo, codigo)
        resultados.append({'codigo': codigo, **resultado})

        # Si falla un paso crítico, detener
        if resultado['estado'] == 'ERROR':
            break

    periodo.refresh_from_db()
    return JsonResponse({
        'resultados':      resultados,
        'avance':          periodo.porcentaje_avance,
        'periodo_estado':  periodo.estado,
    })


@login_required
@solo_admin
def cierre_reabrir(request, pk):
    """Reabre un período cerrado para correcciones."""
    if request.method != 'POST':
        return redirect('cierre_wizard', pk=pk)

    periodo = get_object_or_404(PeriodoCierre, pk=pk)
    periodo.estado = 'REABIERTO'
    periodo.cerrado_en = None
    periodo.save(update_fields=['estado', 'cerrado_en'])

    # Resetear paso de bloqueo
    PasoCierre.objects.filter(
        periodo=periodo, codigo='BLOQUEAR_PERIODO',
    ).update(estado='PENDIENTE', resultado={}, ejecutado_en=None)

    messages.warning(request, f'Período {periodo} reabierto.')
    return redirect('cierre_wizard', pk=pk)


@login_required
@solo_admin
def cierre_resumen(request, pk):
    """
    AJAX: Devuelve el resumen pre-cierre del período (headcount, bruto estimado,
    alertas previas).  Llamado desde el wizard antes de ejecutar pasos.
    """
    from django.db.models import Sum, Count, Q
    from asistencia.models import ConfiguracionSistema, RegistroTareo
    from personal.models import Personal

    periodo = get_object_or_404(PeriodoCierre, pk=pk)
    config = ConfiguracionSistema.get()
    inicio, fin = config.get_ciclo_asistencia(periodo.anio, periodo.mes)

    # ── Headcount ───────────────────────────────────────────────
    total_activos = Personal.objects.filter(estado='Activo').count()
    staff_activos = Personal.objects.filter(estado='Activo', grupo_tareo='STAFF').count()
    rco_activos   = Personal.objects.filter(estado='Activo', grupo_tareo='RCO').count()

    # ── Registros del período ────────────────────────────────────
    qs_period = RegistroTareo.objects.filter(fecha__gte=inicio, fecha__lte=fin)
    total_registros  = qs_period.count()
    trabajadores_con_registro = qs_period.values('personal').distinct().count()

    # ── Alertas previas ─────────────────────────────────────────
    alertas = []

    sin_marcacion = total_activos - trabajadores_con_registro
    if sin_marcacion > 0:
        alertas.append({
            'nivel': 'warning',
            'icono': 'fas fa-user-clock',
            'mensaje': f'{sin_marcacion} trabajador(es) sin marcación en el período',
        })

    sin_personal = qs_period.filter(personal__isnull=True).count()
    if sin_personal > 0:
        alertas.append({
            'nivel': 'danger',
            'icono': 'fas fa-user-times',
            'mensaje': f'{sin_personal} registro(s) sin empleado vinculado (DNI no encontrado)',
        })

    ss_count = qs_period.filter(codigo_dia='SS').count()
    if ss_count > 0:
        alertas.append({
            'nivel': 'warning',
            'icono': 'fas fa-sign-out-alt',
            'mensaje': f'{ss_count} registro(s) con código SS (Sin Salida) pendientes',
        })

    faltas = qs_period.filter(codigo_dia='FA').count()
    if faltas > 0:
        alertas.append({
            'nivel': 'info',
            'icono': 'fas fa-calendar-times',
            'mensaje': f'{faltas} falta(s) (FA) registradas en el período',
        })

    # ── HE totales ───────────────────────────────────────────────
    he_agg = qs_period.aggregate(
        he25=Sum('he_25'), he35=Sum('he_35'), he100=Sum('he_100'),
    )
    he_total = float((he_agg['he25'] or 0) + (he_agg['he35'] or 0) + (he_agg['he100'] or 0))

    if not alertas:
        alertas.append({
            'nivel': 'success',
            'icono': 'fas fa-check-circle',
            'mensaje': 'Sin alertas previas — el período está listo para cierre',
        })

    return JsonResponse({
        'ok': True,
        'periodo': str(periodo),
        'rango': f'{inicio.strftime("%d/%m/%Y")} — {fin.strftime("%d/%m/%Y")}',
        'headcount': {
            'total': total_activos,
            'staff': staff_activos,
            'rco': rco_activos,
            'con_registro': trabajadores_con_registro,
        },
        'registros': total_registros,
        'he_total': he_total,
        'alertas': alertas,
    })


@login_required
@solo_admin
def cierre_dashboard(request):
    """
    Dashboard principal de Cierre de Nómina.
    Muestra historial, estado del período actual, y accesos rápidos.
    """
    from asistencia.models import ConfiguracionSistema
    hoy = date.today()

    # Calcular el período de nómina actual según ciclo (día 21 → día 20)
    config = ConfiguracionSistema.get()
    dia_corte = config.dia_corte_planilla

    # Si hoy es antes del corte, el período activo es el mes anterior
    if hoy.day <= dia_corte:
        if hoy.month == 1:
            periodo_mes, periodo_anio = 12, hoy.year - 1
        else:
            periodo_mes, periodo_anio = hoy.month - 1, hoy.year
    else:
        periodo_mes, periodo_anio = hoy.month, hoy.year

    # Período de cierre actual (puede no existir)
    periodo_actual = PeriodoCierre.objects.filter(
        anio=periodo_anio, mes=periodo_mes,
    ).prefetch_related('pasos').first()

    # Historial completo
    periodos = PeriodoCierre.objects.prefetch_related('pasos').all()

    # KPI summary
    periodos_list = list(periodos)
    total_cerrados = sum(1 for p in periodos_list if p.estado == 'CERRADO')
    periodos_anio = sum(1 for p in periodos_list if p.anio == hoy.year)
    ultimo_cierre = next(
        (p for p in sorted(periodos_list, key=lambda x: (x.anio, x.mes), reverse=True) if p.estado == 'CERRADO'),
        None,
    )

    # Calcular fechas del ciclo actual para el calendario visual
    if hoy.day > dia_corte:
        # Ciclo: día (corte+1) de este mes → día corte del mes siguiente
        ciclo_inicio = date(hoy.year, hoy.month, dia_corte + 1)
        if hoy.month == 12:
            ciclo_fin = date(hoy.year + 1, 1, dia_corte)
        else:
            ciclo_fin = date(hoy.year, hoy.month + 1, dia_corte)
    else:
        # Ciclo: día (corte+1) del mes anterior → día corte de este mes
        if hoy.month == 1:
            ciclo_inicio = date(hoy.year - 1, 12, dia_corte + 1)
        else:
            ciclo_inicio = date(hoy.year, hoy.month - 1, dia_corte + 1)
        ciclo_fin = date(hoy.year, hoy.month, dia_corte)

    # Calcular posición porcentual del día de hoy en el ciclo
    total_dias_ciclo = (ciclo_fin - ciclo_inicio).days or 1
    dias_transcurridos = min(max((hoy - ciclo_inicio).days, 0), total_dias_ciclo)
    pct_ciclo = round(dias_transcurridos / total_dias_ciclo * 100)

    MESES = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
             'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']

    dias_para_corte = (ciclo_fin - hoy).days

    context = {
        'periodos': periodos,
        'periodo_actual': periodo_actual,
        'periodo_mes': periodo_mes,
        'periodo_anio': periodo_anio,
        'periodo_mes_nombre': MESES[periodo_mes],
        'hoy': hoy,
        'dia_corte': dia_corte,
        'ciclo_inicio': ciclo_inicio,
        'ciclo_fin': ciclo_fin,
        'pct_ciclo': pct_ciclo,
        'anio_actual': hoy.year,
        'mes_actual': hoy.month,
        # KPI summary
        'total_cerrados': total_cerrados,
        'periodos_anio': periodos_anio,
        'ultimo_cierre': ultimo_cierre,
        'dias_para_corte': dias_para_corte,
    }
    return render(request, 'cierre/dashboard.html', context)


@login_required
@solo_admin
def cierre_checklist_ajax(request, pk):
    """
    AJAX (GET): Devuelve un checklist pre-cierre con ítems de validación.
    Cada ítem tiene: check, ok, detalle.
    """
    from django.db.models import Sum, Count, Q
    from asistencia.models import ConfiguracionSistema, RegistroTareo
    from personal.models import Personal

    periodo = get_object_or_404(PeriodoCierre, pk=pk)
    config = ConfiguracionSistema.get()
    inicio, fin = config.get_ciclo_asistencia(periodo.anio, periodo.mes)
    hoy = date.today()

    items = []

    # ── 1. Tareo completo ──────────────────────────────────────────────
    total_tareo = RegistroTareo.objects.filter(
        fecha__gte=inicio, fecha__lte=fin,
    ).count()
    MESES_CORTOS = ['', 'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
                    'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
    mes_label = f'{MESES_CORTOS[periodo.mes]} {periodo.anio}'
    items.append({
        'check': 'Tareo completo',
        'ok': total_tareo > 0,
        'detalle': (
            f'{total_tareo:,} registros {mes_label}'
            if total_tareo > 0
            else f'Sin registros de tareo para {mes_label} — importar primero'
        ),
    })

    # ── 2. Personal sin sueldo ─────────────────────────────────────────
    from django.db.models import Q as DQ
    sin_sueldo = Personal.objects.filter(
        estado='Activo',
    ).filter(
        DQ(sueldo_base__isnull=True) | DQ(sueldo_base=0),
    ).count()
    items.append({
        'check': 'Personal sin sueldo',
        'ok': sin_sueldo == 0,
        'detalle': (
            f'{sin_sueldo} empleado(s) activo(s) sin sueldo_base definido'
            if sin_sueldo > 0
            else 'Todos los empleados activos tienen sueldo_base'
        ),
    })

    # ── 3. HE validadas ────────────────────────────────────────────────
    he_count = RegistroTareo.objects.filter(
        fecha__gte=inicio, fecha__lte=fin,
    ).filter(
        DQ(he_25__gt=0) | DQ(he_35__gt=0) | DQ(he_100__gt=0),
    ).count()
    items.append({
        'check': 'HE validadas',
        'ok': True,  # HE puede ser 0 y es válido
        'detalle': (
            f'{he_count} registro(s) con horas extra en el período'
            if he_count > 0
            else 'Sin horas extra en el período'
        ),
    })

    # ── 4. Nómina generada ─────────────────────────────────────────────
    nomina_count = 0
    nomina_ok = False
    try:
        from nominas.models import RegistroNomina, PeriodoNomina
        periodo_nomina = PeriodoNomina.objects.filter(
            anio=periodo.anio, mes=periodo.mes,
        ).first()
        if periodo_nomina:
            nomina_count = RegistroNomina.objects.filter(
                periodo=periodo_nomina,
            ).count()
            nomina_ok = nomina_count > 0
            detalle_nomina = f'{nomina_count} registros calculados ({periodo_nomina.get_estado_display()})'
        else:
            detalle_nomina = f'Sin período de nómina para {mes_label}'
    except Exception:
        detalle_nomina = 'Módulo de nóminas no disponible'
        nomina_ok = True  # No bloquear si nóminas no está activo

    items.append({
        'check': 'Nómina generada',
        'ok': nomina_ok,
        'detalle': detalle_nomina,
    })

    # ── 5. Sin préstamos vencidos ──────────────────────────────────────
    prestamos_vencidos = 0
    try:
        from prestamos.models import CuotaPrestamo
        # CuotaPrestamo usa campo 'periodo' (DateField = primer día del mes de descuento)
        # Consideramos vencida si periodo < hoy y estado = PENDIENTE
        prestamos_vencidos = CuotaPrestamo.objects.filter(
            periodo__lt=hoy,
            estado='PENDIENTE',
        ).count()
    except Exception:
        prestamos_vencidos = 0

    items.append({
        'check': 'Sin préstamos vencidos',
        'ok': prestamos_vencidos == 0,
        'detalle': (
            f'{prestamos_vencidos} cuota(s) pendiente(s) de períodos anteriores'
            if prestamos_vencidos > 0
            else '0 cuotas vencidas sin pagar'
        ),
    })

    puede_cerrar = all(item['ok'] for item in items)

    return JsonResponse({
        'items': items,
        'puede_cerrar': puede_cerrar,
        'periodo': str(periodo),
        'rango': f'{inicio.strftime("%d/%m/%Y")} — {fin.strftime("%d/%m/%Y")}',
    })


@login_required
@solo_admin
def cierre_validar(request, pk):
    """
    AJAX (GET): Valida un período antes de finalizar el cierre.
    Compara headcount vs nómina, detecta neto negativo y sueldo cero.
    """
    from django.db.models import Sum, Count, Q as DQ
    from personal.models import Personal
    from asistencia.models import RegistroTareo, ConfiguracionSistema

    periodo = get_object_or_404(PeriodoCierre, pk=pk)
    config = ConfiguracionSistema.get()
    inicio, fin = config.get_ciclo_asistencia(periodo.anio, periodo.mes)

    errores = []
    advertencias = []

    # ── Headcount ─────────────────────────────────────────────────────
    total_activos = Personal.objects.filter(estado='Activo').count()

    # ── Nómina ────────────────────────────────────────────────────────
    nomina_count = 0
    neto_negativo = 0
    sueldo_cero_nomina = 0
    nomina_disponible = False

    try:
        from nominas.models import RegistroNomina, PeriodoNomina
        periodo_nomina = PeriodoNomina.objects.filter(
            anio=periodo.anio, mes=periodo.mes,
        ).first()

        if periodo_nomina:
            nomina_disponible = True
            qs_nomina = RegistroNomina.objects.filter(periodo=periodo_nomina)
            nomina_count = qs_nomina.count()

            neto_negativo = qs_nomina.filter(neto_a_pagar__lt=0).count()
            sueldo_cero_nomina = qs_nomina.filter(sueldo_base=0).count()

            diferencia = total_activos - nomina_count
            if diferencia > 0:
                advertencias.append(
                    f'{diferencia} empleado(s) activo(s) sin registro en nómina '
                    f'({total_activos} activos vs {nomina_count} en nómina)'
                )
            elif diferencia < 0:
                advertencias.append(
                    f'La nómina tiene {abs(diferencia)} registro(s) más que empleados activos '
                    f'(posible baja no procesada)'
                )

            if neto_negativo > 0:
                errores.append(
                    f'{neto_negativo} registro(s) con neto_a_pagar negativo — revisar descuentos'
                )

            if sueldo_cero_nomina > 0:
                advertencias.append(
                    f'{sueldo_cero_nomina} registro(s) en nómina con sueldo_base = 0'
                )
        else:
            advertencias.append(f'Sin período de nómina generado para {periodo.mes_nombre} {periodo.anio}')
    except Exception as exc:
        advertencias.append(f'Módulo nóminas no disponible: {exc}')

    # ── Personal sin sueldo ───────────────────────────────────────────
    from django.db.models import Q
    sin_sueldo_activos = Personal.objects.filter(
        estado='Activo',
    ).filter(
        Q(sueldo_base__isnull=True) | Q(sueldo_base=0),
    ).count()

    if sin_sueldo_activos > 0:
        advertencias.append(
            f'{sin_sueldo_activos} empleado(s) activo(s) sin sueldo_base — no aparecerán en nómina'
        )

    # ── Tareo ─────────────────────────────────────────────────────────
    sin_tareo = RegistroTareo.objects.filter(
        fecha__gte=inicio, fecha__lte=fin, personal__isnull=True,
    ).count()
    if sin_tareo > 0:
        advertencias.append(
            f'{sin_tareo} registro(s) de tareo sin empleado vinculado (DNI no reconocido)'
        )

    puede_cerrar = len(errores) == 0

    return JsonResponse({
        'ok': True,
        'puede_cerrar': puede_cerrar,
        'errores': errores,
        'advertencias': advertencias,
        'resumen': {
            'activos': total_activos,
            'en_nomina': nomina_count,
            'neto_negativo': neto_negativo,
            'sueldo_cero_nomina': sueldo_cero_nomina,
            'sin_sueldo_activos': sin_sueldo_activos,
            'sin_tareo': sin_tareo,
            'nomina_disponible': nomina_disponible,
        },
        'periodo': str(periodo),
    })


@login_required
@solo_admin
def cierre_rezagos(request, pk):
    """
    Reporte post-cierre: muestra registros que caen después del corte de planilla
    (día corte+1 hasta fin de mes) del período cerrado.

    Estos "rezagos" son eventos que pertenecen al mes calendario del período
    pero se liquidan en la planilla del MES SIGUIENTE.

    Incluye: faltas, ausencias, papeletas, HE pendientes de ese rango.
    """
    from django.db.models import Sum, Count, Q
    from asistencia.models import ConfiguracionSistema, RegistroTareo, RegistroPapeleta

    periodo = get_object_or_404(PeriodoCierre, pk=pk)
    config = ConfiguracionSistema.get()
    corte = config.dia_corte_planilla

    # Rango de rezagos: día (corte+1) hasta fin de mes
    ultimo_dia = calendar.monthrange(periodo.anio, periodo.mes)[1]

    if corte >= ultimo_dia:
        # No hay rezagos si el corte es el último día del mes
        return render(request, 'cierre/rezagos.html', {
            'periodo': periodo,
            'sin_rezagos': True,
            'corte': corte,
        })

    fecha_inicio = date(periodo.anio, periodo.mes, corte + 1)
    fecha_fin = date(periodo.anio, periodo.mes, ultimo_dia)

    # ── Registros de asistencia en el rango ──
    registros = RegistroTareo.objects.filter(
        fecha__gte=fecha_inicio,
        fecha__lte=fecha_fin,
    ).select_related('personal')

    resumen = registros.aggregate(
        total=Count('id'),
        faltas=Count('id', filter=Q(codigo_dia='FA')),
        ss=Count('id', filter=Q(codigo_dia='SS')),
        trabajados=Count('id', filter=Q(codigo_dia__in=['T', 'NOR', 'TR'])),
        he25=Sum('he_25'),
        he35=Sum('he_35'),
        he100=Sum('he_100'),
    )

    he_total = (resumen['he25'] or 0) + (resumen['he35'] or 0) + (resumen['he100'] or 0)

    # Detalle de faltas y anomalías
    faltas_detalle = registros.filter(
        codigo_dia__in=['FA', 'SS', 'LSG', 'DM'],
    ).order_by('fecha', 'personal__apellidos_nombres').values(
        'personal__apellidos_nombres',
        'personal__nro_doc',
        'fecha',
        'codigo_dia',
        'observaciones',
    )[:50]

    # ── Papeletas que cubren fechas en el rango ──
    papeletas = RegistroPapeleta.objects.filter(
        fecha_inicio__lte=fecha_fin,
        fecha_fin__gte=fecha_inicio,
    ).select_related('personal').order_by('-fecha_inicio')[:50]

    # ── HE detalle por trabajador en el rango ──
    from django.db.models import F
    he_detalle_qs = registros.filter(
        Q(he_25__gt=0) | Q(he_35__gt=0) | Q(he_100__gt=0),
    ).values(
        'personal__apellidos_nombres',
        'personal__grupo_tareo',
    ).annotate(
        sum_he25=Sum('he_25'),
        sum_he35=Sum('he_35'),
        sum_he100=Sum('he_100'),
    ).order_by('-sum_he25', '-sum_he35', '-sum_he100')[:30]
    # Add total per row (Decimal-safe)
    he_detalle = []
    for h in he_detalle_qs:
        h['sum_total'] = (h['sum_he25'] or 0) + (h['sum_he35'] or 0) + (h['sum_he100'] or 0)
        he_detalle.append(h)

    # Calcular siguiente período para referencia
    if periodo.mes == 12:
        sig_mes, sig_anio = 1, periodo.anio + 1
    else:
        sig_mes, sig_anio = periodo.mes + 1, periodo.anio

    context = {
        'periodo': periodo,
        'config': config,
        'corte': corte,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'resumen': resumen,
        'he_total': he_total,
        'faltas_detalle': faltas_detalle,
        'papeletas': papeletas,
        'he_detalle': he_detalle,
        'sig_mes': sig_mes,
        'sig_anio': sig_anio,
        'sin_rezagos': False,
    }
    return render(request, 'cierre/rezagos.html', context)
