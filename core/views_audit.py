"""
Vistas de Auditoría avanzada — lista paginada, detalle, timeline y export Excel.

Rutas: /sistema/auditoria/...
Solo accesible por superusuarios.
"""
import io
from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.contenttypes.models import ContentType
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone

from core.audit_models import AuditEntry
from core.models import AuditLog

User = get_user_model()

solo_admin = user_passes_test(lambda u: u.is_superuser, login_url='login')


def _build_audit_qs(request):
    """Construye el queryset filtrado a partir de los GET params."""
    qs = AuditLog.objects.select_related('usuario', 'content_type').all()

    accion = request.GET.get('accion', '').strip()
    usuario_id = request.GET.get('usuario', '').strip()
    modelo = request.GET.get('modelo', '').strip()
    buscar = request.GET.get('q', '').strip()
    fecha_desde = request.GET.get('fecha_desde', '').strip()
    fecha_hasta = request.GET.get('fecha_hasta', '').strip()

    if accion:
        qs = qs.filter(accion=accion)
    if usuario_id:
        qs = qs.filter(usuario_id=usuario_id)
    if modelo:
        try:
            ct = ContentType.objects.get(pk=modelo)
            qs = qs.filter(content_type=ct)
        except ContentType.DoesNotExist:
            pass
    if buscar:
        qs = qs.filter(
            Q(descripcion__icontains=buscar)
            | Q(usuario__username__icontains=buscar)
            | Q(usuario__first_name__icontains=buscar)
            | Q(usuario__last_name__icontains=buscar)
        )
    if fecha_desde:
        try:
            dt = datetime.strptime(fecha_desde, '%Y-%m-%d')
            qs = qs.filter(timestamp__gte=timezone.make_aware(dt))
        except ValueError:
            pass
    if fecha_hasta:
        try:
            dt = datetime.strptime(fecha_hasta, '%Y-%m-%d') + timedelta(days=1)
            qs = qs.filter(timestamp__lt=timezone.make_aware(dt))
        except ValueError:
            pass

    return qs


def _filter_context(request):
    """Contexto compartido para los filtros."""
    modelos_con_logs = ContentType.objects.filter(
        pk__in=AuditLog.objects.values_list('content_type_id', flat=True).distinct()
    ).order_by('model')

    usuarios_con_logs = User.objects.filter(
        pk__in=AuditLog.objects.values_list('usuario_id', flat=True).distinct()
    ).order_by('username')

    return {
        'modelos': modelos_con_logs,
        'usuarios': usuarios_con_logs,
        'filtro_accion': request.GET.get('accion', ''),
        'filtro_usuario': request.GET.get('usuario', ''),
        'filtro_modelo': request.GET.get('modelo', ''),
        'buscar': request.GET.get('q', ''),
        'fecha_desde': request.GET.get('fecha_desde', ''),
        'fecha_hasta': request.GET.get('fecha_hasta', ''),
    }


@login_required
@solo_admin
def audit_log_list(request):
    """Lista paginada de eventos de auditoría con filtros avanzados."""
    qs = _build_audit_qs(request)
    total = qs.count()

    # Estadísticas rápidas
    stats = AuditLog.objects.aggregate(
        total_creates=Count('pk', filter=Q(accion='CREATE')),
        total_updates=Count('pk', filter=Q(accion='UPDATE')),
        total_deletes=Count('pk', filter=Q(accion='DELETE')),
    )
    stats['total'] = AuditLog.objects.count()

    # Paginación
    per_page = int(request.GET.get('per_page', 50))
    per_page = min(max(per_page, 10), 200)
    paginator = Paginator(qs, per_page)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'titulo': 'Auditoría del Sistema',
        'page_obj': page_obj,
        'total_filtrado': total,
        'stats': stats,
        'per_page': per_page,
    }
    context.update(_filter_context(request))

    return render(request, 'core/audit/lista.html', context)


@login_required
@solo_admin
def audit_log_detail(request, pk):
    """Detalle completo de un registro de auditoría."""
    log = get_object_or_404(
        AuditLog.objects.select_related('usuario', 'content_type'),
        pk=pk,
    )

    # Registros adyacentes del mismo objeto para navegación
    same_object_logs = AuditLog.objects.filter(
        content_type=log.content_type,
        object_id=log.object_id,
    ).select_related('usuario').order_by('-timestamp')

    # Previous and next in the same object timeline
    prev_log = same_object_logs.filter(timestamp__gt=log.timestamp).order_by('timestamp').first()
    next_log = same_object_logs.filter(timestamp__lt=log.timestamp).order_by('-timestamp').first()

    context = {
        'titulo': f'Detalle de Auditoría #{log.pk}',
        'log': log,
        'same_object_logs': same_object_logs[:20],
        'prev_log': prev_log,
        'next_log': next_log,
    }
    return render(request, 'core/audit/detalle.html', context)


