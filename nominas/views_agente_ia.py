"""
Vistas del Agente IA Nóminas.

URLs:
- /nominas/agente/                       — lista conversaciones + crear nueva
- /nominas/agente/<id>/                  — chat con conversación específica
- /nominas/agente/<id>/mensaje/  (POST)  — enviar mensaje (AJAX)
- /nominas/reintegros/                   — lista reintegros pendientes
- /nominas/reintegros/<id>/              — detalle + aprobar/rechazar
- /nominas/reintegros/<id>/aprobar/      — aprobar reintegro
- /nominas/reintegros/<id>/aplicar/      — aplicar al período actual
- /nominas/reintegros/<id>/revertir/     — revertir
"""
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from .agente_ia.orquestador import procesar_mensaje
from .models import (
    AuditAgenteIA,
    ConversacionAgenteIA,
    MensajeAgenteIA,
    ReintegroNomina,
)

solo_admin = user_passes_test(lambda u: u.is_superuser)


def _empresa_del_user(user):
    """Detecta empresa del usuario."""
    try:
        from personal.models import Personal
        p = Personal.objects.filter(usuario=user).select_related('empresa').first()
        if p and p.empresa:
            return p.empresa
    except Exception:
        pass
    try:
        from empresas.models import Empresa
        return Empresa.objects.order_by('pk').first()
    except Exception:
        return None


# ════════════════════════════════════════════════════════════════════════
# Chat
# ════════════════════════════════════════════════════════════════════════

@login_required
@solo_admin
def agente_lista(request):
    """Lista conversaciones del usuario + acceso rápido a nueva."""
    conversaciones = ConversacionAgenteIA.objects.filter(
        usuario=request.user, archivada=False,
    ).order_by('-actualizada_en')[:30]

    reintegros_pendientes = ReintegroNomina.objects.filter(
        estado__in=['PROPUESTO', 'APROBADO'],
    ).count()

    return render(request, 'nominas/agente_ia/lista.html', {
        'conversaciones':       conversaciones,
        'reintegros_pendientes': reintegros_pendientes,
    })


@login_required
@solo_admin
def agente_nueva(request):
    """Crea conversación nueva y redirige al chat."""
    empresa = _empresa_del_user(request.user)
    conv = ConversacionAgenteIA.objects.create(
        usuario=request.user, empresa=empresa,
    )
    return redirect('agente_chat', pk=conv.pk)


@login_required
@solo_admin
def agente_chat(request, pk):
    """Pantalla de chat — historial + caja de input."""
    conv = get_object_or_404(
        ConversacionAgenteIA.objects.prefetch_related('mensajes'),
        pk=pk, usuario=request.user,
    )

    return render(request, 'nominas/agente_ia/chat.html', {
        'conversacion': conv,
        'mensajes':     conv.mensajes.all(),
    })


@login_required
@solo_admin
@require_POST
def agente_mensaje(request, pk):
    """AJAX endpoint — recibe mensaje, devuelve respuesta del agente."""
    import json

    conv = get_object_or_404(ConversacionAgenteIA, pk=pk, usuario=request.user)
    try:
        data = json.loads(request.body or '{}')
        texto = (data.get('mensaje') or '').strip()
    except Exception:
        texto = (request.POST.get('mensaje') or '').strip()

    if not texto:
        return JsonResponse({'error': 'Mensaje vacío'}, status=400)
    if len(texto) > 2000:
        return JsonResponse({'error': 'Mensaje demasiado largo (máx 2000 caracteres)'}, status=400)

    ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
         or request.META.get('REMOTE_ADDR')

    result = procesar_mensaje(
        conversacion=conv,
        texto_usuario=texto,
        usuario=request.user,
        ip=ip,
    )

    return JsonResponse({
        'respuesta':        result['respuesta'],
        'intent':           result['intent_detectado'],
        'tools_llamadas':   [t['name'] for t in result['tools_llamadas']],
    })


# ════════════════════════════════════════════════════════════════════════
# Reintegros — approval flow
# ════════════════════════════════════════════════════════════════════════

@login_required
@solo_admin
def reintegros_lista(request):
    """Lista todos los reintegros con filtros por estado."""
    estado_filter = request.GET.get('estado', '')
    qs = ReintegroNomina.objects.select_related(
        'personal', 'propuesto_por', 'aprobado_por',
    ).order_by('-creado_en')

    if estado_filter:
        qs = qs.filter(estado=estado_filter)

    # Stats por estado
    from django.db.models import Count
    stats = dict(
        ReintegroNomina.objects.values_list('estado').annotate(n=Count('id')).values_list('estado', 'n')
    )

    return render(request, 'nominas/agente_ia/reintegros_lista.html', {
        'reintegros':     qs[:200],
        'estado_filter':  estado_filter,
        'stats':          stats,
        'estados':        ReintegroNomina.ESTADO_CHOICES,
    })


@login_required
@solo_admin
def reintegro_detalle(request, pk):
    """Detalle de un reintegro + acciones disponibles según estado."""
    r = get_object_or_404(
        ReintegroNomina.objects.select_related(
            'personal', 'empresa', 'propuesto_por', 'aprobado_por',
            'conversacion_ia', 'periodo_aplicar', 'linea_generada',
        ),
        pk=pk,
    )

    # Períodos abiertos donde se podría aplicar
    from .models import PeriodoNomina
    periodos_disponibles = PeriodoNomina.objects.filter(
        tipo='REGULAR', estado__in=['BORRADOR', 'CALCULADO'],
    ).order_by('-anio', '-mes')[:6]

    return render(request, 'nominas/agente_ia/reintegro_detalle.html', {
        'reintegro':            r,
        'periodos_disponibles': periodos_disponibles,
        'impacto_aportes':      r.impacto_aportes or {},
    })


