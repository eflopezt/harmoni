"""
Control de Activos / Herramientas asignadas al personal.
"""
from datetime import date
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from personal.models import Personal, ActivoAsignado

solo_admin = user_passes_test(lambda u: u.is_superuser or u.is_staff, login_url='login')


@login_required
@solo_admin
def activos_panel(request):
    """Panel de activos asignados al personal."""
    activos = ActivoAsignado.objects.select_related('personal').all()

    buscar = request.GET.get('q', '').strip()
    estado = request.GET.get('estado', '')
    tipo = request.GET.get('tipo', '')

    if buscar:
        activos = activos.filter(
            Q(personal__apellidos_nombres__icontains=buscar) |
            Q(personal__nro_doc__icontains=buscar) |
            Q(descripcion__icontains=buscar) |
            Q(serial__icontains=buscar)
        )
    if estado:
        activos = activos.filter(estado=estado)
    if tipo:
        activos = activos.filter(tipo=tipo)

    kpi = ActivoAsignado.objects.aggregate(
        asignados=Count('id', filter=Q(estado='ASIGNADO')),
        devueltos=Count('id', filter=Q(estado='DEVUELTO')),
        extraviados=Count('id', filter=Q(estado='EXTRAVIADO')),
    )

    return render(request, 'personal/activos_panel.html', {
        'activos': activos[:200],
        'total': activos.count(),
        'kpi': kpi,
        'buscar': buscar,
        'filtro_estado': estado,
        'filtro_tipo': tipo,
        'tipos': ActivoAsignado.TIPO_CHOICES,
    })


@login_required
@solo_admin
@require_POST
def activo_asignar(request, personal_pk):
    """Asignar un activo a un trabajador."""
    personal = get_object_or_404(Personal, pk=personal_pk)

    activo = ActivoAsignado.objects.create(
        personal=personal,
        tipo=request.POST.get('tipo', 'OTRO'),
        descripcion=request.POST.get('descripcion', ''),
        serial=request.POST.get('serial', ''),
        fecha_asignacion=request.POST.get('fecha_asignacion', date.today()),
        valor_estimado=request.POST.get('valor_estimado') or None,
        observaciones=request.POST.get('observaciones', ''),
        registrado_por=request.user,
    )

    messages.success(request, f'Activo "{activo.descripcion}" asignado a {personal.apellidos_nombres}')
    return redirect('activos_panel')


@login_required
@solo_admin
@require_POST
def activo_devolver(request, pk):
    """Registrar devolución de un activo."""
    activo = get_object_or_404(ActivoAsignado, pk=pk)
    activo.estado = 'DEVUELTO'
    activo.fecha_devolucion = date.today()
    activo.observaciones += f'\nDevuelto el {date.today()} por {request.user.get_full_name()}'
    activo.save()

    messages.success(request, f'Activo "{activo.descripcion}" marcado como devuelto.')
    return redirect('activos_panel')