@login_required
@solo_admin
def audit_log_timeline(request, content_type_id, object_id):
    """Timeline de todos los cambios de un objeto específico."""
    ct = get_object_or_404(ContentType, pk=content_type_id)
    logs = AuditLog.objects.filter(
        content_type=ct,
        object_id=object_id,
    ).select_related('usuario').order_by('-timestamp')

    # Intentar obtener representación del objeto
    obj_repr = None
    try:
        model_class = ct.model_class()
        if model_class:
            obj = model_class.objects.filter(pk=object_id).first()
            if obj:
                obj_repr = str(obj)
    except Exception:
        pass

    context = {
        'titulo': f'Timeline — {ct.model.title()} #{object_id}',
        'logs': logs,
        'content_type': ct,
        'object_id': object_id,
        'obj_repr': obj_repr,
        'total': logs.count(),
    }
    return render(request, 'core/audit/timeline.html', context)


@login_required
@solo_admin
def audit_log_export(request):
    """Exporta los registros filtrados a Excel (.xlsx)."""
    try:
        import xlsxwriter
    except ImportError:
        return HttpResponse(
            'xlsxwriter no está instalado. Ejecute: pip install xlsxwriter',
            status=500,
        )

    qs = _build_audit_qs(request)[:10000]  # Limitar a 10k registros

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {'in_memory': True})
    worksheet = workbook.add_worksheet('Auditoría')

    # Formatos
    header_fmt = workbook.add_format({
        'bold': True,
        'bg_color': '#0d2b27',
        'font_color': '#ffffff',
        'border': 1,
        'text_wrap': True,
        'valign': 'vcenter',
    })
    date_fmt = workbook.add_format({'num_format': 'dd/mm/yyyy hh:mm:ss'})
    wrap_fmt = workbook.add_format({'text_wrap': True, 'valign': 'top'})

    # Cabeceras
    headers = ['ID', 'Fecha/Hora', 'Acción', 'Módulo', 'Objeto ID', 'Descripción',
               'Usuario', 'IP', 'Campos Modificados']
    for col, h in enumerate(headers):
        worksheet.write(0, col, h, header_fmt)

    # Anchos de columna
    widths = [8, 20, 14, 16, 10, 50, 16, 16, 60]
    for col, w in enumerate(widths):
        worksheet.set_column(col, col, w)

    # Datos
    for row_idx, log in enumerate(qs, start=1):
        worksheet.write(row_idx, 0, log.pk)
        if log.timestamp:
            worksheet.write_datetime(row_idx, 1, log.timestamp.replace(tzinfo=None), date_fmt)
        worksheet.write(row_idx, 2, log.get_accion_display())
        worksheet.write(row_idx, 3, log.content_type.model.title() if log.content_type else '')
        worksheet.write(row_idx, 4, log.object_id)
        worksheet.write(row_idx, 5, log.descripcion, wrap_fmt)
        worksheet.write(row_idx, 6, log.usuario.username if log.usuario else 'sistema')
        worksheet.write(row_idx, 7, log.ip_address or '')

        # Cambios como texto legible
        if log.cambios:
            cambios_text = []
            for campo, vals in log.cambios.items():
                old = vals.get('old', '—')
                new = vals.get('new', '—')
                cambios_text.append(f'{campo}: {old} → {new}')
            worksheet.write(row_idx, 8, '\n'.join(cambios_text), wrap_fmt)

    workbook.close()
    output.seek(0)

    now_str = timezone.now().strftime('%Y%m%d_%H%M')
    response = HttpResponse(
        output.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="auditoria_{now_str}.xlsx"'
    return response


# ════════════════════════════════════════════════════════════════════
#  AuditEntry (v2) — sistema de auditoría con signals automáticos
#  Modelo en core.audit_models.AuditEntry — usa entity_type como string
#  (no ContentType) para sobrevivir DELETEs y ser más liviano.
# ════════════════════════════════════════════════════════════════════

@login_required
@solo_admin
def audit_timeline(request, entity_type, entity_id):
    """Timeline de cambios para una entidad concreta (AuditEntry v2).

    URL: /sistema/audit/<entity_type>/<entity_id>/
    Solo admins. Renderiza un timeline tipo Notion ordenado fecha desc.
    """
    entries = (
        AuditEntry.objects
        .filter(entity_type=entity_type, entity_id=entity_id)
        .select_related('usuario', 'empresa')
        .order_by('-fecha')
    )

    context = {
        'titulo': f'Auditoría — {entity_type} #{entity_id}',
        'entity_type': entity_type,
        'entity_id': entity_id,
        'entries': entries,
        'total': entries.count(),
    }
    return render(request, 'core/audit_log_v2.html', context)
