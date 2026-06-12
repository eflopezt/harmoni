"""
Revisión pre-aprobación del período (variance review).

Patrón estándar de payroll moderno (Deel/Rippling/Gusto): antes de aprobar,
el admin ve UNA pantalla con:
  - el monto que va a salir de la cuenta (cifra hero),
  - la variación por concepto vs el mes anterior (Δ y Δ%),
  - flags por trabajador (del detector de anomalías) que puede descartar
    explícitamente — advertencia ≠ bloqueo, pero queda registro de quién
    descartó qué (PeriodoNomina.flags_descartados),
  - el resumen en lenguaje humano (qué cobran, qué se retiene, qué paga
    la empresa) y los parámetros legales congelados del período.

URLs:
  /nominas/periodos/<pk>/revision/            (GET)
  /nominas/periodos/<pk>/revision/descartar/  (POST flag_key)
"""
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Avg, Count, Max, Min, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import LineaNomina, PeriodoNomina
from .views_anomalias import detectar_anomalias_periodo

solo_admin = user_passes_test(lambda u: u.is_superuser)

# Umbral de resaltado en la tabla de variación por concepto
PCT_VARIACION_CONCEPTO = Decimal('15.00')


def _totales_por_concepto(periodo):
    """Suma de LineaNomina por concepto del período → dict codigo → row."""
    qs = (
        LineaNomina.objects
        .filter(registro__periodo=periodo)
        .values('concepto__codigo', 'concepto__nombre', 'concepto__tipo')
        .annotate(total=Sum('monto'), n=Count('registro_id', distinct=True))
    )
    return {
        r['concepto__codigo']: {
            'codigo': r['concepto__codigo'],
            'nombre': r['concepto__nombre'],
            'tipo': r['concepto__tipo'],
            'total': r['total'] or Decimal('0'),
            'n': r['n'],
        }
        for r in qs
    }


def variance_conceptos(periodo, anterior):
    """
    Tabla de variación por concepto: actual vs anterior, Δ y Δ%.
    Incluye conceptos que aparecen o desaparecen entre meses.
    """
    act = _totales_por_concepto(periodo)
    ant = _totales_por_concepto(anterior) if anterior else {}

    rows = []
    for codigo in set(act) | set(ant):
        a = act.get(codigo)
        b = ant.get(codigo)
        total_act = a['total'] if a else Decimal('0')
        total_ant = b['total'] if b else Decimal('0')
        delta = total_act - total_ant
        if total_ant:
            pct = delta / total_ant * Decimal('100')
        else:
            pct = Decimal('100') if total_act else Decimal('0')
        base = a or b
        resaltar = bool(anterior) and (
            abs(pct) >= PCT_VARIACION_CONCEPTO or a is None or b is None
        )
        rows.append({
            'codigo': codigo,
            'nombre': base['nombre'],
            'tipo': base['tipo'],
            'total_act': total_act,
            'total_ant': total_ant,
            'n_act': a['n'] if a else 0,
            'n_ant': b['n'] if b else 0,
            'delta': delta,
            'pct': pct,
            'nuevo': b is None,
            'desaparecio': a is None,
            'resaltar': resaltar,
        })

    rows.sort(key=lambda r: (0 if r['resaltar'] else 1, -abs(r['delta'])))
    return rows


def _flag_key(anomalia):
    reg = anomalia.get('registro')
    pid = getattr(reg, 'personal_id', None) or 'NA'
    return f"{anomalia['tipo']}:{pid}"


@login_required
@solo_admin
def periodo_revision(request, pk):
    """Pantalla de revisión previa a aprobar el período."""
    periodo = get_object_or_404(PeriodoNomina, pk=pk)
    report = detectar_anomalias_periodo(periodo)
    anterior = report['anterior']

    descartados = periodo.flags_descartados or {}
    flags = []
    pendientes = 0
    for a in report['anomalias']:
        key = _flag_key(a)
        desc = descartados.get(key)
        if not desc:
            pendientes += 1
        flags.append({**a, 'key': key, 'descartado': desc})

    stats = periodo.registros.aggregate(
        n=Count('id'),
        neto_prom=Avg('neto_a_pagar'),
        neto_min=Min('neto_a_pagar'),
        neto_max=Max('neto_a_pagar'),
        essalud=Sum('aporte_essalud'),
    )
    retenciones = (periodo.total_bruto or 0) - (periodo.total_neto or 0)

    return render(request, 'nominas/periodo_revision.html', {
        'periodo': periodo,
        'anterior': anterior,
        'variance': variance_conceptos(periodo, anterior),
        'flags': flags,
        'flags_pendientes': pendientes,
        'stats': stats,
        'retenciones': retenciones,
        'parametros': periodo.parametros_snapshot or {},
        'puede_aprobar': periodo.estado == 'CALCULADO',
        'delta_neto': (periodo.total_neto or 0) - (anterior.total_neto or 0) if anterior else None,
    })


@login_required
@solo_admin
@require_POST
def periodo_flag_descartar(request, pk):
    """Descarta (o restaura) un flag de la revisión. Queda registro de quién."""
    periodo = get_object_or_404(PeriodoNomina, pk=pk)
    if periodo.estado in ('CERRADO', 'ANULADO'):
        messages.error(request, 'El período ya está cerrado.')
        return redirect('nominas_periodo_revision', pk=pk)

    key = (request.POST.get('flag_key') or '').strip()
    if not key:
        return redirect('nominas_periodo_revision', pk=pk)

    descartados = dict(periodo.flags_descartados or {})
    if key in descartados:
        # Restaurar: vuelve a quedar pendiente
        descartados.pop(key)
        messages.info(request, 'Flag restaurado — vuelve a quedar pendiente de revisión.')
    else:
        descartados[key] = {
            'por': request.user.get_username(),
            'en': timezone.now().isoformat(),
            'mensaje': (request.POST.get('mensaje') or '')[:300],
        }
        messages.success(request, 'Flag descartado. Queda registrado en la auditoría del período.')

    periodo.flags_descartados = descartados
    periodo.save(update_fields=['flags_descartados'])
    return redirect('nominas_periodo_revision', pk=pk)
