"""
PDF Reporte Ejecutivo del Mes — 1 página para gerencia.

Resumen consolidado del período: KPIs, top 5, distribución, alertas.
Diseñado para "El Mes en Una Página" — directo y accionable.

URL: /nominas/periodos/<pk>/reporte-ejecutivo.pdf
"""
from decimal import Decimal

from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Avg, Count, Max, Min, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string

solo_admin = user_passes_test(lambda u: u.is_superuser)


@login_required
@solo_admin
def reporte_ejecutivo_pdf(request, pk):
    """Genera PDF resumen ejecutivo del período."""
    from .models import PeriodoNomina, RegistroNomina
    from .views_anomalias import detectar_anomalias_periodo

    periodo = get_object_or_404(PeriodoNomina, pk=pk)

    # KPIs principales
    agg = periodo.registros.aggregate(
        total_trab=Count('id'),
        total_neto=Sum('neto_a_pagar'),
        total_bruto=Sum('total_ingresos'),
        total_desc=Sum('total_descuentos'),
        total_essalud=Sum('aporte_essalud'),
        avg_neto=Avg('neto_a_pagar'),
        max_neto=Max('neto_a_pagar'),
        min_neto=Min('neto_a_pagar'),
    )

    # Top 5 mayores netos
    top_5 = list(
        periodo.registros.select_related('personal')
        .order_by('-neto_a_pagar')[:5]
    )

    # Bottom 3 (atención sueldos bajos / cesados)
    bottom_3 = list(
        periodo.registros.select_related('personal')
        .filter(neto_a_pagar__gt=0)
        .order_by('neto_a_pagar')[:3]
    )

    # Comparativa vs mes anterior
    mes_ant = periodo.mes - 1
    anio_ant = periodo.anio
    if mes_ant <= 0:
        mes_ant = 12
        anio_ant -= 1
    anterior = PeriodoNomina.objects.filter(
        tipo=periodo.tipo, anio=anio_ant, mes=mes_ant,
    ).first()
    delta_neto = None
    delta_pct = None
    if anterior and anterior.total_neto:
        delta_neto = (periodo.total_neto or Decimal('0')) - anterior.total_neto
        if anterior.total_neto > 0:
            delta_pct = float(delta_neto / anterior.total_neto * Decimal('100'))

    # Anomalías
    anomalias_report = detectar_anomalias_periodo(periodo)
    n_anomalias = len(anomalias_report['anomalias'])
    anomalias_top = anomalias_report['anomalias'][:5]

    # Empresa
    empresa = None
    try:
        from empresas.models import Empresa
        empresa = periodo.empresa or Empresa.objects.first()
    except Exception:
        pass

    from django.utils import timezone
    html = render_to_string('nominas/reporte_ejecutivo_pdf.html', {
        'periodo':       periodo,
        'empresa':       empresa,
        'kpis':          agg,
        'top_5':         top_5,
        'bottom_3':      bottom_3,
        'anterior':      anterior,
        'delta_neto':    delta_neto,
        'delta_pct':     delta_pct,
        'n_anomalias':   n_anomalias,
        'anomalias':     anomalias_top,
        'anomalias_criticos': anomalias_report['criticos'],
        'anomalias_warns':    anomalias_report['warns'],
        'fecha_emision': timezone.now(),
    })

    try:
        from weasyprint import HTML
        pdf = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()
        resp = HttpResponse(pdf, content_type='application/pdf')
        resp['Content-Disposition'] = (
            f'attachment; filename="ejecutivo_{periodo.anio}_{periodo.mes:02d}.pdf"'
        )
        return resp
    except ImportError:
        return HttpResponse(html, content_type='text/html; charset=utf-8')
