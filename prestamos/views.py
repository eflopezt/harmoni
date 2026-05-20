"""
Vistas del módulo de Préstamos al Personal.
"""
import json
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Sum, Count
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect

from personal.models import Personal
from .models import TipoPrestamo, Prestamo, CuotaPrestamo

solo_admin = user_passes_test(lambda u: u.is_superuser, login_url='login')


@login_required
@solo_admin
def prestamos_panel(request):
    """Panel principal de préstamos."""
    qs = Prestamo.objects.select_related('personal', 'tipo').all()

    # Filtros
    estado = request.GET.get('estado', '')
    tipo_id = request.GET.get('tipo', '')
    buscar = request.GET.get('q', '')

    if estado:
        qs = qs.filter(estado=estado)
    if tipo_id:
        qs = qs.filter(tipo_id=tipo_id)
    if buscar:
        qs = qs.filter(
            Q(personal__apellidos_nombres__icontains=buscar) |
            Q(personal__nro_doc__icontains=buscar)
        )

    # Stats
    hoy = date.today()
    en_curso = Prestamo.objects.filter(estado='EN_CURSO')
    total_por_cobrar = sum(p.saldo_pendiente for p in en_curso)
    descuento_mes = CuotaPrestamo.objects.filter(
        estado='PENDIENTE',
        periodo__year=hoy.year,
        periodo__month=hoy.month,
    ).aggregate(t=Sum('monto'))['t'] or Decimal('0.00')

    # Estado de cuenta por empleado — empleados con préstamos EN_CURSO
    empleados_con_deuda = (
        Prestamo.objects
        .filter(estado='EN_CURSO')
        .values('personal__pk', 'personal__apellidos_nombres', 'personal__nro_doc')
        .annotate(num_prestamos=Count('pk'))
        .order_by('personal__apellidos_nombres')
    )
    resumen_empleados = []
    for emp in empleados_con_deuda:
        prestamos_emp = Prestamo.objects.filter(
            personal_id=emp['personal__pk'], estado='EN_CURSO'
        )
        total_prestado = prestamos_emp.aggregate(
            t=Sum('monto_solicitado')
        )['t'] or Decimal('0.00')
        amortizado = CuotaPrestamo.objects.filter(
            prestamo__personal_id=emp['personal__pk'],
            estado='PAGADO',
        ).aggregate(t=Sum('monto_pagado'))['t'] or Decimal('0.00')
        saldo = sum(p.saldo_pendiente for p in prestamos_emp)
        resumen_empleados.append({
            'pk': emp['personal__pk'],
            'nombre': emp['personal__apellidos_nombres'],
            'nro_doc': emp['personal__nro_doc'],
            'num_prestamos': emp['num_prestamos'],
            'total_prestado': total_prestado,
            'amortizado': amortizado,
            'saldo': saldo,
        })

    # ── Analytics: resumen por estado ───────────────────────────────────────
    resumen_estados = {}
    try:
        for row in (
            Prestamo.objects
            .values('estado')
            .annotate(total=Count('pk'))
        ):
            resumen_estados[row['estado']] = row['total']
    except Exception:
        resumen_estados = {}

    # ── Analytics: monto total pendiente de préstamos EN_CURSO ──────────────
    monto_total_pendiente = Decimal('0.00')
    try:
        monto_total_pendiente = sum(
            p.saldo_pendiente for p in Prestamo.objects.filter(estado='EN_CURSO')
        )
    except Exception:
        monto_total_pendiente = Decimal('0.00')

    # ── Analytics: cuotas pendientes del mes agrupadas por semana ───────────
    cuotas_mes_json = '[]'
    try:
        cuotas_mes = CuotaPrestamo.objects.filter(
            periodo__year=hoy.year,
            periodo__month=hoy.month,
        ).values('estado', 'periodo__day', 'monto')

        # Distribuir en S1–S4 según día del período
        semanas = {
            'S1 (1–7)': Decimal('0.00'),
            'S2 (8–15)': Decimal('0.00'),
            'S3 (16–22)': Decimal('0.00'),
            'S4 (23+)': Decimal('0.00'),
        }
        semanas_pagadas = {
            'S1 (1–7)': Decimal('0.00'),
            'S2 (8–15)': Decimal('0.00'),
            'S3 (16–22)': Decimal('0.00'),
            'S4 (23+)': Decimal('0.00'),
        }

        def _semana(dia):
            if dia <= 7:
                return 'S1 (1–7)'
            elif dia <= 15:
                return 'S2 (8–15)'
            elif dia <= 22:
                return 'S3 (16–22)'
            else:
                return 'S4 (23+)'

        for c in cuotas_mes:
            llave = _semana(c['periodo__day'])
            monto = c['monto'] or Decimal('0.00')
            if c['estado'] == 'PAGADO':
                semanas_pagadas[llave] += monto
            else:
                semanas[llave] += monto

        labels = list(semanas.keys())
        cuotas_mes_json = json.dumps([
            {
                'label': lbl,
                'pendiente': float(semanas[lbl]),
                'pagado': float(semanas_pagadas[lbl]),
            }
            for lbl in labels
        ])
    except Exception:
        cuotas_mes_json = '[]'

    # ── Analytics: top 5 préstamos activos por monto ────────────────────────
    top_prestamos = []
    try:
        top_prestamos = list(
            Prestamo.objects
            .filter(estado='EN_CURSO')
            .select_related('personal')
            .order_by(
                Coalesce('monto_aprobado', 'monto_solicitado').desc()
            )[:5]
        )
    except Exception:
        top_prestamos = []

    # ── KPI strip ────────────────────────────────────────────────────────────
    kpi_prestamos_activos = 0
    try:
        kpi_prestamos_activos = Prestamo.objects.filter(estado='EN_CURSO').count()
    except Exception:
        kpi_prestamos_activos = 0

    kpi_monto_pendiente = Decimal('0.00')
    try:
        kpi_monto_pendiente = sum(
            p.saldo_pendiente for p in Prestamo.objects.filter(estado='EN_CURSO')
        )
    except Exception:
        kpi_monto_pendiente = Decimal('0.00')

    kpi_cuotas_vencidas = 0
    try:
        # Cuotas pendientes cuyo periodo es anterior al mes actual (ya debieron descontarse)
        kpi_cuotas_vencidas = CuotaPrestamo.objects.filter(
            estado='PENDIENTE',
            periodo__lt=hoy.replace(day=1),
        ).count()
    except Exception:
        kpi_cuotas_vencidas = 0

    kpi_desembolsado_mes = Decimal('0.00')
    try:
        kpi_desembolsado_mes = (
            Prestamo.objects
            .filter(
                estado='EN_CURSO',
                fecha_aprobacion__year=hoy.year,
                fecha_aprobacion__month=hoy.month,
            )
            .aggregate(t=Sum(Coalesce('monto_aprobado', 'monto_solicitado')))['t']
        ) or Decimal('0.00')
    except Exception:
        kpi_desembolsado_mes = Decimal('0.00')

    context = {
        'titulo': 'Préstamos al Personal',
        'prestamos': qs[:100],
        'total': qs.count(),
        'filtro_estado': estado,
        'filtro_tipo': tipo_id,
        'buscar': buscar,
        'tipos': TipoPrestamo.objects.filter(activo=True),
        'stats': {
            'en_curso': en_curso.count(),
            'total_por_cobrar': total_por_cobrar,
            'descuento_mes': descuento_mes,
            'pendientes_aprobacion': Prestamo.objects.filter(estado='PENDIENTE').count(),
        },
        'resumen_empleados': resumen_empleados,
        # Analytics
        'resumen_estados': resumen_estados,
        'monto_total_pendiente': monto_total_pendiente,
        'cuotas_mes_json': cuotas_mes_json,
        'top_prestamos': top_prestamos,
        # KPI strip
        'kpi_prestamos_activos': kpi_prestamos_activos,
        'kpi_monto_pendiente': kpi_monto_pendiente,
        'kpi_cuotas_vencidas': kpi_cuotas_vencidas,
        'kpi_desembolsado_mes': kpi_desembolsado_mes,
    }
    return render(request, 'prestamos/panel.html', context)


