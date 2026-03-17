"""
Core — Vistas de Reportes PDF Ejecutivos.

Endpoints para descargar reportes PDF generados con el motor HarmoniReport.
"""
import logging
from datetime import date

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

logger = logging.getLogger('core.views_reports')

solo_admin = user_passes_test(lambda u: u.is_superuser, login_url='login')


@login_required
@solo_admin
def reporte_planilla_pdf(request):
    """Download payroll summary PDF for a given periodo."""
    from nominas.models import PeriodoNomina

    periodo_id = request.GET.get('periodo')
    if not periodo_id:
        # Default: latest calculated/approved periodo
        periodo = (
            PeriodoNomina.objects
            .filter(estado__in=['CALCULADO', 'APROBADO', 'CERRADO'])
            .order_by('-anio', '-mes')
            .first()
        )
        if not periodo:
            return HttpResponse(
                'No hay periodos de nomina disponibles.', status=404)
    else:
        periodo = get_object_or_404(PeriodoNomina, pk=periodo_id)

    from core.reports.reporte_planilla import generar_reporte_planilla
    pdf_bytes = generar_reporte_planilla(periodo)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"reporte_planilla_{periodo.anio}_{periodo.mes:02d}.pdf"
    disposition = request.GET.get('inline', '')
    if disposition == '1':
        response['Content-Disposition'] = f'inline; filename="{filename}"'
    else:
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@solo_admin
def reporte_personal_pdf(request):
    """Download HR summary PDF."""
    estado = request.GET.get('estado', 'Activo')

    from core.reports.reporte_personal import generar_reporte_personal
    pdf_bytes = generar_reporte_personal(filtro_estado=estado)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"reporte_personal_{date.today().strftime('%Y%m%d')}.pdf"
    disposition = request.GET.get('inline', '')
    if disposition == '1':
        response['Content-Disposition'] = f'inline; filename="{filename}"'
    else:
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@solo_admin
def reporte_asistencia_pdf(request):
    """Download monthly attendance summary PDF."""
    hoy = date.today()
    anio = int(request.GET.get('anio', hoy.year))
    mes = int(request.GET.get('mes', hoy.month))

    from core.reports.reporte_asistencia import generar_reporte_asistencia
    pdf_bytes = generar_reporte_asistencia(anio, mes)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"reporte_asistencia_{anio}_{mes:02d}.pdf"
    disposition = request.GET.get('inline', '')
    if disposition == '1':
        response['Content-Disposition'] = f'inline; filename="{filename}"'
    else:
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@solo_admin
def reporte_vacaciones_pdf(request):
    """Download vacation summary PDF."""
    from core.reports.reporte_vacaciones import generar_reporte_vacaciones
    pdf_bytes = generar_reporte_vacaciones()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"reporte_vacaciones_{date.today().strftime('%Y%m%d')}.pdf"
    disposition = request.GET.get('inline', '')
    if disposition == '1':
        response['Content-Disposition'] = f'inline; filename="{filename}"'
    else:
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
