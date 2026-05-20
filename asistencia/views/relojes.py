"""
Vistas del módulo Tareo — Relojes Biométricos ZKTeco.

Permite configurar, probar y sincronizar relojes biométricos
ZKTeco y compatibles directamente desde Harmoni.
"""
import json
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from asistencia.views._common import solo_admin


# ─────────────────────────────────────────────────────────────
# LISTA DE RELOJES
# ─────────────────────────────────────────────────────────────

@login_required
@solo_admin
def lista_relojes(request):
    """Lista de relojes biométricos configurados."""
    from asistencia.models import RelojBiometrico

    relojes = (
        RelojBiometrico.objects
        .annotate(
            total_marc=Count('marcaciones'),
            sin_procesar=Count('marcaciones', filter=Q(marcaciones__procesado=False)),
        )
        .order_by('nombre')
    )

    context = {
        'titulo': 'Relojes Biométricos',
        'relojes': relojes,
        'pyzk_disponible': _check_pyzk(),
    }
    return render(request, 'asistencia/relojes/lista.html', context)


# ─────────────────────────────────────────────────────────────
# CREAR / EDITAR RELOJ
# ─────────────────────────────────────────────────────────────

@login_required
@solo_admin
def crear_reloj(request):
    """Formulario para añadir nuevo reloj biométrico."""
    from asistencia.models import RelojBiometrico

    if request.method == 'POST':
        try:
            reloj = _reloj_from_post(request.POST, RelojBiometrico())
            reloj.save()
            messages.success(request, f'Reloj "{reloj.nombre}" creado correctamente.')
            return redirect('asistencia_relojes_detalle', pk=reloj.pk)
        except Exception as e:
            messages.error(request, f'Error al guardar: {e}')

    context = {
        'titulo': 'Agregar Reloj Biométrico',
        'accion': 'Crear',
        'reloj': None,
    }
    return render(request, 'asistencia/relojes/form.html', context)


@login_required
@solo_admin
def editar_reloj(request, pk: int):
    """Formulario para editar reloj biométrico existente."""
    from asistencia.models import RelojBiometrico

    reloj = get_object_or_404(RelojBiometrico, pk=pk)

    if request.method == 'POST':
        try:
            reloj = _reloj_from_post(request.POST, reloj)
            reloj.save()
            messages.success(request, f'Reloj "{reloj.nombre}" actualizado.')
            return redirect('asistencia_relojes_detalle', pk=reloj.pk)
        except Exception as e:
            messages.error(request, f'Error al guardar: {e}')

    context = {
        'titulo': f'Editar: {reloj.nombre}',
        'accion': 'Guardar cambios',
        'reloj': reloj,
    }
    return render(request, 'asistencia/relojes/form.html', context)


@login_required
@solo_admin
@require_POST
def eliminar_reloj(request, pk: int):
    """Elimina un reloj (y sus marcaciones via CASCADE)."""
    from asistencia.models import RelojBiometrico
    reloj = get_object_or_404(RelojBiometrico, pk=pk)
    nombre = reloj.nombre
    reloj.delete()
    messages.warning(request, f'Reloj "{nombre}" eliminado.')
    return redirect('asistencia_relojes_lista')


# ─────────────────────────────────────────────────────────────
# DETALLE / PANEL DEL RELOJ
# ─────────────────────────────────────────────────────────────

@login_required
@solo_admin
def detalle_reloj(request, pk: int):
    """
    Página de detalle de un reloj:
      - Info del dispositivo y estado de conexión
      - Estadísticas de marcaciones
      - Lista de marcaciones recientes
      - Botones: Probar conexión, Sincronizar, Procesar a Tareo
    """
    from asistencia.models import MarcacionBiometrica, RelojBiometrico

    reloj = get_object_or_404(RelojBiometrico, pk=pk)

    # Fecha por defecto: mes actual
    hoy = date.today()
    fecha_ini_str = request.GET.get('fecha_ini', hoy.replace(day=1).isoformat())
    fecha_fin_str = request.GET.get('fecha_fin', hoy.isoformat())

    try:
        fecha_ini = date.fromisoformat(fecha_ini_str)
        fecha_fin = date.fromisoformat(fecha_fin_str)
    except ValueError:
        fecha_ini = hoy.replace(day=1)
        fecha_fin = hoy

    # Estadísticas del período
    marc_periodo = MarcacionBiometrica.objects.filter(
        reloj=reloj,
        timestamp__date__gte=fecha_ini,
        timestamp__date__lte=fecha_fin,
    )

    stats = {
        'total':        marc_periodo.count(),
        'sin_procesar': marc_periodo.filter(procesado=False).count(),
        'procesadas':   marc_periodo.filter(procesado=True).count(),
        'sin_match':    marc_periodo.filter(personal__isnull=True).count(),
    }

    # Empleados únicos en el período
    stats['empleados_unicos'] = (
        marc_periodo.values('user_id_dispositivo').distinct().count()
    )

    # Marcaciones recientes (últimas 100)
    marcaciones = (
        marc_periodo
        .select_related('personal')
        .order_by('-timestamp')[:100]
    )

    # Importaciones ZK previas para este reloj
    from asistencia.models import TareoImportacion
    importaciones = (
        TareoImportacion.objects
        .filter(tipo='ZK', metadata__reloj_id=reloj.pk)
        .order_by('-creado_en')[:10]
    )

    context = {
        'titulo': reloj.nombre,
        'reloj': reloj,
        'fecha_ini': fecha_ini,
        'fecha_fin': fecha_fin,
        'stats': stats,
        'marcaciones': marcaciones,
        'importaciones': importaciones,
        'pyzk_disponible': _check_pyzk(),
    }
    return render(request, 'asistencia/relojes/detalle.html', context)


