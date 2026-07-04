"""
Gestión MANUAL de suscripciones (sin pasarela de pago).

Solo para el dueño/staff de Harmoni (superuser). Permite ver el estado de cada
empresa (plan, prueba, suscripción) y registrar pagos manualmente: extender la
suscripción, cambiar de plan, o cancelar.

URL: /sistema/suscripciones/   (name='suscripciones_admin')
"""
from datetime import timedelta

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from empresas.models import Empresa


from core.permisos import es_operador_plataforma


@user_passes_test(es_operador_plataforma, login_url='home')
@require_http_methods(['GET', 'POST'])
def suscripciones_admin(request):
    from core.planes import PLANES, plan_choices

    if request.method == 'POST':
        emp = Empresa.objects.filter(pk=request.POST.get('empresa_id')).first()
        accion = request.POST.get('accion')
        if not emp:
            messages.error(request, 'Empresa no encontrada.')
            return redirect('suscripciones_admin')

        hoy = timezone.localdate()
        base = emp.suscripcion_hasta if (emp.suscripcion_hasta and emp.suscripcion_hasta >= hoy) else hoy

        if accion == 'extender':
            meses = int(request.POST.get('meses', 1))
            periodo_desde = base
            emp.suscripcion_hasta = base + timedelta(days=30 * meses)
            metodo = request.POST.get('metodo', 'YAPE')
            referencia = request.POST.get('referencia', '').strip()
            if referencia:
                emp.suscripcion_nota = f'{metodo} · {referencia}'
            emp.save(update_fields=['suscripcion_hasta', 'suscripcion_nota', 'actualizado_en'])

            # Registrar el pago en el ledger (HistorialPago) — comprobante/referencia.
            try:
                from empresas.models_billing import HistorialPago
                precio = PLANES.get(emp.plan, {}).get('precio') or 0
                HistorialPago.objects.create(
                    empresa=emp, monto=precio * meses, fecha_pago=hoy,
                    metodo_pago=metodo, referencia=referencia, estado='PAGADO',
                    periodo_desde=periodo_desde, periodo_hasta=emp.suscripcion_hasta,
                    registrado_por=request.user,
                    notas=f'Registro manual desde panel de suscripciones ({meses} mes/es).',
                )
            except Exception:
                pass
            messages.success(request, f'{emp.razon_social}: pago registrado, suscripción hasta {emp.suscripcion_hasta}.')

        elif accion == 'cambiar_plan':
            nuevo = request.POST.get('plan')
            if nuevo in PLANES:
                emp.plan = nuevo
                emp.save(update_fields=['plan', 'actualizado_en'])
                messages.success(request, f'{emp.razon_social}: plan → {PLANES[nuevo]["nombre"]}.')
            else:
                messages.error(request, 'Plan inválido.')

        elif accion == 'cancelar':
            # Bloquea acceso desde ya (suscripción vencida ayer).
            emp.suscripcion_hasta = hoy - timedelta(days=1)
            emp.save(update_fields=['suscripcion_hasta', 'actualizado_en'])
            messages.warning(request, f'{emp.razon_social}: suscripción cancelada (acceso bloqueado).')

        elif accion == 'extender_trial':
            dias = int(request.POST.get('dias', 30))
            tb = emp.fecha_fin_prueba if (emp.fecha_fin_prueba and emp.fecha_fin_prueba >= hoy) else hoy
            emp.fecha_fin_prueba = tb + timedelta(days=dias)
            emp.save(update_fields=['fecha_fin_prueba', 'actualizado_en'])
            messages.success(request, f'{emp.razon_social}: prueba extendida {dias} días → {emp.fecha_fin_prueba}.')

        return redirect('suscripciones_admin')

    # GET — listado
    empresas = list(
        Empresa.objects.annotate(
            n_workers=Count('personal', filter=Q(personal__estado='Activo'))
        ).prefetch_related('pagos_suscripcion').order_by('-actualizado_en')
    )
    # Resumen por estado
    resumen = {'ACTIVA': 0, 'TRIAL': 0, 'VENCIDA': 0, 'SIN_RESTRICCION': 0}
    for e in empresas:
        resumen[e.estado_suscripcion] = resumen.get(e.estado_suscripcion, 0) + 1

    return render(request, 'core/suscripciones_admin.html', {
        'empresas': empresas,
        'resumen':  resumen,
        'planes':   [{'codigo': c, 'nombre': PLANES[c]['nombre']} for c in PLANES],
    })


@user_passes_test(es_operador_plataforma, login_url='home')
def suscripcion_pagos(request, empresa_id):
    """Historial completo de pagos (ledger) de una empresa."""
    from empresas.models_billing import HistorialPago
    emp = Empresa.objects.filter(pk=empresa_id).first()
    if not emp:
        messages.error(request, 'Empresa no encontrada.')
        return redirect('suscripciones_admin')
    pagos = HistorialPago.objects.filter(empresa=emp).order_by('-fecha_pago', '-creado_en')
    total = sum((p.monto for p in pagos if p.estado == 'PAGADO'), 0)
    return render(request, 'core/suscripcion_pagos.html', {
        'empresa': emp, 'pagos': pagos, 'total': total,
    })
