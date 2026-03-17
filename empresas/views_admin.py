"""
Super-admin billing dashboard — Vista global de tenants, revenue y acciones rápidas.

Solo accesible para superusers.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Q, Sum, F
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import Empresa
from .models_billing import HistorialPago, Plan, Suscripcion

solo_admin = user_passes_test(lambda u: u.is_superuser)


@login_required
@solo_admin
def admin_billing_dashboard(request):
    """
    Dashboard super-admin: lista de tenants con métricas de revenue.
    """
    # All subscriptions with related data
    suscripciones = (
        Suscripcion.objects
        .select_related('empresa', 'plan')
        .order_by('-creado_en')
    )

    # Empresas without subscription
    empresas_sin_sub = Empresa.objects.filter(
        activa=True,
    ).exclude(
        pk__in=suscripciones.values_list('empresa_id', flat=True),
    )

    # Revenue metrics
    hoy = date.today()
    primer_dia_mes = hoy.replace(day=1)

    pagos_mes = HistorialPago.objects.filter(
        estado='PAGADO',
        fecha_pago__gte=primer_dia_mes,
        fecha_pago__lte=hoy,
    )
    mrr = pagos_mes.aggregate(total=Sum('monto'))['total'] or Decimal('0')

    # Counts by status
    stats = {
        'total_empresas': Empresa.objects.filter(activa=True).count(),
        'total_suscripciones': suscripciones.count(),
        'activas': suscripciones.filter(estado='ACTIVA').count(),
        'trial': suscripciones.filter(estado='TRIAL').count(),
        'suspendidas': suscripciones.filter(estado='SUSPENDIDA').count(),
        'canceladas': suscripciones.filter(estado='CANCELADA').count(),
        'sin_suscripcion': empresas_sin_sub.count(),
        'mrr': mrr,
    }

    # Pagos pendientes de validación
    pagos_pendientes = (
        HistorialPago.objects
        .filter(estado='PENDIENTE')
        .select_related('suscripcion__empresa', 'suscripcion__plan')
        .order_by('-fecha_pago')[:20]
    )

    # Filter by estado if requested
    estado_filter = request.GET.get('estado', '')
    if estado_filter:
        suscripciones = suscripciones.filter(estado=estado_filter)

    return render(request, 'empresas/billing/admin_dashboard.html', {
        'titulo': 'Billing — Super Admin',
        'suscripciones': suscripciones,
        'empresas_sin_sub': empresas_sin_sub,
        'stats': stats,
        'pagos_pendientes': pagos_pendientes,
        'estado_filter': estado_filter,
    })


@login_required
@solo_admin
@require_POST
def admin_billing_action(request):
    """
    Acciones rápidas sobre suscripciones:
    - extend_trial: extender trial N días
    - activate: activar suscripción
    - suspend: suspender suscripción
    - cancel: cancelar suscripción
    - approve_payment: aprobar un pago pendiente
    """
    action = request.POST.get('action')
    suscripcion_id = request.POST.get('suscripcion_id')
    pago_id = request.POST.get('pago_id')

    if action == 'approve_payment' and pago_id:
        pago = get_object_or_404(HistorialPago, pk=pago_id)
        pago.estado = 'PAGADO'
        pago.save()

        # Activate subscription if suspended or trial
        sub = pago.suscripcion
        if sub.estado in ('SUSPENDIDA', 'TRIAL'):
            sub.estado = 'ACTIVA'
        # Update next payment date
        if pago.periodo_hasta:
            sub.proximo_pago = pago.periodo_hasta
        sub.save()

        messages.success(
            request,
            f'Pago #{pago.pk} aprobado. Suscripción de '
            f'{sub.empresa.nombre_display} activada.',
        )
        return redirect('admin_billing_dashboard')

    if action == 'reject_payment' and pago_id:
        pago = get_object_or_404(HistorialPago, pk=pago_id)
        pago.estado = 'ANULADO'
        pago.save()
        messages.warning(
            request,
            f'Pago #{pago.pk} rechazado.',
        )
        return redirect('admin_billing_dashboard')

    if not suscripcion_id:
        messages.error(request, 'Suscripción no especificada.')
        return redirect('admin_billing_dashboard')

    suscripcion = get_object_or_404(
        Suscripcion.objects.select_related('empresa'),
        pk=suscripcion_id,
    )

    if action == 'extend_trial':
        dias = int(request.POST.get('dias', 7))
        suscripcion.dias_trial += dias
        suscripcion.save()
        messages.success(
            request,
            f'Trial de {suscripcion.empresa.nombre_display} '
            f'extendido {dias} días (total: {suscripcion.dias_trial} días).',
        )

    elif action == 'activate':
        suscripcion.estado = 'ACTIVA'
        suscripcion.save()
        messages.success(
            request,
            f'Suscripción de {suscripcion.empresa.nombre_display} activada.',
        )

    elif action == 'suspend':
        suscripcion.estado = 'SUSPENDIDA'
        suscripcion.save()
        messages.warning(
            request,
            f'Suscripción de {suscripcion.empresa.nombre_display} suspendida.',
        )

    elif action == 'cancel':
        suscripcion.estado = 'CANCELADA'
        suscripcion.fecha_fin = date.today()
        suscripcion.save()
        messages.error(
            request,
            f'Suscripción de {suscripcion.empresa.nombre_display} cancelada.',
        )

    elif action == 'change_plan':
        plan_id = request.POST.get('plan_id')
        try:
            plan = Plan.objects.get(pk=plan_id, activo=True)
            suscripcion.plan = plan
            suscripcion.save()
            messages.success(
                request,
                f'Plan de {suscripcion.empresa.nombre_display} '
                f'cambiado a {plan.nombre}.',
            )
        except Plan.DoesNotExist:
            messages.error(request, 'Plan no encontrado.')

    else:
        messages.error(request, f'Acción desconocida: {action}')

    return redirect('admin_billing_dashboard')
