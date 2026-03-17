"""
Billing Views — Dashboard de facturación, pagos y cambio de plan.

Para usuarios normales (no admin). Cada empresa ve su propia suscripción.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from .models import Empresa
from .models_billing import HistorialPago, Plan, Suscripcion


@login_required
def billing_dashboard(request):
    """
    Dashboard de billing para la empresa actual.

    Muestra: plan activo, uso de empleados, estado de suscripción,
    historial de pagos recientes.
    """
    empresa = getattr(request, 'empresa_actual', None)
    suscripcion = None
    pagos = []
    planes = Plan.objects.filter(activo=True)

    if empresa:
        try:
            suscripcion = Suscripcion.objects.select_related('plan').get(
                empresa=empresa,
            )
            pagos = HistorialPago.objects.filter(
                suscripcion=suscripcion,
            ).order_by('-fecha_pago')[:10]
        except Suscripcion.DoesNotExist:
            pass

    return render(request, 'empresas/billing/dashboard.html', {
        'titulo': 'Facturación',
        'empresa': empresa,
        'suscripcion': suscripcion,
        'pagos': pagos,
        'planes': planes,
    })


@login_required
def billing_upgrade(request):
    """
    Cambiar de plan / upgrade / downgrade.
    """
    empresa = getattr(request, 'empresa_actual', None)
    if not empresa:
        messages.error(request, 'No hay empresa seleccionada.')
        return redirect('billing_dashboard')

    planes = Plan.objects.filter(activo=True)

    try:
        suscripcion = Suscripcion.objects.select_related('plan').get(
            empresa=empresa,
        )
    except Suscripcion.DoesNotExist:
        suscripcion = None

    if request.method == 'POST':
        plan_id = request.POST.get('plan_id')
        ciclo = request.POST.get('ciclo', 'MENSUAL')

        try:
            nuevo_plan = Plan.objects.get(pk=plan_id, activo=True)
        except Plan.DoesNotExist:
            messages.error(request, 'Plan no encontrado.')
            return redirect('billing_upgrade')

        if suscripcion:
            suscripcion.plan = nuevo_plan
            suscripcion.ciclo = ciclo
            if suscripcion.estado == 'TRIAL':
                suscripcion.estado = 'ACTIVA'
                suscripcion.fecha_inicio = date.today()
            suscripcion.save()
            messages.success(
                request,
                f'Plan actualizado a {nuevo_plan.nombre}.',
            )
        else:
            # Create new subscription
            if ciclo == 'ANUAL':
                proximo_pago = date.today() + timedelta(days=365)
            else:
                proximo_pago = date.today() + timedelta(days=30)

            Suscripcion.objects.create(
                empresa=empresa,
                plan=nuevo_plan,
                estado='ACTIVA',
                ciclo=ciclo,
                fecha_inicio=date.today(),
                proximo_pago=proximo_pago,
                creado_por=request.user,
            )
            messages.success(
                request,
                f'Suscripción creada con plan {nuevo_plan.nombre}.',
            )

        return redirect('billing_dashboard')

    return render(request, 'empresas/billing/upgrade.html', {
        'titulo': 'Cambiar plan',
        'planes': planes,
        'suscripcion': suscripcion,
    })


@login_required
def billing_payment(request):
    """
    Registrar un pago manual (Yape, Plin, transferencia).
    """
    empresa = getattr(request, 'empresa_actual', None)
    if not empresa:
        messages.error(request, 'No hay empresa seleccionada.')
        return redirect('billing_dashboard')

    try:
        suscripcion = Suscripcion.objects.select_related('plan').get(
            empresa=empresa,
        )
    except Suscripcion.DoesNotExist:
        messages.error(request, 'No tiene una suscripción activa.')
        return redirect('billing_upgrade')

    if request.method == 'POST':
        metodo = request.POST.get('metodo_pago', 'YAPE')
        referencia = request.POST.get('referencia', '').strip()
        comprobante = request.FILES.get('comprobante')
        notas = request.POST.get('notas', '').strip()

        monto = suscripcion.monto_periodo

        # Calculate period
        periodo_desde = date.today()
        if suscripcion.ciclo == 'ANUAL':
            periodo_hasta = periodo_desde + timedelta(days=365)
        else:
            periodo_hasta = periodo_desde + timedelta(days=30)

        pago = HistorialPago.objects.create(
            suscripcion=suscripcion,
            monto=monto,
            fecha_pago=date.today(),
            fecha_vencimiento=periodo_hasta,
            metodo_pago=metodo,
            referencia=referencia,
            comprobante=comprobante,
            estado='PENDIENTE',
            periodo_desde=periodo_desde,
            periodo_hasta=periodo_hasta,
            notas=notas,
            registrado_por=request.user,
        )

        messages.success(
            request,
            f'Pago de S/ {monto} registrado. '
            f'Será validado por el administrador.',
        )
        return redirect('billing_dashboard')

    return render(request, 'empresas/billing/payment.html', {
        'titulo': 'Registrar pago',
        'suscripcion': suscripcion,
    })


@login_required
def billing_invoice(request, pago_id):
    """
    Generar / ver comprobante de pago (boleta/factura).
    """
    empresa = getattr(request, 'empresa_actual', None)
    pago = get_object_or_404(
        HistorialPago.objects.select_related('suscripcion__empresa', 'suscripcion__plan'),
        pk=pago_id,
    )

    # Security: only allow viewing own company's payments (or superuser)
    if not request.user.is_superuser:
        if empresa and pago.suscripcion.empresa_id != empresa.pk:
            messages.error(request, 'No tiene permiso para ver este comprobante.')
            return redirect('billing_dashboard')

    return render(request, 'empresas/billing/invoice.html', {
        'titulo': f'Comprobante #{pago.pk}',
        'pago': pago,
        'empresa': pago.suscripcion.empresa,
    })