@login_required
@solo_admin
def prestamo_crear(request):
    """Crear nuevo préstamo."""
    tipos = TipoPrestamo.objects.filter(activo=True)

    if request.method == 'POST':
        try:
            personal = get_object_or_404(Personal, pk=request.POST['personal_id'])
            tipo = get_object_or_404(TipoPrestamo, pk=request.POST['tipo_id'])
            monto = Decimal(request.POST['monto'])
            cuotas = int(request.POST['num_cuotas'])
            motivo = request.POST.get('motivo', '')
            fecha_descuento = request.POST.get('fecha_descuento', '')

            # Validaciones
            if tipo.monto_maximo and monto > tipo.monto_maximo:
                messages.error(request, f'El monto excede el máximo permitido (S/ {tipo.monto_maximo})')
                return redirect('prestamo_crear')
            if cuotas > tipo.max_cuotas:
                messages.error(request, f'Máximo {tipo.max_cuotas} cuotas para {tipo.nombre}')
                return redirect('prestamo_crear')

            prestamo = Prestamo.objects.create(
                personal=personal,
                tipo=tipo,
                monto_solicitado=monto,
                num_cuotas=cuotas,
                motivo=motivo,
                solicitado_por=request.user,
                estado='PENDIENTE' if tipo.requiere_aprobacion else 'BORRADOR',
            )
            if fecha_descuento:
                prestamo.fecha_primer_descuento = date.fromisoformat(fecha_descuento)
                prestamo.save(update_fields=['fecha_primer_descuento'])

            # Auto-aprobar si no requiere aprobación
            if not tipo.requiere_aprobacion:
                prestamo.aprobar(request.user)

            from core.audit import log_create
            log_create(request, prestamo, f'Préstamo {tipo.nombre} por S/ {monto} para {personal.apellidos_nombres}')

            messages.success(request, f'Préstamo registrado: {tipo.nombre} — S/ {monto}')
            return redirect('prestamo_detalle', pk=prestamo.pk)
        except (ValueError, KeyError) as e:
            messages.error(request, f'Error en los datos: {e}')

    context = {
        'titulo': 'Nuevo Préstamo',
        'tipos': tipos,
        'personal_list': Personal.objects.filter(estado='Activo').order_by('apellidos_nombres'),
    }
    return render(request, 'prestamos/crear.html', context)