# ─────────────────────────────────────────────────────────────
# AJAX: PROBAR CONEXIÓN
# ─────────────────────────────────────────────────────────────

@login_required
@solo_admin
@require_POST
def ajax_test_reloj(request, pk: int):
    """
    POST /asistencia/relojes/<pk>/test/
    Prueba la conexión al dispositivo. Retorna JSON.
    """
    from asistencia.models import RelojBiometrico
    from asistencia.services.zk_service import ZKService

    reloj = get_object_or_404(RelojBiometrico, pk=pk)

    if not _check_pyzk():
        return JsonResponse({
            'ok': False,
            'detail': 'pyzk no está instalado en el servidor. '
                      'Ejecuta: pip install pyzk',
        })

    svc    = ZKService(reloj)
    result = svc.test_connection()
    return JsonResponse(result)


# ─────────────────────────────────────────────────────────────
# AJAX: SINCRONIZAR (PULL ATTENDANCE)
# ─────────────────────────────────────────────────────────────

@login_required
@solo_admin
@require_POST
def ajax_sync_reloj(request, pk: int):
    """
    POST /asistencia/relojes/<pk>/sync/
    Descarga marcaciones del dispositivo → guarda en MarcacionBiometrica.
    Retorna JSON con contadores.
    """
    from asistencia.models import RelojBiometrico
    from asistencia.services.zk_service import ZKService

    reloj = get_object_or_404(RelojBiometrico, pk=pk)

    if not _check_pyzk():
        return JsonResponse({
            'ok': False,
            'error': 'pyzk no está instalado. Ejecuta: pip install pyzk',
        })

    svc    = ZKService(reloj)
    result = svc.pull_attendance(user=request.user)
    return JsonResponse(result)


# ─────────────────────────────────────────────────────────────
# AJAX: PROCESAR MARCACIONES → TAREO
# ─────────────────────────────────────────────────────────────

@login_required
@solo_admin
@require_POST
def ajax_procesar_reloj(request, pk: int):
    """
    POST /asistencia/relojes/<pk>/procesar/
    Body JSON: {"fecha_ini": "YYYY-MM-DD", "fecha_fin": "YYYY-MM-DD"}

    Convierte MarcacionBiometrica del período en RegistroTareo via TareoProcessor.
    """
    from asistencia.models import RelojBiometrico
    from asistencia.services.zk_service import ZKService

    reloj = get_object_or_404(RelojBiometrico, pk=pk)

    try:
        body = json.loads(request.body)
        fecha_ini = date.fromisoformat(body.get('fecha_ini', ''))
        fecha_fin = date.fromisoformat(body.get('fecha_fin', ''))
    except (ValueError, KeyError):
        return JsonResponse({'ok': False, 'error': 'Fechas inválidas.'}, status=400)

    if fecha_ini > fecha_fin:
        return JsonResponse({'ok': False, 'error': 'La fecha inicio debe ser ≤ fecha fin.'}, status=400)

    svc    = ZKService(reloj)
    result = svc.procesar_a_tareo(fecha_ini, fecha_fin, user=request.user)
    return JsonResponse(result)


# ─────────────────────────────────────────────────────────────
# AJAX: LISTA DE USUARIOS DEL DISPOSITIVO
# ─────────────────────────────────────────────────────────────

@login_required
@solo_admin
@require_POST
def ajax_usuarios_reloj(request, pk: int):
    """
    POST /asistencia/relojes/<pk>/usuarios/
    Obtiene lista de usuarios enrollados en el dispositivo.
    """
    from asistencia.models import RelojBiometrico
    from asistencia.services.zk_service import ZKService

    reloj = get_object_or_404(RelojBiometrico, pk=pk)

    if not _check_pyzk():
        return JsonResponse({'ok': False, 'usuarios': [], 'error': 'pyzk no instalado.'})

    svc    = ZKService(reloj)
    users  = svc.get_users()
    return JsonResponse({'ok': True, 'usuarios': users, 'total': len(users)})


# ─────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────

def _check_pyzk() -> bool:
    """Verifica si pyzk está disponible en el entorno."""
    try:
        import zk  # noqa: F401
        return True
    except ImportError:
        return False


def _reloj_from_post(post, reloj):
    """Puebla un objeto RelojBiometrico desde POST data."""
    reloj.nombre            = post.get('nombre', '').strip()
    reloj.ip                = post.get('ip', '').strip()
    reloj.puerto            = int(post.get('puerto') or 4370)
    reloj.timeout           = int(post.get('timeout') or 10)
    reloj.protocolo         = post.get('protocolo', 'TCP')
    reloj.campo_id_empleado = post.get('campo_id_empleado', 'USER_ID')
    reloj.ubicacion         = post.get('ubicacion', '').strip()
    reloj.descripcion       = post.get('descripcion', '').strip()
    reloj.activo            = post.get('activo') == '1'

    if not reloj.nombre:
        raise ValueError('El nombre del reloj es obligatorio.')
    if not reloj.ip:
        raise ValueError('La dirección IP es obligatoria.')

    return reloj
