"""Descuentos por planilla — vistas admin + portal trabajador."""
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from .forms import DescuentoPlanillaForm
from .models import DescuentoPlanilla, AplicacionDescuento


def _is_admin(user):
    return user.is_authenticated and (user.is_superuser or user.is_staff)


# ── Admin views ─────────────────────────────────────────────────────────

@login_required
def panel(request):
    """Lista todos los descuentos con filtros."""
    if not _is_admin(request.user):
        return HttpResponseForbidden('Solo administradores.')

    qs = DescuentoPlanilla.objects.select_related(
        'personal', 'personal__subarea', 'personal__subarea__area',
    )

    estado = request.GET.get('estado', '')
    causal = request.GET.get('causal', '')
    if estado:
        qs = qs.filter(estado=estado)
    if causal:
        qs = qs.filter(causal=causal)

    # KPIs
    total = qs.count()
    en_curso = qs.filter(estado__in=['APROBADO', 'EN_CURSO']).count()
    pendientes = qs.filter(estado='PENDIENTE').count()
    saldo_total = DescuentoPlanilla.objects.filter(
        estado__in=['APROBADO', 'EN_CURSO'],
    ).aggregate(s=Sum('monto_total'))['s'] or Decimal('0')

    # Causales más frecuentes para filtro rápido
    causales = (
        DescuentoPlanilla.objects.values('causal')
        .annotate(c=Count('id'))
        .order_by('-c')
    )

    return render(request, 'descuentos/panel.html', {
        'descuentos': qs[:200],
        'total': total,
        'en_curso': en_curso,
        'pendientes': pendientes,
        'saldo_total': saldo_total,
        'causales': causales,
        'filtro_estado': estado,
        'filtro_causal': causal,
        'estado_choices': DescuentoPlanilla.ESTADO_CHOICES,
        'causal_choices': DescuentoPlanilla.CAUSAL_CHOICES,
    })


@login_required
def crear(request):
    if not _is_admin(request.user):
        return HttpResponseForbidden()

    if request.method == 'POST':
        form = DescuentoPlanillaForm(request.POST, request.FILES)
        if form.is_valid():
            d = form.save(commit=False)
            d.solicitado_por = request.user
            d.save()
            messages.success(
                request,
                f'Descuento creado para {d.personal} (S/ {d.monto_total} en {d.num_cuotas} cuota{"s" if d.num_cuotas > 1 else ""}).',
            )
            return redirect('descuentos_detalle', pk=d.pk)
    else:
        form = DescuentoPlanillaForm()

    return render(request, 'descuentos/form.html', {
        'form': form, 'titulo': 'Nuevo Descuento',
    })


@login_required
def detalle(request, pk):
    if not _is_admin(request.user):
        return HttpResponseForbidden()
    d = get_object_or_404(
        DescuentoPlanilla.objects.select_related('personal'),
        pk=pk,
    )
    aplicaciones = d.aplicaciones.select_related('registro_nomina').order_by(
        '-periodo_anio', '-periodo_mes',
    )
    return render(request, 'descuentos/detalle.html', {
        'descuento': d,
        'aplicaciones': aplicaciones,
    })


@login_required
@require_POST
def aprobar(request, pk):
    if not _is_admin(request.user):
        return HttpResponseForbidden()
    d = get_object_or_404(DescuentoPlanilla, pk=pk)
    if d.estado != 'PENDIENTE':
        messages.warning(request, 'Solo se pueden aprobar descuentos pendientes.')
        return redirect('descuentos_detalle', pk=pk)

    d.estado = 'APROBADO'
    d.aprobado_por = request.user
    d.fecha_aprobacion = date.today()
    if not d.fecha_inicio_descuento:
        # Por defecto el siguiente período
        hoy = date.today()
        # Si estamos pasado el 15, ir al siguiente mes
        if hoy.day > 15:
            mes = (hoy.month % 12) + 1
            anio = hoy.year + (1 if hoy.month == 12 else 0)
            d.fecha_inicio_descuento = date(anio, mes, 1)
        else:
            d.fecha_inicio_descuento = date(hoy.year, hoy.month, 1)
    d.save()
    messages.success(request, f'Descuento aprobado. Inicia {d.fecha_inicio_descuento}.')
    return redirect('descuentos_detalle', pk=pk)


@login_required
@require_POST
def anular(request, pk):
    if not _is_admin(request.user):
        return HttpResponseForbidden()
    d = get_object_or_404(DescuentoPlanilla, pk=pk)
    motivo = (request.POST.get('motivo') or '').strip()
    d.estado = 'ANULADO'
    if motivo:
        d.observaciones = (d.observaciones or '') + f'\n[ANULADO {date.today()}] {motivo}'
    d.save()
    messages.info(request, 'Descuento anulado.')
    return redirect('descuentos_detalle', pk=pk)


# ── Portal del trabajador ──────────────────────────────────────────────

@login_required
def mis_descuentos(request):
    """El trabajador ve sus descuentos."""
    from portal.views import _get_empleado
    empleado = _get_empleado(request.user)
    if not empleado:
        messages.warning(request, 'Tu usuario no está vinculado a un empleado.')
        return redirect('portal_home')

    descuentos = DescuentoPlanilla.objects.filter(
        personal=empleado,
    ).exclude(estado='ANULADO').order_by('-fecha_registro')

    en_curso = descuentos.filter(estado__in=['APROBADO', 'EN_CURSO'])
    saldo = sum((d.saldo_pendiente for d in en_curso), Decimal('0'))
    cuota_mes = sum(
        (d.cuota_mensual or Decimal('0')) for d in en_curso
    )

    return render(request, 'descuentos/mis_descuentos.html', {
        'descuentos': descuentos,
        'empleado': empleado,
        'en_curso_count': en_curso.count(),
        'saldo': saldo,
        'cuota_mes': cuota_mes,
    })