@login_required
@solo_admin
def prestamo_detalle(request, pk):
    """Detalle de un préstamo con sus cuotas."""
    prestamo = get_object_or_404(
        Prestamo.objects.select_related('personal', 'tipo', 'solicitado_por', 'aprobado_por'),
        pk=pk
    )
    cuotas = prestamo.cuotas.all()

    # Última cuota pagada
    ultima_pagada = prestamo.cuotas.filter(estado='PAGADO').order_by('-numero').first()
    # Próxima cuota a vencer (primera PENDIENTE en orden de período)
    proxima_vencer = prestamo.cuotas.filter(estado='PENDIENTE').order_by('periodo').first()

    # Estado de cuenta del empleado (año en curso)
    hoy = date.today()
    prestamos_empleado = Prestamo.objects.filter(
        personal=prestamo.personal,
        fecha_solicitud__year=hoy.year,
    ).exclude(estado='CANCELADO')
    total_prestado_anio = prestamos_empleado.aggregate(
        t=Sum('monto_solicitado')
    )['t'] or Decimal('0.00')
    total_amortizado = CuotaPrestamo.objects.filter(
        prestamo__personal=prestamo.personal,
        estado='PAGADO',
        fecha_pago__year=hoy.year,
    ).aggregate(t=Sum('monto_pagado'))['t'] or Decimal('0.00')
    saldo_total_empleado = sum(
        p.saldo_pendiente
        for p in Prestamo.objects.filter(personal=prestamo.personal, estado='EN_CURSO')
    )

    context = {
        'titulo': f'Préstamo #{prestamo.pk}',
        'p': prestamo,
        'cuotas': cuotas,
        'today': hoy,
        'ultima_pagada': ultima_pagada,
        'proxima_vencer': proxima_vencer,
        'cuenta_empleado': {
            'total_prestado_anio': total_prestado_anio,
            'total_amortizado': total_amortizado,
            'saldo_total': saldo_total_empleado,
        },
    }
    return render(request, 'prestamos/detalle.html', context)


