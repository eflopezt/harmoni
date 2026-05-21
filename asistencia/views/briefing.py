"""Briefing del Día — vistas (admin + worker).

Pre-shift handover de gastronomía premium. Brigade kitchen style.
"""
from datetime import date as _date
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from asistencia.models import BriefingServicio, BriefingLectura
from empresas.models import Empresa

solo_admin_o_jefe = user_passes_test(lambda u: u.is_superuser or u.is_staff)


@login_required
@solo_admin_o_jefe
def briefing_panel(request):
    """Lista de briefings del local — recientes primero."""
    fecha_filtro = request.GET.get('fecha', '')
    empresa_id = request.GET.get('empresa_id', '')

    qs = BriefingServicio.objects.select_related('empresa', 'publicado_por').order_by('-fecha', '-id')

    if fecha_filtro:
        try:
            qs = qs.filter(fecha=fecha_filtro)
        except (ValueError, TypeError):
            pass
    if empresa_id:
        try:
            qs = qs.filter(empresa_id=int(empresa_id))
        except (ValueError, TypeError):
            pass

    # Stats
    hoy = _date.today()
    hoy_count       = BriefingServicio.objects.filter(fecha=hoy).count()
    publicados_hoy  = BriefingServicio.objects.filter(fecha=hoy, estado='PUBLICADO').count()
    borradores_hoy  = BriefingServicio.objects.filter(fecha=hoy, estado='BORRADOR').count()

    empresas = Empresa.objects.filter(activa=True).order_by('razon_social')

    return render(request, 'asistencia/briefing_panel.html', {
        'briefings':      qs[:50],
        'fecha_filtro':   fecha_filtro,
        'empresa_filtro': empresa_id,
        'empresas':       empresas,
        'hoy':            hoy,
        'hoy_count':      hoy_count,
        'publicados_hoy': publicados_hoy,
        'borradores_hoy': borradores_hoy,
    })


@login_required
@solo_admin_o_jefe
def briefing_crear(request):
    """Crea un nuevo briefing (form simple)."""
    if request.method == 'POST':
        empresa_id = request.POST.get('empresa')
        fecha      = request.POST.get('fecha')
        servicio   = request.POST.get('servicio', 'ALMUERZO')

        try:
            empresa = Empresa.objects.get(pk=int(empresa_id))
        except (Empresa.DoesNotExist, ValueError, TypeError):
            messages.error(request, 'Empresa inválida.')
            return redirect('briefing_panel')

        try:
            anio, mes, dia = fecha.split('-')
            fecha_obj = _date(int(anio), int(mes), int(dia))
        except (ValueError, AttributeError):
            messages.error(request, 'Fecha inválida.')
            return redirect('briefing_panel')

        # Evitar duplicado (unique_together)
        if BriefingServicio.objects.filter(
            empresa=empresa, fecha=fecha_obj, servicio=servicio,
        ).exists():
            messages.warning(
                request,
                f'Ya existe un briefing de {servicio} para {empresa} el {fecha_obj}. Edítalo en su lugar.',
            )
            existing = BriefingServicio.objects.get(
                empresa=empresa, fecha=fecha_obj, servicio=servicio,
            )
            return redirect('briefing_detalle', pk=existing.pk)

        b = BriefingServicio.objects.create(
            empresa=empresa,
            fecha=fecha_obj,
            servicio=servicio,
            covers_esperados=int(request.POST.get('covers_esperados') or 0),
            notas_chef=request.POST.get('notas_chef', '').strip(),
            especiales=request.POST.get('especiales', '').strip(),
            items_86=request.POST.get('items_86', '').strip(),
            vips_alergias=request.POST.get('vips_alergias', '').strip(),
            dress_code=request.POST.get('dress_code', '').strip(),
            notas_operativas=request.POST.get('notas_operativas', '').strip(),
            estado='BORRADOR',
        )

        # Si "publicar=1" lo publica inmediatamente
        if request.POST.get('publicar') == '1':
            b.publicar(request.user)
            messages.success(
                request,
                f'✓ Briefing publicado: {b}. Los trabajadores asignados lo verán al hacer login.',
            )
        else:
            messages.success(request, f'Briefing guardado como borrador: {b}.')

        return redirect('briefing_detalle', pk=b.pk)

    # GET → form
    empresas = Empresa.objects.filter(activa=True).order_by('razon_social')
    return render(request, 'asistencia/briefing_form.html', {
        'briefing':         None,
        'empresas':         empresas,
        'fecha_default':    _date.today().isoformat(),
        'servicio_choices': BriefingServicio.SERVICIO_CHOICES,
    })


@login_required
@solo_admin_o_jefe
def briefing_detalle(request, pk):
    """Detalle/edición de un briefing. Permite publicar/cerrar."""
    b = get_object_or_404(BriefingServicio.objects.select_related('empresa', 'publicado_por'), pk=pk)

    if request.method == 'POST':
        accion = request.POST.get('accion', '')

        if accion == 'editar':
            b.covers_esperados = int(request.POST.get('covers_esperados') or 0)
            b.notas_chef       = request.POST.get('notas_chef', '').strip()
            b.especiales       = request.POST.get('especiales', '').strip()
            b.items_86         = request.POST.get('items_86', '').strip()
            b.vips_alergias    = request.POST.get('vips_alergias', '').strip()
            b.dress_code       = request.POST.get('dress_code', '').strip()
            b.notas_operativas = request.POST.get('notas_operativas', '').strip()
            b.save()
            messages.success(request, 'Briefing actualizado.')

        elif accion == 'publicar' and b.estado == 'BORRADOR':
            b.publicar(request.user)
            messages.success(
                request,
                f'✓ Briefing publicado. Los trabajadores asignados al servicio '
                f'lo verán al hacer login.',
            )

        elif accion == 'cerrar' and b.estado == 'PUBLICADO':
            b.estado = 'CERRADO'
            b.save(update_fields=['estado', 'actualizado_en'])
            messages.info(request, 'Briefing cerrado.')

        elif accion == 'eliminar' and b.estado == 'BORRADOR':
            b.delete()
            messages.warning(request, 'Briefing eliminado.')
            return redirect('briefing_panel')

        return redirect('briefing_detalle', pk=b.pk)

    # Lecturas del briefing
    lecturas = b.lecturas.select_related('personal').order_by('-leido_en')
    total_lecturas = lecturas.count()

    return render(request, 'asistencia/briefing_detalle.html', {
        'briefing':       b,
        'lecturas':       lecturas[:30],
        'total_lecturas': total_lecturas,
    })


@login_required
def briefing_marcar_leido(request, pk):
    """Endpoint AJAX para que un trabajador marque que leyó el briefing."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST requerido'}, status=405)

    b = get_object_or_404(BriefingServicio, pk=pk, estado='PUBLICADO')

    # Personal asociado al user
    try:
        from personal.models import Personal
        personal = Personal.objects.get(usuario=request.user)
    except (Personal.DoesNotExist, AttributeError):
        return JsonResponse({'ok': False, 'error': 'No es trabajador'}, status=403)

    lectura, created = BriefingLectura.objects.get_or_create(
        briefing=b, personal=personal,
    )
    return JsonResponse({
        'ok':       True,
        'created':  created,
        'leido_en': lectura.leido_en.isoformat(),
    })
