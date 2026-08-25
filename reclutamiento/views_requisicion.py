"""
Aprobación de requisición de vacante (paso previo a publicar).

Flujo:
    BORRADOR --[solicitar]--> POR_APROBAR --[aprobar]--> APROBADA (+ aprobada_por)
                                          --[rechazar]--> BORRADOR (sin aprobar)

Una vacante que nunca pasó por aprobación puede publicarse igual (flujo
aditivo para vacantes simples), pero mientras está POR_APROBAR queda
bloqueada para publicar hasta que el aprobador decida.
"""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import Vacante
from core.permisos import requiere_modulo

solo_reclutamiento = requiere_modulo('reclutamiento')


def _puede_aprobar(user):
    """Aprobadores: staff/superuser o perfil con puede_aprobar."""
    if user.is_superuser or user.is_staff:
        return True
    perfil = getattr(user, 'perfil_acceso', None)
    return bool(perfil and getattr(perfil, 'puede_aprobar', False))


@login_required
@solo_reclutamiento
@require_POST
def vacante_solicitar_aprobacion(request, pk):
    v = get_object_or_404(Vacante, pk=pk)
    if v.estado == 'BORRADOR':
        just = (request.POST.get('justificacion') or '').strip()
        if just:
            v.justificacion = just
        v.estado = 'POR_APROBAR'
        v.aprobada_por = None
        v.fecha_aprobacion = None
        v.save(update_fields=['estado', 'justificacion', 'aprobada_por',
                              'fecha_aprobacion', 'actualizado_en'])
        messages.success(request, 'Requisición enviada a aprobación.')
    else:
        messages.info(request, 'La vacante no está en borrador.')
    return redirect('vacante_detalle', pk=pk)


@login_required
@solo_reclutamiento
@require_POST
def vacante_aprobar(request, pk):
    v = get_object_or_404(Vacante, pk=pk)
    if not _puede_aprobar(request.user):
        messages.error(request, 'No tienes permisos para aprobar requisiciones.')
        return redirect('vacante_detalle', pk=pk)
    if v.estado == 'POR_APROBAR':
        v.estado = 'APROBADA'
        v.aprobada_por = request.user
        v.fecha_aprobacion = timezone.now()
        v.save(update_fields=['estado', 'aprobada_por', 'fecha_aprobacion',
                              'actualizado_en'])
        messages.success(request, 'Requisición aprobada. Ya puedes publicar la vacante.')
    else:
        messages.info(request, 'La requisición no está pendiente de aprobación.')
    return redirect('vacante_detalle', pk=pk)


@login_required
@solo_reclutamiento
@require_POST
def vacante_rechazar(request, pk):
    v = get_object_or_404(Vacante, pk=pk)
    if not _puede_aprobar(request.user):
        messages.error(request, 'No tienes permisos para rechazar requisiciones.')
        return redirect('vacante_detalle', pk=pk)
    if v.estado == 'POR_APROBAR':
        motivo = (request.POST.get('motivo') or '').strip()
        if motivo:
            v.justificacion = (f'{v.justificacion}\n[Rechazo] {motivo}').strip()
        v.estado = 'BORRADOR'
        v.aprobada_por = None
        v.fecha_aprobacion = None
        v.save(update_fields=['estado', 'aprobada_por', 'fecha_aprobacion',
                              'justificacion', 'actualizado_en'])
        messages.warning(request, 'Requisición rechazada; vuelve a borrador.')
    else:
        messages.info(request, 'La requisición no está pendiente de aprobación.')
    return redirect('vacante_detalle', pk=pk)