@login_required
@solo_admin
def prestamo_aprobar(request, pk):
    """Aprobar un préstamo pendiente."""
    prestamo = get_object_or_404(Prestamo, pk=pk)

    if request.method == 'POST' and prestamo.estado in ('BORRADOR', 'PENDIENTE'):
        monto = request.POST.get('monto_aprobado')
        fecha_desc = request.POST.get('fecha_descuento')
        monto_aprobado = Decimal(monto) if monto else None
        fecha_descuento = date.fromisoformat(fecha_desc) if fecha_desc else None

        prestamo.aprobar(request.user, monto_aprobado, fecha_descuento)

        from core.audit import log_update
        log_update(request, prestamo, {'estado': {'old': 'PENDIENTE', 'new': 'EN_CURSO'}},
                   f'Préstamo aprobado: S/ {prestamo.monto_aprobado}')

        messages.success(request, f'Préstamo aprobado — {prestamo.num_cuotas} cuotas de S/ {prestamo.cuota_mensual}')
    return redirect('prestamo_detalle', pk=pk)


@login_required
@solo_admin
def prestamo_cancelar(request, pk):
    """Cancelar un préstamo."""
    prestamo = get_object_or_404(Prestamo, pk=pk)
    if request.method == 'POST' and prestamo.estado not in ('PAGADO', 'CANCELADO'):
        estado_ant = prestamo.estado
        prestamo.estado = 'CANCELADO'
        prestamo.save(update_fields=['estado'])

        from core.audit import log_update
        log_update(request, prestamo, {'estado': {'old': estado_ant, 'new': 'CANCELADO'}},
                   f'Préstamo cancelado: {prestamo.tipo.nombre} — {prestamo.personal.apellidos_nombres}')

        messages.warning(request, 'Préstamo cancelado.')
    return redirect('prestamo_detalle', pk=pk)


@login_required
@solo_admin
def cuota_pagar(request, pk):
    """Registrar pago de una cuota (AJAX)."""
    cuota = get_object_or_404(CuotaPrestamo.objects.select_related('prestamo'), pk=pk)
    if request.method == 'POST' and cuota.estado == 'PENDIENTE':
        cuota.registrar_pago()

        from core.audit import log_update
        log_update(request, cuota.prestamo,
                   {'cuota_pagada': {'old': f'Cuota {cuota.numero} pendiente', 'new': f'Cuota {cuota.numero} pagada'}},
                   f'Cuota #{cuota.numero} pagada — S/ {cuota.monto} — {cuota.prestamo.personal.apellidos_nombres}')

        return JsonResponse({
            'ok': True,
            'cuota_id': cuota.pk,
            'estado': cuota.get_estado_display(),
            'prestamo_estado': cuota.prestamo.get_estado_display(),
            'saldo': str(cuota.prestamo.saldo_pendiente),
            'avance': cuota.prestamo.porcentaje_avance,
        })
    return JsonResponse({'ok': False, 'error': 'No se puede pagar esta cuota'})


# ── Portal del trabajador ──
@login_required
def mis_prestamos(request):
    """Vista del portal: mis préstamos."""
    from portal.views import _get_empleado
    empleado = _get_empleado(request.user)

    prestamos = []
    if empleado:
        prestamos = Prestamo.objects.filter(
            personal=empleado
        ).select_related('tipo').exclude(estado='CANCELADO')

    context = {
        'titulo': 'Mis Préstamos',
        'empleado': empleado,
        'prestamos': prestamos,
    }
    return render(request, 'prestamos/mis_prestamos.html', context)
