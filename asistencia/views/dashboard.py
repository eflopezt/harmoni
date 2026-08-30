"""
Vistas del módulo Tareo — Dashboard principal.
"""
import calendar
from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Count, Q, Sum
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

    # Ciclo HE según ConfiguracionSistema.dia_corte_planilla
    from asistencia.models import ConfiguracionSistema as _CS
    _cfg = _CS.objects.first()
    if _cfg:
        ciclo_ini, ciclo_fin = _cfg.get_ciclo_he(anio_sel, mes_sel)
    else:
        if mes_sel == 1:
            mes_ant, anio_ant = 12, anio_sel - 1
        else:
            mes_ant, anio_ant = mes_sel - 1, anio_sel
        ciclo_ini = date(anio_ant, mes_ant, 22)
        ciclo_fin = date(anio_sel, mes_sel, 21)

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

    # ── Alertas de cierre de planilla ────────────────────────────
    alertas = []

    # 1. SS (sin salida) en el mes
    if stats['ss_count'] > 0:
        alertas.append({
            'tipo': 'danger',
            'icono': 'fa-sign-out-alt',
            'titulo': f'{stats["ss_count"]} registros Sin Salida (SS)',
            'detalle': 'Marcaciones con entrada pero sin salida — verificar antes de cerrar planilla.',
            'url': f'/asistencia/calendario/?mes={mes_sel}&anio={anio_sel}',
        })

    # 2. HE elevadas (>50h en el mes) — solo RCO
    he_elevadas = list(
        qs_rco_valid
        .values('nombre_archivo', 'dni')
        .annotate(total_he=Sum('he_25') + Sum('he_35') + Sum('he_100'))
        .filter(total_he__gt=50)
        .order_by('-total_he')[:5]
    )
    if he_elevadas:
        nombres = ', '.join(r['nombre_archivo'].split()[0] for r in he_elevadas[:3])
        alertas.append({
            'tipo': 'warning',
            'icono': 'fa-clock',
            'titulo': f'{len(he_elevadas)} trabajadores con HE > 50h',
            'detalle': f'RCO con horas extra elevadas: {nombres}{"..." if len(he_elevadas) > 3 else ""}. Verificar autorización.',
            'url': f'/asistencia/exportar/horas-rco/?mes={mes_sel}&anio={anio_sel}',
        })

    # 3. Contratos por vencer (próximos 30 días)
    from datetime import timedelta
    contratos_vencer = Personal.objects.filter(
        estado='Activo',
        fecha_fin_contrato__isnull=False,
        fecha_fin_contrato__gte=hoy,
        fecha_fin_contrato__lte=hoy + timedelta(days=30),
    ).count()
    if contratos_vencer:
        alertas.append({
            'tipo': 'warning',
            'icono': 'fa-file-contract',
            'titulo': f'{contratos_vencer} contratos vencen en 30 días',
            'detalle': 'Contratos a plazo fijo próximos al vencimiento. Renovar o preparar cese.',
            'url': '/personal/?filtro=contratos_por_vencer',
        })

    # 4. Personal activo sin registros en el mes (posibles omisiones)
    pids_con_registro = set(
        qs_staff_dedup.values_list('personal_id', flat=True)
    ) | set(qs_rco.values_list('personal_id', flat=True))
    pids_activos = set(Personal.objects.filter(
        estado='Activo',
        fecha_alta__lte=mes_fin,
    ).filter(
        Q(fecha_cese__isnull=True) | Q(fecha_cese__gte=mes_ini)
    ).values_list('id', flat=True))
    sin_registro = len(pids_activos - pids_con_registro)
    if sin_registro > 5:  # threshold para evitar false positives
        alertas.append({
            'tipo': 'info',
            'icono': 'fa-user-slash',
            'titulo': f'{sin_registro} activos sin tareo en {mes_nombre}',
            'detalle': 'Personal activo sin ningún registro en el período. Puede ser normal (ingreso tardío, vacaciones) o indica importación incompleta.',
            'url': f'/asistencia/exportar/validacion/?mes={mes_sel}&anio={anio_sel}',
        })

    context = {
        'titulo': 'Módulo Asistencia',
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
        'alertas': alertas,
        'contratos_vencer': contratos_vencer,
    }
    return render(request, 'asistencia/dashboard.html', context)
