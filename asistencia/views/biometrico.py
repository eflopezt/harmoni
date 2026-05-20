"""
Vistas del módulo Tareo — Panel Biométrico.

Panel de gestión de dispositivos ZKTeco con vista de status,
formulario de alta y logs de sincronización.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from asistencia.views._common import solo_admin


@login_required
@solo_admin
def panel_biometrico(request):
    """Panel principal de dispositivos biométricos con status cards."""
    from asistencia.models import RelojBiometrico, MarcacionBiometrica

    dispositivos = list(
        RelojBiometrico.objects.all().order_by('-activo', 'nombre')
    )

    # Enrich with stats
    for d in dispositivos:
        d.total_marc = MarcacionBiometrica.objects.filter(reloj=d).count()
        d.sin_procesar = MarcacionBiometrica.objects.filter(
            reloj=d, procesado=False
        ).count() if hasattr(MarcacionBiometrica, 'procesado') else 0

    stats = {
        'total': len(dispositivos),
        'online': sum(1 for d in dispositivos if d.estado_conexion == 'CONECTADO'),
        'offline': sum(1 for d in dispositivos if d.estado_conexion in ('DESCONECTADO', 'ERROR', 'SIN_VERIFICAR')),
        'sin_procesar': sum(getattr(d, 'sin_procesar', 0) for d in dispositivos),
    }

    return render(request, 'asistencia/biometrico/panel.html', {
        'titulo': 'Panel Biométrico',
        'dispositivos': dispositivos,
        'stats': stats,
    })


@login_required
@solo_admin
def agregar_dispositivo(request):
    """Formulario para agregar un nuevo dispositivo biométrico."""
    from asistencia.models import RelojBiometrico

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        ip = request.POST.get('ip', '').strip()
        puerto = int(request.POST.get('puerto', 4370) or 4370)
        timeout = int(request.POST.get('timeout', 10) or 10)
        protocolo = request.POST.get('protocolo', 'TCP')
        ubicacion = request.POST.get('ubicacion', '').strip()
        campo_id = request.POST.get('campo_id_empleado', 'USER_ID')
        activo = 'activo' in request.POST

        if not nombre or not ip:
            messages.error(request, 'Nombre e IP son requeridos.')
            return render(request, 'asistencia/biometrico/agregar.html', {
                'titulo': 'Agregar Dispositivo',
                'form': request.POST,
            })

        reloj = RelojBiometrico.objects.create(
            nombre=nombre,
            ip=ip,
            puerto=puerto,
            timeout=timeout,
            protocolo=protocolo,
            ubicacion=ubicacion,
            campo_id_empleado=campo_id,
            activo=activo,
        )
        messages.success(request, f'Dispositivo "{nombre}" creado exitosamente.')
        return redirect('asistencia_biometrico_panel')

    return render(request, 'asistencia/biometrico/agregar.html', {
        'titulo': 'Agregar Dispositivo',
        'form': {},
    })


@login_required
@solo_admin
@require_POST
def test_dispositivo(request):
    """AJAX: Probar conexión a un dispositivo por IP/puerto."""
    import json
    try:
        body = json.loads(request.body)
        ip = body.get('ip', '').strip()
        puerto = int(body.get('puerto', 4370))
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'detail': 'Datos inválidos.'})

    if not ip:
        return JsonResponse({'ok': False, 'detail': 'IP requerida.'})

    try:
        from asistencia.services.zkteco_service import ZKTecoService
        svc = ZKTecoService()
        result = svc.test_connection(ip, puerto)
        return JsonResponse(result)
    except ImportError:
        return JsonResponse({
            'ok': False,
            'detail': 'Librería pyzk no instalada. Ejecuta: pip install pyzk',
        })
    except Exception as e:
        return JsonResponse({'ok': False, 'detail': str(e)})


@login_required
@solo_admin
def logs_sincronizacion(request):
    """Historial de sincronizaciones de dispositivos biométricos."""
    from asistencia.models import RelojBiometrico

    dispositivos = RelojBiometrico.objects.all().order_by('nombre')

    # Build logs list from available data
    # For now, return an empty list — logs would need a SyncLog model
    # or could be reconstructed from MarcacionBiometrica timestamps
    logs = []

    dispositivo_filtro = request.GET.get('dispositivo', '')
    estado_filtro = request.GET.get('estado', '')
    desde = request.GET.get('desde', '')
    hasta = request.GET.get('hasta', '')

    return render(request, 'asistencia/biometrico/logs.html', {
        'titulo': 'Historial de Sincronización',
        'logs': logs,
        'dispositivos': dispositivos,
        'dispositivo_filtro': dispositivo_filtro,
        'estado_filtro': estado_filtro,
        'desde': desde,
        'hasta': hasta,
    })