@login_required
@solo_admin
@require_POST
def reintegro_aprobar(request, pk):
    """Aprobar un reintegro propuesto."""
    r = get_object_or_404(ReintegroNomina, pk=pk)
    if r.estado != 'PROPUESTO':
        messages.error(request, f'Solo se pueden aprobar reintegros en estado PROPUESTO. Actual: {r.estado}.')
        return redirect('reintegro_detalle', pk=pk)

    r.estado = 'APROBADO'
    r.aprobado_por = request.user
    r.aprobado_en = timezone.now()
    r.save()

    AuditAgenteIA.objects.create(
        usuario=request.user,
        accion='PROPONER_REINTEGRO',
        detalle={'reintegro_id': r.pk, 'accion': 'aprobado', 'monto': str(r.monto_reintegro)},
        exito=True,
    )

    messages.success(request, f'Reintegro #{r.pk} aprobado. Ahora puedes aplicarlo a un período.')
    return redirect('reintegro_detalle', pk=pk)


@login_required
@solo_admin
@require_POST
def reintegro_aplicar(request, pk):
    """Aplicar reintegro APROBADO a un período abierto — crea LineaNomina."""
    r = get_object_or_404(ReintegroNomina, pk=pk)
    if r.estado != 'APROBADO':
        messages.error(request, f'Solo se aplican reintegros APROBADOS. Actual: {r.estado}.')
        return redirect('reintegro_detalle', pk=pk)

    periodo_id = request.POST.get('periodo_id')
    if not periodo_id:
        messages.error(request, 'Debes seleccionar el período donde aplicar.')
        return redirect('reintegro_detalle', pk=pk)

    from .models import PeriodoNomina, LineaNomina, RegistroNomina, ConceptoRemunerativo
    periodo = get_object_or_404(PeriodoNomina, pk=int(periodo_id))
    if periodo.estado not in ('BORRADOR', 'CALCULADO'):
        messages.error(request, f'El período {periodo} no acepta cambios (estado {periodo.estado}).')
        return redirect('reintegro_detalle', pk=pk)

    # Buscar/crear el registro del trabajador en ese período
    registro = RegistroNomina.objects.filter(
        periodo=periodo, personal=r.personal,
    ).first()
    if not registro:
        messages.error(request, f'{r.personal} no tiene registro en el período seleccionado. Genera el período primero.')
        return redirect('reintegro_detalle', pk=pk)

    # Buscar/crear el concepto "reintegro"
    concepto_reintegro, _ = ConceptoRemunerativo.objects.get_or_create(
        codigo='reintegro',
        defaults={
            'nombre':       'Reintegro',
            'descripcion':  'Reintegro por correcciones a planillas anteriores.',
            'categoria':    'OTROS_ING',
            'tipo':         'INGRESO',
            'subtipo':      'REMUNERATIVO',
            'formula':      'MANUAL',
            'afecto_essalud':    True,
            'afecto_afp':        True,
            'afecto_onp':        True,
            'afecto_renta':      True,
            'afecto_cts':        True,
            'afecto_gratif':     True,
            'afecto_vacaciones': True,
            'codigo_plame':      '0312',
            'es_sistema':        True,
        },
    )

    # Crear la línea
    linea = LineaNomina.objects.create(
        registro=registro,
        concepto=concepto_reintegro,
        monto=r.monto_reintegro,
        descripcion=(
            f'Reintegro por {r.get_motivo_display()} ({r.periodo_origen_str}): {r.descripcion}'
        )[:200],
    )

    # Actualizar el reintegro
    r.estado = 'APLICADO'
    r.aplicado_en = timezone.now()
    r.periodo_aplicar = periodo
    r.linea_generada = linea
    r.save()

    AuditAgenteIA.objects.create(
        usuario=request.user,
        accion='APLICAR_REINTEGRO',
        detalle={
            'reintegro_id': r.pk,
            'periodo_id':   periodo.pk,
            'linea_id':     linea.pk,
            'monto':        str(r.monto_reintegro),
        },
        exito=True,
    )

    messages.success(
        request,
        f'Reintegro #{r.pk} aplicado a la planilla {periodo.mes:02d}/{periodo.anio}. '
        f'Línea creada por S/ {r.monto_reintegro}.',
    )
    return redirect('reintegro_detalle', pk=pk)


@login_required
@solo_admin
@require_POST
def reintegro_revertir(request, pk):
    """Revertir un reintegro aplicado (elimina la línea generada)."""
    r = get_object_or_404(ReintegroNomina, pk=pk)
    if r.estado not in ('APROBADO', 'APLICADO'):
        messages.error(request, f'No se puede revertir un reintegro en estado {r.estado}.')
        return redirect('reintegro_detalle', pk=pk)

    motivo = (request.POST.get('motivo') or '').strip()
    if not motivo:
        messages.error(request, 'Debes indicar el motivo de la reversión.')
        return redirect('reintegro_detalle', pk=pk)

    # Si está APLICADO, eliminar la línea
    if r.estado == 'APLICADO' and r.linea_generada_id:
        try:
            r.linea_generada.delete()
        except Exception:
            pass

    r.estado = 'REVERSADO'
    r.revertido_por = request.user
    r.revertido_en = timezone.now()
    r.motivo_reversion = motivo
    r.save()

    AuditAgenteIA.objects.create(
        usuario=request.user,
        accion='REVERTIR_REINTEGRO',
        detalle={'reintegro_id': r.pk, 'motivo': motivo},
        exito=True,
    )

    messages.success(request, f'Reintegro #{r.pk} reversado.')
    return redirect('reintegro_detalle', pk=pk)
