"""
Core — Vista para descargar el Reporte BI Excel mensual.
"""
from __future__ import annotations

import logging
from datetime import date

from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import HttpResponse, HttpResponseBadRequest

logger = logging.getLogger('core.views_bi')


@login_required
@user_passes_test(lambda u: u.is_superuser or u.is_staff, login_url='login')
def reporte_bi_mensual(request):
    """Genera y descarga el Excel BI mensual cross-modulo.

    Query params:
      - anio (int, default año actual)
      - mes  (int 1-12, default mes actual)
      - empresa_id (int opcional, filtra por RUC)
    """
    hoy = date.today()
    try:
        anio = int(request.GET.get('anio', hoy.year))
        mes = int(request.GET.get('mes', hoy.month))
    except (TypeError, ValueError):
        return HttpResponseBadRequest('anio y mes deben ser enteros')

    if not (1 <= mes <= 12):
        return HttpResponseBadRequest('mes debe estar entre 1 y 12')
    if anio < 2000 or anio > 2100:
        return HttpResponseBadRequest('anio fuera de rango')

    empresa_id_raw = request.GET.get('empresa_id') or request.GET.get('empresa')
    empresa_id = None
    if empresa_id_raw:
        try:
            empresa_id = int(empresa_id_raw)
        except (TypeError, ValueError):
            return HttpResponseBadRequest('empresa_id debe ser entero')

    from core.bi_excel import build_reporte_bi_mensual
    try:
        excel_bytes = build_reporte_bi_mensual(anio, mes, empresa_id=empresa_id)
    except Exception:
        logger.exception('Error generando reporte BI %s/%s', anio, mes)
        return HttpResponse(
            'Error generando el reporte. Revise logs.', status=500,
        )

    response = HttpResponse(
        excel_bytes,
        content_type=(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ),
    )
    filename = f'reporte_bi_{anio}_{mes:02d}.xlsx'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['Content-Length'] = str(len(excel_bytes))
    return response
