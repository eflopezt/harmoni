"""
Vistas del módulo Tareo — Dashboard principal.
"""
import calendar
from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Count, Q, Sum, F
from django.shortcuts import render

from asistencia.views._common import solo_admin, _qs_staff_dedup


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------

@login_required
@solo_admin
def tareo_dashboard(request):
    """Panel principal del módulo Tareo (solo admin)."""
    from personal.models import Personal
    from asistencia.models import BancoHoras, RegistroTareo, TareoImportacion

    # ── Selector de mes ──────────────────────────────────────────
    MESES_ES = ['Enero','Febrero','Marzo','Abril','Mayo','Junio',
                'Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre']
    MESES = [(i + 1, nombre) for i, nombre in enumerate(MESES_ES)]

    hoy = date.today()
    anio_sel = int(request.GET.get('anio', hoy.year))
    mes_sel  = int(request.GET.get('mes',  hoy.month))
    mes_nombre = MESES_ES[mes_sel - 1]

    _anios_banco = set(BancoHoras.objects.values_list('periodo_anio', flat=True))
    _anios_reg   = set(RegistroTareo.objects.values_list('fecha__year', flat=True))
    anios_disponibles = sorted(_anios_banco | _anios_reg | {hoy.year}, reverse=True)

    # ── Stats de Personal ────────────────────────────────────────
    total_staff = Personal.objects.filter(grupo_tareo='STAFF', estado='Activo').count()
    total_rco   = Personal.objects.filter(grupo_tareo='RCO',   estado='Activo').count()

    # ── Mes calendario (para stats de display) ───────────────────
    mes_ini = date(anio_sel, mes_sel, 1)
    mes_fin = date(anio_sel, mes_sel, calendar.monthrange(anio_sel, mes_sel)[1])

    # Ciclo HE (referencia: 21 mes anterior → fin del mes) ────────
    if mes_sel == 1:
        mes_ant, anio_ant = 12, anio_sel - 1
    else:
        mes_ant, anio_ant = mes_sel - 1, anio_sel
    ciclo_ini = date(anio_ant, mes_ant, 21)
    ciclo_fin = mes_fin

    # Stats filtrados por mes calendario (no ciclo HE)
    # STAFF: deduplicado por (personal, fecha) → importación más reciente
    # RCO: sin duplicados (solo tiene una importación por período)
    qs_staff_dedup = _qs_staff_dedup(mes_ini, mes_fin)
    qs_rco = RegistroTareo.objects.filter(grupo='RCO', fecha__gte=mes_ini, fecha__lte=mes_fin)

    # Excluir registros post-cese y pre-ingreso
    qs_staff_valid = qs_staff_dedup.exclude(
        personal__fecha_cese__isnull=False,
        fecha__gt=models.F('personal__fecha_cese')
    ).exclude(
        personal__fecha_alta__isnull=False,
        fecha__lt=models.F('personal__fecha_alta')
    )
    qs_rco_valid = qs_rco.exclude(
        personal__fecha_cese__isnull=False,
        fecha__gt=models.F('personal__fecha_cese')
    ).exclude(
        personal__fecha_alta__isnull=False,
        fecha__lt=models.F('personal__fecha_alta')
    )
    # Faltas reales: excluir domingos LOCAL (son DS, no faltas)
    faltas_staff = qs_staff_valid.filter(
        codigo_dia__in=['F', 'FA', 'LSG']
    ).exclude(
        condicion__in=['LOCAL', 'LIMA', ''], dia_semana=6
    ).count()
    faltas_rco = qs_rco_valid.filter(
        codigo_dia__in=['F', 'FA', 'LSG']
    ).exclude(
        condicion__in=['LOCAL', 'LIMA', ''], dia_semana=6
    ).count()

    staff_stats = qs_staff_valid.aggregate(
        personas    = Count('dni', distinct=True),
        he_25       = Sum('he_25'),
        he_35       = Sum('he_35'),
        he_100      = Sum('he_100'),
        ss_count    = Count('id', filter=Q(codigo_dia='SS')),
    )
    rco_stats = qs_rco_valid.aggregate(
        personas    = Count('dni', distinct=True),
        he_25       = Sum('he_25'),
        he_35       = Sum('he_35'),
        he_100      = Sum('he_100'),
        ss_count    = Count('id', filter=Q(codigo_dia='SS')),
    )

    def _d(v): return v or Decimal('0')
    stats = {
        'staff_personas':  staff_stats['personas'] or 0,
        'rco_personas':    rco_stats['personas']   or 0,
        'he_25_total':     _d(staff_stats['he_25'])  + _d(rco_stats['he_25']),
        'he_35_total':     _d(staff_stats['he_35'])  + _d(rco_stats['he_35']),
        'he_100_total':    _d(staff_stats['he_100']) + _d(rco_stats['he_100']),
        'faltas':          faltas_staff + faltas_rco,
        'ss_count':        (staff_stats['ss_count'] or 0) + (rco_stats['ss_count'] or 0),
        'total_registros': qs_staff_dedup.count() + qs_rco.count(),
    }
    stats['he_25_total']  = stats['he_25_total']  or Decimal('0')
    stats['he_35_total']  = stats['he_35_total']  or Decimal('0')
    stats['he_100_total'] = stats['he_100_total'] or Decimal('0')
    stats['he_total'] = stats['he_25_total'] + stats['he_35_total'] + stats['he_100_total']
    stats['total_staff_bd'] = total_staff
    # Si Personal no tiene grupo_tareo='RCO' configurado, usar conteo de RegistroTareo
    stats['total_rco_bd'] = total_rco if total_rco > 0 else (stats['rco_personas'] or 0)

    # ── Banco de horas del mes seleccionado ──────────────────────
    banco_qs = BancoHoras.objects.filter(periodo_anio=anio_sel, periodo_mes=mes_sel)
    banco_stats = banco_qs.aggregate(
        personas      = Count('personal', distinct=True),
        saldo_total   = Sum('saldo_horas'),
        acumulado_25  = Sum('he_25_acumuladas'),
        acumulado_35  = Sum('he_35_acumuladas'),
        acumulado_100 = Sum('he_100_acumuladas'),
        compensado    = Sum('he_compensadas'),
    )

    ultimas_imports = TareoImportacion.objects.order_by('-creado_en')[:8]

    context = {
        'titulo': 'Módulo Tareo',
        'anio_sel': anio_sel,
        'mes_sel': mes_sel,
        'mes_nombre': mes_nombre,
        'meses': MESES,
        'anios_disponibles': anios_disponibles,
        'stats': stats,
        'banco_stats': banco_stats,
        'ultimas_imports': ultimas_imports,
        'mes_ini': mes_ini,
        'mes_fin': mes_fin,
        'ciclo_ini': ciclo_ini,
        'ciclo_fin': ciclo_fin,
    }
    return render(request, 'asistencia/dashboard.html', context)
