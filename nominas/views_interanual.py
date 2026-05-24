"""
Comparativa Interanual — Mismo Mes vs Año Anterior.

Vista que compara las métricas del mes actual contra el mismo mes
hace 12 meses (year-over-year, YoY).

Útil para:
- Analizar crecimiento real del payroll
- Detectar estacionalidades (mayo, noviembre, julio, diciembre tienen picos)
- Justificar presupuesto / planificación cash flow

URL: /nominas/interanual/?anio=2026&mes=5
"""
from decimal import Decimal

from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Avg, Count, Sum
from django.shortcuts import render
from django.utils import timezone


solo_admin = user_passes_test(lambda u: u.is_superuser)


def _delta_pct(antes: Decimal, despues: Decimal):
    if not antes or antes == 0:
        return None
    return float((despues - antes) / antes * Decimal('100'))


def _agregar(periodo):
    if not periodo:
        return None
    agg = periodo.registros.aggregate(
        trab=Count('id'),
        neto=Sum('neto_a_pagar'),
        bruto=Sum('total_ingresos'),
        desc=Sum('total_descuentos'),
        essalud=Sum('aporte_essalud'),
        avg_neto=Avg('neto_a_pagar'),
    )
    return {
        'periodo':    periodo,
        'trab':       agg['trab'] or 0,
        'neto':       agg['neto'] or Decimal('0'),
        'bruto':      agg['bruto'] or Decimal('0'),
        'desc':       agg['desc'] or Decimal('0'),
        'essalud':    agg['essalud'] or Decimal('0'),
        'avg_neto':   agg['avg_neto'] or Decimal('0'),
    }


@login_required
@solo_admin
def comparativo_interanual(request):
    """Mes actual vs mismo mes año anterior."""
    from .models import PeriodoNomina

    hoy = timezone.localdate()
    anio = int(request.GET.get('anio', hoy.year))
    mes = int(request.GET.get('mes', hoy.month))

    periodo_actual = PeriodoNomina.objects.filter(
        tipo='REGULAR', anio=anio, mes=mes,
        estado__in=['CALCULADO', 'APROBADO', 'CERRADO'],
    ).first()
    periodo_yoy = PeriodoNomina.objects.filter(
        tipo='REGULAR', anio=anio - 1, mes=mes,
        estado__in=['CALCULADO', 'APROBADO', 'CERRADO'],
    ).first()

    actual = _agregar(periodo_actual)
    yoy = _agregar(periodo_yoy)

    # Deltas
    deltas = None
    if actual and yoy:
        deltas = {
            'trab':    actual['trab'] - yoy['trab'],
            'trab_pct': _delta_pct(Decimal(yoy['trab']), Decimal(actual['trab'])) if yoy['trab'] else None,
            'neto':    actual['neto'] - yoy['neto'],
            'neto_pct': _delta_pct(yoy['neto'], actual['neto']),
            'bruto':   actual['bruto'] - yoy['bruto'],
            'bruto_pct': _delta_pct(yoy['bruto'], actual['bruto']),
            'avg_neto':    actual['avg_neto'] - yoy['avg_neto'],
            'avg_neto_pct': _delta_pct(yoy['avg_neto'], actual['avg_neto']),
            'essalud': actual['essalud'] - yoy['essalud'],
            'essalud_pct': _delta_pct(yoy['essalud'], actual['essalud']),
        }

    # Lista años disponibles (para el selector)
    anios_disp = list(
        PeriodoNomina.objects.filter(tipo='REGULAR')
        .values_list('anio', flat=True).distinct().order_by('-anio')
    )

    return render(request, 'nominas/comparativo_interanual.html', {
        'anio':           anio,
        'mes':            mes,
        'actual':         actual,
        'yoy':            yoy,
        'deltas':         deltas,
        'anios_disp':     anios_disp,
        'meses':          [(i, ['','Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'][i]) for i in range(1,13)],
    })
