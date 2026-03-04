"""
personal/views/cese.py — Vista para registrar el cese de un trabajador.

Digitaliza el flujo manual que antes se hacía en Excel + email:
1. Admin selecciona empleado → abre modal "Dar de Baja"
2. Completa: fecha_cese, motivo_cese, observaciones
3. Al confirmar: actualiza Personal.estado='Cesado' + crea ProcesoOffboarding
4. Opcionalmente genera los 2 certificados de cese (Trabajo + 5ta Categoría)
"""
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from personal.models import Personal


# ─── Mapa motivo Personal ↔ motivo ProcesoOffboarding ─────────────────────────
# ProcesoOffboarding.MOTIVO_CHOICES solo tiene 5 opciones; mapeamos los 12 de Personal
_MOTIVO_OFF_MAP = {
    'RENUNCIA':       'RENUNCIA',
    'MUTUO_ACUERDO':  'MUTUO_ACUERDO',
    'JUBILACION':     'JUBILACION',
    'VENCIMIENTO':    'FIN_CONTRATO',
    'NO_RENOVACION':  'FIN_CONTRATO',
    'DESPIDO_CAUSA':  'DESPIDO',
    'CESE_COLECTIVO': 'DESPIDO',
    'LIQUIDACION':    'MUTUO_ACUERDO',
    'FALLECIMIENTO':  'FIN_CONTRATO',
    'INVALIDEZ':      'FIN_CONTRATO',
    'ABANDONO':       'DESPIDO',
    'OTRO':           'FIN_CONTRATO',
}


@login_required
@require_POST
def personal_dar_baja(request, pk):
    """
    POST — Registra el cese del trabajador:
      1. Actualiza Personal (estado, fecha_cese, motivo_cese, observaciones)
      2. Crea ProcesoOffboarding desde la primera plantilla activa (si existe)
      3. Invalida cache de notificaciones del usuario vinculado

    Acepta solicitudes AJAX (retorna JSON) y normales (redirect).
    """
    personal = get_object_or_404(Personal, pk=pk)
    es_ajax  = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    # ── Validar datos del formulario ─────────────────────────────────────
    fecha_cese_str = request.POST.get('fecha_cese', '').strip()
    motivo_cese    = request.POST.get('motivo_cese', 'VENCIMIENTO').strip()
    observaciones  = request.POST.get('observaciones', '').strip()

    if not fecha_cese_str:
        msg = 'La fecha de cese es obligatoria.'
        if es_ajax:
            return JsonResponse({'error': msg}, status=400)
        messages.error(request, msg)
        return redirect('personal_detail', pk=pk)

    try:
        fecha_cese = date.fromisoformat(fecha_cese_str)
    except ValueError:
        msg = 'Fecha de cese inválida.'
        if es_ajax:
            return JsonResponse({'error': msg}, status=400)
        messages.error(request, msg)
        return redirect('personal_detail', pk=pk)

    if personal.estado == 'Cesado':
        msg = f'{personal.apellidos_nombres} ya figura como Cesado.'
        if es_ajax:
            return JsonResponse({'error': msg}, status=400)
        messages.warning(request, msg)
        return redirect('personal_detail', pk=pk)

    # ── 1. Actualizar Personal ──────────────────────────────────────────
    personal.estado       = 'Cesado'
    personal.fecha_cese   = fecha_cese
    personal.motivo_cese  = motivo_cese
    if observaciones:
        existing = personal.observaciones or ''
        sep = '\n' if existing else ''
        personal.observaciones = f'{existing}{sep}[CESE {fecha_cese}] {observaciones}'
    personal.save(update_fields=['estado', 'fecha_cese', 'motivo_cese', 'observaciones'])

    # ── 2. Crear ProcesoOffboarding automático ─────────────────────────
    proceso_off = None
    try:
        from onboarding.models import PlantillaOffboarding, ProcesoOffboarding, PasoOffboarding, PasoPlantillaOff
        plantilla = PlantillaOffboarding.objects.filter(activa=True).first()
        if plantilla:
            motivo_off = _MOTIVO_OFF_MAP.get(motivo_cese, 'FIN_CONTRATO')
            proceso_off = ProcesoOffboarding.objects.create(
                personal=personal,
                plantilla=plantilla,
                motivo_cese=motivo_off,
                fecha_cese=fecha_cese,
                iniciado_por=request.user,
            )
            # Generar pasos desde la plantilla
            for paso_tmpl in PasoPlantillaOff.objects.filter(plantilla=plantilla).order_by('orden'):
                PasoOffboarding.objects.create(
                    proceso=proceso_off,
                    nombre=paso_tmpl.nombre,
                    descripcion=paso_tmpl.descripcion,
                    tipo=paso_tmpl.tipo,
                    orden=paso_tmpl.orden,
                    responsable=paso_tmpl.responsable_default,
                )
    except Exception:
        pass  # Si no hay plantilla o hay error, continúa sin offboarding

    # ── 3. Notificación (usar servicio existente si está disponible) ───
    try:
        from comunicaciones.services import NotificacionService
        NotificacionService.notificar_cese(personal, request.user)
    except Exception:
        pass

    # ── Respuesta ──────────────────────────────────────────────────────
    msg_ok = (
        f'{personal.apellidos_nombres} dado de baja exitosamente. '
        f'Fecha de cese: {fecha_cese.strftime("%d/%m/%Y")}.'
    )
    if proceso_off:
        msg_ok += ' Se creó el proceso de offboarding automáticamente.'

    if es_ajax:
        return JsonResponse({
            'success': True,
            'mensaje': msg_ok,
            'redirect': f'/personal/{pk}/',
            'proceso_off_pk': proceso_off.pk if proceso_off else None,
        })

    messages.success(request, msg_ok)
    return redirect('personal_detail', pk=pk)


@login_required
@require_POST
def personal_reactivar(request, pk):
    """
    POST — Reactiva un trabajador cesado (rectificación).
    Limpia fecha_cese y motivo_cese, vuelve a estado Activo.
    Requiere superusuario.
    """
    if not request.user.is_superuser:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Sin permisos.'}, status=403)
        messages.error(request, 'Solo administradores pueden reactivar trabajadores.')
        return redirect('personal_detail', pk=pk)

    personal = get_object_or_404(Personal, pk=pk)

    personal.estado      = 'Activo'
    personal.fecha_cese  = None
    personal.motivo_cese = ''
    personal.save(update_fields=['estado', 'fecha_cese', 'motivo_cese'])

    messages.success(request, f'{personal.apellidos_nombres} reactivado correctamente.')
    return redirect('personal_detail', pk=pk)
