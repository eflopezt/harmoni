"""
Analytics & People Intelligence — Vistas.

Dashboard ejecutivo con KPIs en tiempo real y tendencias históricas.
"""
import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Avg, Count, Max, Min, Q, Sum
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.contrib import messages
from django.views.decorators.http import require_POST, require_GET

from .models import KPISnapshot, AlertaRRHH
from .services import generar_snapshot, generar_alertas

solo_admin = user_passes_test(lambda u: u.is_superuser, login_url='login')


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder que maneja Decimal."""
    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        return super().default(o)


# ─────────────────────────────────────────────────
# DASHBOARD EJECUTIVO
# ─────────────────────────────────────────────────

@solo_admin
def dashboard(request):
    """Dashboard ejecutivo de RRHH con KPIs y tendencias."""
    from personal.models import Personal, Area

    # ── KPI en tiempo real ──
    activos = Personal.objects.filter(estado='Activo')
    total = activos.count()
    staff = activos.filter(grupo_tareo='STAFF').count()
    rco = activos.filter(grupo_tareo='RCO').count()

    hoy = date.today()
    inicio_mes = date(hoy.year, hoy.month, 1)

    altas_mes = Personal.objects.filter(
        fecha_alta__gte=inicio_mes, fecha_alta__lte=hoy).count()
    bajas_mes = Personal.objects.filter(
        fecha_cese__gte=inicio_mes, fecha_cese__lte=hoy, estado='Cesado').count()

    # ── Distribución por área ──
    areas_data = (
        activos
        .values('subarea__area__nombre')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    areas_labels = [a['subarea__area__nombre'] or 'Sin Área' for a in areas_data]
    areas_values = [a['total'] for a in areas_data]

    # ── Tendencia histórica (últimos 12 meses) ──
    snapshots = KPISnapshot.objects.order_by('-periodo')[:12][::-1]
    trend_labels = [s.periodo.strftime('%b %Y') for s in snapshots]
    trend_headcount = [s.total_empleados for s in snapshots]
    trend_staff = [s.empleados_staff for s in snapshots]
    trend_rco = [s.empleados_rco for s in snapshots]
    trend_rotacion = [float(s.tasa_rotacion) for s in snapshots]
    trend_asistencia = [float(s.tasa_asistencia) for s in snapshots]
    trend_he = [float(s.total_he_mes) for s in snapshots]

    # ── Si no hay snapshots, build live 6-month trend ──
    if not snapshots:
        live_labels = []
        live_hc = []
        for i in range(5, -1, -1):
            ref = date(hoy.year, hoy.month, 1) - timedelta(days=i * 30)
            mes_label = ref.strftime('%b %Y')
            count = Personal.objects.filter(
                fecha_alta__lte=ref
            ).exclude(
                fecha_cese__lt=ref
            ).count()
            live_labels.append(mes_label)
            live_hc.append(count)
        trend_labels = live_labels
        trend_headcount = live_hc
        trend_staff = []
        trend_rco = []
        trend_rotacion = []
        trend_asistencia = []
        trend_he = []

    # ── Alertas activas (últimas 5 para widget) ──
    alertas = AlertaRRHH.objects.filter(estado='ACTIVA').order_by('-creado_en')[:5]
    total_alertas_activas = AlertaRRHH.objects.filter(estado='ACTIVA').count()

    # ── Snapshots: actual y anterior para deltas ──
    snapshots_recientes = KPISnapshot.objects.order_by('-periodo')[:2]
    ultimo_snapshot = snapshots_recientes[0] if snapshots_recientes else None
    penultimo_snapshot = snapshots_recientes[1] if len(snapshots_recientes) > 1 else None

    # ── Tasa asistencia actual (mes en curso) ──
    tasa_asistencia_actual = None
    try:
        from asistencia.models import RegistroTareo
        registros_mes = RegistroTareo.objects.filter(
            fecha__gte=inicio_mes, fecha__lte=hoy)
        total_reg = registros_mes.count()
        asistidos = registros_mes.exclude(
            codigo_dia__in=['F', 'FALTA', 'SIN_MARCACION', 'FERIADO']).count()
        if total_reg > 0:
            tasa_asistencia_actual = round(asistidos / total_reg * 100, 1)
    except Exception:
        pass

    # ── People Risk summary ──
    hoy_60 = hoy + timedelta(days=60)
    contratos_vencen = Personal.objects.filter(
        estado='Activo',
        tipo_contrato='PLAZO_FIJO',
        fecha_fin_contrato__gte=hoy,
        fecha_fin_contrato__lte=hoy_60,
    ).count()

    # Ausentismo crítico (faltas > 3 en el mes): best-effort
    ausentismo_critico = 0
    try:
        from asistencia.models import RegistroTareo
        from django.db.models import Count as DjCount
        faltas_por_persona = (
            RegistroTareo.objects.filter(
                fecha__gte=inicio_mes,
                fecha__lte=hoy,
                codigo_dia__in=['F', 'FALTA'],
            )
            .values('personal_id')
            .annotate(faltas=DjCount('id'))
            .filter(faltas__gt=3)
        )
        ausentismo_critico = faltas_por_persona.count()
    except Exception:
        pass

    # High risk count (simplified for widget — full calc in attrition_risk view)
    riesgo_alto = 0
    try:
        riesgo_alto = Personal.objects.filter(
            estado='Activo',
            tipo_contrato='PLAZO_FIJO',
            fecha_fin_contrato__gte=hoy,
            fecha_fin_contrato__lte=hoy_60,
        ).count()
    except Exception:
        pass

    # ── Alertas activas enriquecidas (top 5, por severidad desc luego fecha desc) ──
    # Orden manual: CRITICAL > WARN > INFO usando Case/When
    top_alertas = []
    try:
        from django.db.models import Case, IntegerField, When
        top_alertas = list(
            AlertaRRHH.objects.filter(estado='ACTIVA').annotate(
                sev_order=Case(
                    When(severidad='CRITICAL', then=0),
                    When(severidad='WARN', then=1),
                    When(severidad='INFO', then=2),
                    default=3,
                    output_field=IntegerField(),
                )
            ).order_by('sev_order', '-creado_en')[:5]
        )
    except Exception:
        pass

    # ── Módulos resumen (señales por módulo) ──
    modulos_resumen = []

    # Vacaciones pendientes
    try:
        from vacaciones.models import SolicitudVacacion
        vac_count = SolicitudVacacion.objects.filter(estado='PENDIENTE').count()
    except Exception:
        vac_count = 0
    modulos_resumen.append({
        'label': 'Vacaciones pendientes',
        'value': vac_count,
        'icon': 'fas fa-umbrella-beach',
        'color': '#0891b2',
        'url': 'vacaciones_panel',
    })

    # Permisos pendientes
    try:
        from vacaciones.models import SolicitudPermiso
        per_count = SolicitudPermiso.objects.filter(estado='PENDIENTE').count()
    except Exception:
        per_count = 0
    modulos_resumen.append({
        'label': 'Permisos pendientes',
        'value': per_count,
        'icon': 'fas fa-file-alt',
        'color': '#7c3aed',
        'url': 'permisos_panel',
    })

    # Préstamos activos
    try:
        from prestamos.models import Prestamo
        pre_count = Prestamo.objects.filter(estado='EN_CURSO').count()
    except Exception:
        pre_count = 0
    modulos_resumen.append({
        'label': 'Préstamos activos',
        'value': pre_count,
        'icon': 'fas fa-hand-holding-usd',
        'color': '#d97706',
        'url': 'prestamos_panel',
    })

    # Capacitaciones en curso
    try:
        from capacitaciones.models import Capacitacion
        cap_count = Capacitacion.objects.filter(estado='EN_CURSO').count()
    except Exception:
        cap_count = 0
    modulos_resumen.append({
        'label': 'Capacitaciones en curso',
        'value': cap_count,
        'icon': 'fas fa-chalkboard-teacher',
        'color': '#059669',
        'url': 'capacitaciones_panel',
    })

    # Evaluaciones pendientes
    try:
        from evaluaciones.models import Evaluacion
        eva_count = Evaluacion.objects.filter(estado='PENDIENTE').count()
    except Exception:
        eva_count = 0
    modulos_resumen.append({
        'label': 'Evaluaciones pendientes',
        'value': eva_count,
        'icon': 'fas fa-star-half-alt',
        'color': '#db2777',
        'url': 'evaluaciones_dashboard',
    })

    # Vacantes abiertas
    try:
        from reclutamiento.models import Vacante
        vac_open_count = Vacante.objects.filter(estado='PUBLICADA').count()
    except Exception:
        vac_open_count = 0
    modulos_resumen.append({
        'label': 'Vacantes abiertas',
        'value': vac_open_count,
        'icon': 'fas fa-briefcase',
        'color': '#2563eb',
        'url': 'reclutamiento_dashboard',
    })

    # ── Próximos cumpleaños (personal activo, próximos 30 días) ──
    proximos_cumpleanios = []
    try:
        from django.db.models.functions import ExtractMonth, ExtractDay
        hoy_30 = hoy + timedelta(days=30)
        activos_con_nacimiento = Personal.objects.filter(
            estado='Activo',
            fecha_nacimiento__isnull=False,
        )
        candidatos = []
        for p in activos_con_nacimiento.only('apellidos_nombres', 'fecha_nacimiento'):
            fn = p.fecha_nacimiento
            # Calcular próximo cumpleaños en el año actual o siguiente
            try:
                proximo = fn.replace(year=hoy.year)
            except ValueError:
                # 29 Feb en año no bisiesto
                proximo = fn.replace(year=hoy.year, day=28)
            if proximo < hoy:
                try:
                    proximo = fn.replace(year=hoy.year + 1)
                except ValueError:
                    proximo = fn.replace(year=hoy.year + 1, day=28)
            dias = (proximo - hoy).days
            if 0 <= dias <= 30:
                candidatos.append({
                    'nombre': p.apellidos_nombres,
                    'fecha_cumple': proximo,
                    'dias_para_cumple': dias,
                })
        candidatos.sort(key=lambda x: x['dias_para_cumple'])
        proximos_cumpleanios = candidatos[:5]
    except Exception:
        pass

    context = {
        'total_empleados': total,
        'empleados_staff': staff,
        'empleados_rco': rco,
        'altas_mes': altas_mes,
        'bajas_mes': bajas_mes,
        'areas_labels': json.dumps(areas_labels),
        'areas_values': json.dumps(areas_values),
        'trend_labels': json.dumps(trend_labels),
        'trend_headcount': json.dumps(trend_headcount),
        'trend_staff': json.dumps(trend_staff),
        'trend_rco': json.dumps(trend_rco),
        'trend_rotacion': json.dumps(trend_rotacion),
        'trend_asistencia': json.dumps(trend_asistencia),
        'trend_he': json.dumps(trend_he, cls=DecimalEncoder),
        'alertas': alertas,
        'total_alertas_activas': total_alertas_activas,
        'ultimo_snapshot': ultimo_snapshot,
        'penultimo_snapshot': penultimo_snapshot,
        'tasa_asistencia_actual': tasa_asistencia_actual,
        'total_areas': len(areas_labels),
        # People Risk
        'riesgo_alto': riesgo_alto,
        'contratos_vencen': contratos_vencen,
        'ausentismo_critico': ausentismo_critico,
        # Nuevas señales por módulo y alertas enriquecidas
        'top_alertas': top_alertas,
        'modulos_resumen': modulos_resumen,
        'proximos_cumpleanios': proximos_cumpleanios,
    }
    return render(request, 'analytics/dashboard.html', context)


# ─────────────────────────────────────────────────
# HEADCOUNT DETALLADO
# ─────────────────────────────────────────────────

@solo_admin
def headcount(request):
    """Vista detallada de headcount con pirámide, tendencia y género."""
    from personal.models import Personal, Area

    activos = Personal.objects.filter(estado='Activo')
    hoy = date.today()
    inicio_mes = date(hoy.year, hoy.month, 1)

    # ── Por área y tipo ──
    areas = Area.objects.filter(activa=True).order_by('nombre')
    total = activos.count()
    area_data = []
    for area in areas:
        staff = activos.filter(subarea__area=area, grupo_tareo='STAFF').count()
        rco = activos.filter(subarea__area=area, grupo_tareo='RCO').count()
        if staff + rco > 0:
            area_data.append({
                'nombre': area.nombre,
                'staff': staff,
                'rco': rco,
                'total': staff + rco,
            })

    # ── Antigüedad ──
    antiguedad = {
        'menos_1': activos.filter(fecha_alta__gte=hoy - timedelta(days=365)).count(),
        '1_3': activos.filter(
            fecha_alta__lt=hoy - timedelta(days=365),
            fecha_alta__gte=hoy - timedelta(days=365 * 3)
        ).count(),
        '3_5': activos.filter(
            fecha_alta__lt=hoy - timedelta(days=365 * 3),
            fecha_alta__gte=hoy - timedelta(days=365 * 5)
        ).count(),
        'mas_5': activos.filter(fecha_alta__lt=hoy - timedelta(days=365 * 5)).count(),
    }

    # ── Distribución por género ──
    genero_m = activos.filter(sexo='M').count()
    genero_f = activos.filter(sexo='F').count()
    genero_nd = total - genero_m - genero_f

    # ── Tendencia mensual últimos 12 meses (live query) ──
    monthly_labels = []
    monthly_hc = []
    monthly_staff = []
    monthly_rco = []
    altas_list = []
    bajas_list = []

    for i in range(11, -1, -1):
        # Primer día del mes i meses atrás
        ref_month = date(hoy.year, hoy.month, 1) - timedelta(days=i * 30)
        ref_month = date(ref_month.year, ref_month.month, 1)
        # Último día de ese mes
        if ref_month.month == 12:
            next_month = date(ref_month.year + 1, 1, 1)
        else:
            next_month = date(ref_month.year, ref_month.month + 1, 1)
        last_day = next_month - timedelta(days=1)

        hc = Personal.objects.filter(
            fecha_alta__lte=last_day
        ).exclude(
            fecha_cese__lt=ref_month
        ).count()
        st = Personal.objects.filter(
            fecha_alta__lte=last_day,
            grupo_tareo='STAFF'
        ).exclude(
            fecha_cese__lt=ref_month
        ).count()
        rc = Personal.objects.filter(
            fecha_alta__lte=last_day,
            grupo_tareo='RCO'
        ).exclude(
            fecha_cese__lt=ref_month
        ).count()
        altas = Personal.objects.filter(
            fecha_alta__gte=ref_month,
            fecha_alta__lte=last_day
        ).count()
        bajas = Personal.objects.filter(
            fecha_cese__gte=ref_month,
            fecha_cese__lte=last_day,
            estado='Cesado'
        ).count()

        monthly_labels.append(ref_month.strftime('%b %Y'))
        monthly_hc.append(hc)
        monthly_staff.append(st)
        monthly_rco.append(rc)
        altas_list.append(altas)
        bajas_list.append(bajas)

    # ── Tasa de Rotación últimos 12 meses ──
    total_altas_12 = sum(altas_list)
    total_bajas_12 = sum(bajas_list)
    promedio_hc = sum(monthly_hc) / len(monthly_hc) if monthly_hc else 1
    tasa_rotacion_anual = round((total_altas_12 + total_bajas_12) / (promedio_hc * 2) * 100, 1) if promedio_hc else 0

    # ── Pirámide de edad (si hay fechas) ──
    piramide_labels = ['<25', '25-34', '35-44', '45-54', '55+']
    piramide_m = [0, 0, 0, 0, 0]
    piramide_f = [0, 0, 0, 0, 0]
    edad_bins = [(0, 24), (25, 34), (35, 44), (45, 54), (55, 999)]
    for idx, (min_age, max_age) in enumerate(edad_bins):
        min_date = hoy - timedelta(days=max_age * 365 + 365)
        max_date = hoy - timedelta(days=min_age * 365)
        qs = activos.filter(fecha_nacimiento__isnull=False,
                            fecha_nacimiento__gte=min_date,
                            fecha_nacimiento__lte=max_date)
        piramide_m[idx] = qs.filter(sexo='M').count()
        piramide_f[idx] = qs.filter(sexo='F').count()

    tiene_edad = any(piramide_m) or any(piramide_f)

    context = {
        'area_data': area_data,
        'total': total,
        'antiguedad': antiguedad,
        'antiguedad_json': json.dumps(antiguedad),
        # Género
        'genero_m': genero_m,
        'genero_f': genero_f,
        'genero_nd': genero_nd,
        # Tendencia
        'monthly_labels': json.dumps(monthly_labels),
        'monthly_hc': json.dumps(monthly_hc),
        'monthly_staff': json.dumps(monthly_staff),
        'monthly_rco': json.dumps(monthly_rco),
        'altas_list': json.dumps(altas_list),
        'bajas_list': json.dumps(bajas_list),
        # Rotación
        'tasa_rotacion_anual': tasa_rotacion_anual,
        'total_altas_12': total_altas_12,
        'total_bajas_12': total_bajas_12,
        # Pirámide
        'piramide_labels': json.dumps(piramide_labels),
        'piramide_m': json.dumps(piramide_m),
        'piramide_f': json.dumps(piramide_f),
        'tiene_edad': tiene_edad,
    }
    return render(request, 'analytics/headcount.html', context)


# ─────────────────────────────────────────────────
# PREDICTIVE INSIGHTS — Análisis predictivo RRHH
# ─────────────────────────────────────────────────

@solo_admin
def predictive_insights(request):
    """
    Página de inteligencia predictiva de RRHH.
    Muestra: predicción de bajas, riesgo por área, compa-ratio, ausentismo histórico,
    señales de riesgo agregadas, y recomendaciones de acción.
    """
    from personal.models import Personal, Area
    from django.db.models import Avg, Count, Q

    hoy = date.today()
    inicio_mes = date(hoy.year, hoy.month, 1)
    hace_6m = hoy - timedelta(days=180)
    hace_1y = hoy - timedelta(days=365)
    en_30d = hoy + timedelta(days=30)
    en_60d = hoy + timedelta(days=60)
    en_90d = hoy + timedelta(days=90)

    activos = Personal.objects.filter(estado='Activo').select_related('subarea', 'subarea__area')
    total_activos = activos.count()

    # ── 1. Predicción de bajas próximos 30 / 60 / 90 días ─────────────────
    contratos_30d = activos.filter(
        tipo_contrato='PLAZO_FIJO',
        fecha_fin_contrato__gte=hoy,
        fecha_fin_contrato__lte=en_30d,
    ).count()
    contratos_60d = activos.filter(
        tipo_contrato='PLAZO_FIJO',
        fecha_fin_contrato__gt=en_30d,
        fecha_fin_contrato__lte=en_60d,
    ).count()
    contratos_90d = activos.filter(
        tipo_contrato='PLAZO_FIJO',
        fecha_fin_contrato__gt=en_60d,
        fecha_fin_contrato__lte=en_90d,
    ).count()

    # Tasa histórica de renovación (bajas 12m / altas 12m)
    bajas_12m = Personal.objects.filter(
        fecha_cese__gte=hoy - timedelta(days=365), estado='Cesado'
    ).count()
    altas_12m = Personal.objects.filter(fecha_alta__gte=hoy - timedelta(days=365)).count()
    tasa_renovacion_pct = round((altas_12m / bajas_12m * 100) if bajas_12m else 100, 0)

    # Predicción probabilística de bajas (contratos_30d × tasa no-renovación histórica)
    tasa_no_renueva = max(0, 1 - (altas_12m / bajas_12m)) if bajas_12m else 0.3
    bajas_pred_30d = round(contratos_30d * tasa_no_renueva)

    # ── 2. Scoring por área ────────────────────────────────────────────────
    # Reutilizamos el mismo scoring de attrition pero agregado por área
    faltas_por_persona = {}
    try:
        from asistencia.models import RegistroTareo
        for row in (
            RegistroTareo.objects
            .filter(fecha__gte=inicio_mes, fecha__lte=hoy,
                    codigo_dia__in=['F', 'FALTA'], personal__isnull=False)
            .values('personal_id').annotate(n=Count('id'))
        ):
            faltas_por_persona[row['personal_id']] = row['n']
    except Exception:
        pass

    con_evaluacion = set()
    try:
        from evaluaciones.models import ResultadoConsolidado
        con_evaluacion = set(
            ResultadoConsolidado.objects
            .filter(fecha_consolidacion__gte=hace_6m)
            .values_list('personal_id', flat=True)
        )
    except Exception:
        pass

    con_capacitacion = set()
    try:
        from capacitaciones.models import AsistenciaCapacitacion
        con_capacitacion = set(
            AsistenciaCapacitacion.objects
            .filter(capacitacion__fecha_inicio__gte=hace_1y, estado__in=['ASISTIO', 'PARCIAL'])
            .values_list('personal_id', flat=True)
        )
    except Exception:
        pass

    bandas_min = {}
    bandas_mid = {}
    try:
        from salarios.models import BandaSalarial
        for banda in BandaSalarial.objects.filter(activa=True):
            k = banda.cargo.strip().lower()
            if k not in bandas_min or banda.minimo < bandas_min[k]:
                bandas_min[k] = float(banda.minimo)
            midpoint = float((banda.minimo + banda.maximo) / 2)
            if k not in bandas_mid:
                bandas_mid[k] = midpoint
    except Exception:
        pass

    # Score por empleado
    emp_scores = {}
    for emp in activos:
        score = 0
        if (emp.tipo_contrato == 'PLAZO_FIJO' and emp.fecha_fin_contrato and
                hoy <= emp.fecha_fin_contrato <= en_60d):
            score += 30
        if faltas_por_persona.get(emp.id, 0) > 3:
            score += 20
        if emp.sueldo_base and emp.cargo:
            bm = bandas_min.get(emp.cargo.strip().lower())
            if bm and float(emp.sueldo_base) < bm:
                score += 15
        if emp.id not in con_evaluacion:
            score += 10
        if emp.id not in con_capacitacion:
            score += 10
        emp_scores[emp.id] = (score, emp)

    # Agrupar por área
    areas = Area.objects.filter(activa=True).order_by('nombre')
    area_riesgo = []
    for area in areas:
        emps_area = [e for _, e in emp_scores.values() if e.subarea and e.subarea.area_id == area.id]
        if not emps_area:
            continue
        total_area = len(emps_area)
        high = sum(1 for e in emps_area if emp_scores[e.id][0] >= 40)
        medium = sum(1 for e in emps_area if 20 <= emp_scores[e.id][0] < 40)
        low = total_area - high - medium
        avg_score = round(sum(emp_scores[e.id][0] for e in emps_area) / total_area, 1)
        area_riesgo.append({
            'area': area.nombre,
            'total': total_area,
            'high': high,
            'medium': medium,
            'low': low,
            'avg_score': avg_score,
            'pct_riesgo': round((high + medium) / total_area * 100, 0),
        })
    area_riesgo.sort(key=lambda x: -x['avg_score'])

    # ── 3. Compa-ratio por área ────────────────────────────────────────────
    compa_ratio_data = []
    for area in areas:
        emps_area = [
            e for _, e in emp_scores.values()
            if e.subarea and e.subarea.area_id == area.id and
            e.sueldo_base and e.cargo and e.cargo.strip().lower() in bandas_mid
        ]
        if not emps_area:
            continue
        ratios = []
        for e in emps_area:
            mid = bandas_mid.get(e.cargo.strip().lower())
            if mid and mid > 0:
                ratios.append(float(e.sueldo_base) / mid * 100)
        if ratios:
            avg_ratio = round(sum(ratios) / len(ratios), 1)
            compa_ratio_data.append({'area': area.nombre, 'ratio': avg_ratio, 'n': len(ratios)})

    # ── 4. Ausentismo por semana (últimas 10 semanas) ──────────────────────
    semanas_labels = []
    semanas_pct = []
    for i in range(9, -1, -1):
        inicio_semana = hoy - timedelta(days=hoy.weekday()) - timedelta(weeks=i)
        fin_semana = inicio_semana + timedelta(days=6)
        try:
            from asistencia.models import RegistroTareo
            total_sem = RegistroTareo.objects.filter(
                fecha__gte=inicio_semana, fecha__lte=fin_semana
            ).count()
            faltas_sem = RegistroTareo.objects.filter(
                fecha__gte=inicio_semana, fecha__lte=fin_semana,
                codigo_dia__in=['F', 'FALTA'],
            ).count()
            pct = round(faltas_sem / total_sem * 100, 1) if total_sem > 0 else 0
        except Exception:
            pct = 0
        semanas_labels.append(inicio_semana.strftime('Sem %d/%m'))
        semanas_pct.append(pct)

    ausentismo_tendencia = 'UP' if len(semanas_pct) >= 2 and semanas_pct[-1] > semanas_pct[-3] else 'DOWN'
    ausentismo_actual = semanas_pct[-1] if semanas_pct else 0

    # ── 5. Señales de alerta compuestas ────────────────────────────────────
    senales = []
    riesgo_total = sum(1 for s, _ in emp_scores.values() if s >= 20)
    riesgo_alto = sum(1 for s, _ in emp_scores.values() if s >= 40)

    if riesgo_alto >= 5:
        senales.append({
            'nivel': 'CRITICO',
            'icono': 'fas fa-user-slash',
            'color': '#dc2626',
            'bg': '#fef2f2',
            'titulo': f'{riesgo_alto} empleados en riesgo alto de fuga',
            'accion': 'Revisar contratos y compensaciones de forma urgente',
            'url': '/analytics/attrition/',
        })
    elif riesgo_alto > 0:
        senales.append({
            'nivel': 'ALTO',
            'icono': 'fas fa-exclamation-triangle',
            'color': '#f59e0b',
            'bg': '#fffbeb',
            'titulo': f'{riesgo_alto} empleados con señales de abandono',
            'accion': 'Programar reuniones 1:1 y revisar motivación',
            'url': '/analytics/attrition/',
        })

    if contratos_30d > 0:
        senales.append({
            'nivel': 'URGENTE',
            'icono': 'fas fa-file-contract',
            'color': '#dc2626',
            'bg': '#fff1f2',
            'titulo': f'{contratos_30d} contrato{"s" if contratos_30d > 1 else ""} vence{"n" if contratos_30d > 1 else ""} en 30 días',
            'accion': 'Decidir renovación o inicio de proceso de cese',
            'url': '/personal/?contratos=vencen',
        })

    if ausentismo_actual > 8:
        senales.append({
            'nivel': 'ALTO',
            'icono': 'fas fa-user-clock',
            'color': '#f59e0b',
            'bg': '#fffbeb',
            'titulo': f'Ausentismo esta semana: {ausentismo_actual}%',
            'accion': 'Identificar causas (clima, salud, desmotivación)',
            'url': '/asistencia/',
        })

    sin_eval_pct = round((1 - len(con_evaluacion) / total_activos) * 100) if total_activos else 0
    if sin_eval_pct > 60:
        senales.append({
            'nivel': 'MEDIO',
            'icono': 'fas fa-star-half-alt',
            'color': '#0891b2',
            'bg': '#f0f9ff',
            'titulo': f'{sin_eval_pct}% de empleados sin evaluación reciente',
            'accion': 'Lanzar ciclo de evaluaciones 360°',
            'url': '/evaluaciones/',
        })

    sin_cap_pct = round((1 - len(con_capacitacion) / total_activos) * 100) if total_activos else 0
    if sin_cap_pct > 50:
        senales.append({
            'nivel': 'BAJO',
            'icono': 'fas fa-graduation-cap',
            'color': '#7c3aed',
            'bg': '#faf5ff',
            'titulo': f'{sin_cap_pct}% sin capacitación en el último año',
            'accion': 'Planificar programa de desarrollo y e-learning',
            'url': '/capacitaciones/',
        })

    # ── 6. Top empleados en riesgo (para tabla) ───────────────────────────
    top_riesgo = sorted(
        [(s, e) for s, e in emp_scores.values() if s >= 20],
        key=lambda x: -x[0]
    )[:15]

    context = {
        # Predicción bajas
        'contratos_30d': contratos_30d,
        'contratos_60d': contratos_60d,
        'contratos_90d': contratos_90d,
        'bajas_pred_30d': bajas_pred_30d,
        'tasa_renovacion_pct': int(tasa_renovacion_pct),
        'bajas_12m': bajas_12m,
        'altas_12m': altas_12m,
        # Riesgo
        'riesgo_total': riesgo_total,
        'riesgo_alto': riesgo_alto,
        'total_activos': total_activos,
        # Por área
        'area_riesgo': area_riesgo,
        'area_riesgo_json': json.dumps(area_riesgo),
        # Compa-ratio
        'compa_ratio_data': compa_ratio_data,
        'compa_ratio_json': json.dumps(compa_ratio_data),
        # Ausentismo
        'semanas_labels_json': json.dumps(semanas_labels),
        'semanas_pct_json': json.dumps(semanas_pct),
        'ausentismo_actual': ausentismo_actual,
        'ausentismo_tendencia': ausentismo_tendencia,
        # Señales
        'senales': senales,
        # Top riesgo
        'top_riesgo': top_riesgo,
    }
    return render(request, 'analytics/predictive_insights.html', context)


# ─────────────────────────────────────────────────
# RIESGO DE ROTACIÓN (ATTRITION RISK)
# ─────────────────────────────────────────────────

@solo_admin
def attrition_risk(request):
    """
    Vista de riesgo de rotación por empleado.
    Scoring basado en reglas: contrato, faltas, sueldo, evaluaciones, capacitaciones.
    """
    from personal.models import Personal

    hoy = date.today()
    inicio_mes = date(hoy.year, hoy.month, 1)
    hace_6m = hoy - timedelta(days=180)
    hace_1y = hoy - timedelta(days=365)
    en_60d = hoy + timedelta(days=60)

    activos = Personal.objects.filter(estado='Activo').select_related('subarea', 'subarea__area')

    # ── Precalcular datos para scoring ──

    # Faltas por persona en el último mes
    faltas_por_persona = {}
    try:
        from asistencia.models import RegistroTareo
        faltas_qs = (
            RegistroTareo.objects.filter(
                fecha__gte=inicio_mes,
                fecha__lte=hoy,
                codigo_dia__in=['F', 'FALTA'],
                personal__isnull=False,
            )
            .values('personal_id')
            .annotate(n=Count('id'))
        )
        for row in faltas_qs:
            faltas_por_persona[row['personal_id']] = row['n']
    except Exception:
        pass

    # Empleados con evaluación reciente (últimos 6 meses)
    con_evaluacion = set()
    try:
        from evaluaciones.models import ResultadoConsolidado
        evals = ResultadoConsolidado.objects.filter(
            fecha_consolidacion__gte=hace_6m
        ).values_list('personal_id', flat=True)
        con_evaluacion = set(evals)
    except Exception:
        pass

    # Empleados con capacitación reciente (último año)
    con_capacitacion = set()
    try:
        from capacitaciones.models import AsistenciaCapacitacion
        caps = AsistenciaCapacitacion.objects.filter(
            capacitacion__fecha_inicio__gte=hace_1y,
            estado__in=['ASISTIO', 'PARCIAL'],
        ).values_list('personal_id', flat=True)
        con_capacitacion = set(caps)
    except Exception:
        pass

    # Bandas salariales mínimas por cargo
    bandas_min = {}
    try:
        from salarios.models import BandaSalarial
        for banda in BandaSalarial.objects.filter(activa=True):
            cargo_key = banda.cargo.strip().lower()
            if cargo_key not in bandas_min or banda.minimo < bandas_min[cargo_key]:
                bandas_min[cargo_key] = float(banda.minimo)
    except Exception:
        pass

    # ── Scoring ──
    results = []
    for emp in activos:
        score = 0
        factores = []

        # +30 si contrato plazo fijo vence en 60 días
        if (emp.tipo_contrato == 'PLAZO_FIJO' and
                emp.fecha_fin_contrato and
                hoy <= emp.fecha_fin_contrato <= en_60d):
            score += 30
            dias_restantes = (emp.fecha_fin_contrato - hoy).days
            factores.append(f'Contrato vence en {dias_restantes}d')

        # +20 si faltas > 3 en el último mes
        faltas = faltas_por_persona.get(emp.id, 0)
        if faltas > 3:
            score += 20
            factores.append(f'{faltas} faltas/mes')

        # +15 si sueldo < mínimo de banda de su cargo
        if emp.sueldo_base and emp.cargo:
            cargo_key = emp.cargo.strip().lower()
            banda_min = bandas_min.get(cargo_key)
            if banda_min and float(emp.sueldo_base) < banda_min:
                score += 15
                factores.append('Sueldo bajo banda')

        # +10 si no tiene evaluación en últimos 6 meses
        if emp.id not in con_evaluacion:
            score += 10
            factores.append('Sin evaluación reciente')

        # +10 si no tiene capacitación en el último año
        if emp.id not in con_capacitacion:
            score += 10
            factores.append('Sin capacitación')

        # Nivel de riesgo
        if score >= 40:
            nivel = 'HIGH'
        elif score >= 20:
            nivel = 'MEDIUM'
        else:
            nivel = 'LOW'

        results.append({
            'emp': emp,
            'score': score,
            'nivel': nivel,
            'factores': factores,
            'area': emp.subarea.area.nombre if emp.subarea and emp.subarea.area else 'Sin área',
        })

    # Ordenar: HIGH primero, luego score desc
    level_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
    results.sort(key=lambda x: (level_order[x['nivel']], -x['score']))

    # Conteos por nivel
    count_high = sum(1 for r in results if r['nivel'] == 'HIGH')
    count_medium = sum(1 for r in results if r['nivel'] == 'MEDIUM')
    count_low = sum(1 for r in results if r['nivel'] == 'LOW')

    # Top 10 para gráfico horizontal
    top10 = results[:10]
    chart_labels = [r['emp'].apellidos_nombres for r in top10]
    chart_scores = [r['score'] for r in top10]
    chart_colors = [
        '#dc2626' if r['nivel'] == 'HIGH' else
        '#f59e0b' if r['nivel'] == 'MEDIUM' else '#16a34a'
        for r in top10
    ]

    context = {
        'results': results,
        'count_high': count_high,
        'count_medium': count_medium,
        'count_low': count_low,
        'total': len(results),
        'chart_labels': json.dumps(chart_labels),
        'chart_scores': json.dumps(chart_scores),
        'chart_colors': json.dumps(chart_colors),
    }
    return render(request, 'analytics/attrition_risk.html', context)


# ─────────────────────────────────────────────────
# ANÁLISIS SALARIAL
# ─────────────────────────────────────────────────

@solo_admin
def salary_analytics(request):
    """Vista de análisis salarial: distribución, brechas, percentiles."""
    from personal.models import Personal, Area

    UIT_2026 = Decimal('5350.00')

    activos_con_sueldo = (
        Personal.objects.filter(estado='Activo', sueldo_base__isnull=False)
        .select_related('subarea', 'subarea__area')
    )

    sueldos = list(activos_con_sueldo.values_list('sueldo_base', flat=True))
    sueldos_float = sorted([float(s) for s in sueldos])
    n = len(sueldos_float)

    # ── KPIs básicos ──
    total_planilla = sum(sueldos_float)
    promedio = total_planilla / n if n else 0
    mediana = sueldos_float[n // 2] if n else 0

    # ── Brecha de género ──
    avg_m = activos_con_sueldo.filter(sexo='M').aggregate(avg=Avg('sueldo_base'))['avg'] or 0
    avg_f = activos_con_sueldo.filter(sexo='F').aggregate(avg=Avg('sueldo_base'))['avg'] or 0
    gap_pct = 0
    if avg_m and avg_f and avg_m > 0:
        gap_pct = round(float((avg_m - avg_f) / avg_m) * 100, 1)

    # ── Distribución por rango (bins) ──
    bins = [
        ('Menos de S/2,000', 0, 2000),
        ('S/2,000 – 3,000', 2000, 3000),
        ('S/3,000 – 5,000', 3000, 5000),
        ('S/5,000 – 8,000', 5000, 8000),
        ('Más de S/8,000', 8000, 99999999),
    ]
    dist_labels = []
    dist_values = []
    for label, lo, hi in bins:
        count = activos_con_sueldo.filter(
            sueldo_base__gte=lo, sueldo_base__lt=hi
        ).count()
        dist_labels.append(label)
        dist_values.append(count)

    # ── Promedio por área ──
    area_avg_qs = (
        activos_con_sueldo
        .values('subarea__area__nombre')
        .annotate(avg=Avg('sueldo_base'), cnt=Count('id'))
        .order_by('-avg')
    )
    area_labels = [r['subarea__area__nombre'] or 'Sin Área' for r in area_avg_qs]
    area_avg_values = [round(float(r['avg']), 2) for r in area_avg_qs]

    # ── Percentiles ──
    def percentil(lst, p):
        if not lst:
            return 0
        idx = int(len(lst) * p / 100)
        idx = min(idx, len(lst) - 1)
        return lst[idx]

    p25 = percentil(sueldos_float, 25)
    p50 = percentil(sueldos_float, 50)
    p75 = percentil(sueldos_float, 75)
    p90 = percentil(sueldos_float, 90)

    # ── Ratio vs UIT ──
    ratio_bins = [
        ('< 1 UIT', 0, float(UIT_2026)),
        ('1 – 2 UIT', float(UIT_2026), float(UIT_2026 * 2)),
        ('2 – 3 UIT', float(UIT_2026 * 2), float(UIT_2026 * 3)),
        ('> 3 UIT', float(UIT_2026 * 3), 99999999),
    ]
    uit_labels = []
    uit_values = []
    for label, lo, hi in ratio_bins:
        count = activos_con_sueldo.filter(
            sueldo_base__gte=lo, sueldo_base__lt=hi
        ).count()
        uit_labels.append(label)
        uit_values.append(count)

    # ── Top 5 / Bottom 5 sueldos (para tabla, no nombres) ──
    top5 = list(activos_con_sueldo.order_by('-sueldo_base')[:5].values(
        'apellidos_nombres', 'cargo', 'sueldo_base', 'subarea__area__nombre'
    ))
    bottom5 = list(activos_con_sueldo.order_by('sueldo_base')[:5].values(
        'apellidos_nombres', 'cargo', 'sueldo_base', 'subarea__area__nombre'
    ))

    context = {
        'n_empleados': n,
        'total_planilla': round(total_planilla, 2),
        'promedio': round(promedio, 2),
        'mediana': round(mediana, 2),
        'avg_m': round(float(avg_m), 2),
        'avg_f': round(float(avg_f), 2),
        'gap_pct': gap_pct,
        'p25': round(p25, 2),
        'p50': round(p50, 2),
        'p75': round(p75, 2),
        'p90': round(p90, 2),
        'uit_2026': float(UIT_2026),
        # JSON para gráficos
        'dist_labels': json.dumps(dist_labels),
        'dist_values': json.dumps(dist_values),
        'area_labels': json.dumps(area_labels),
        'area_avg_values': json.dumps(area_avg_values),
        'uit_labels': json.dumps(uit_labels),
        'uit_values': json.dumps(uit_values),
        # Tablas
        'top5': top5,
        'bottom5': bottom5,
        'percentiles': [
            ('P25', round(p25, 2)),
            ('P50 (Mediana)', round(p50, 2)),
            ('P75', round(p75, 2)),
            ('P90', round(p90, 2)),
        ],
    }
    return render(request, 'analytics/salary_analytics.html', context)


# ─────────────────────────────────────────────────
# API RESUMEN AJAX (para widgets de home)
# ─────────────────────────────────────────────────

@solo_admin
def analytics_resumen_ajax(request):
    """Retorna resumen rápido de KPIs para widgets embebidos en otras páginas."""
    from personal.models import Personal

    hoy = date.today()
    inicio_mes = date(hoy.year, hoy.month, 1)

    activos = Personal.objects.filter(estado='Activo')
    headcount_hoy = activos.count()
    nuevos_mes = Personal.objects.filter(
        fecha_alta__gte=inicio_mes, fecha_alta__lte=hoy
    ).count()
    bajas_mes = Personal.objects.filter(
        fecha_cese__gte=inicio_mes, fecha_cese__lte=hoy,
        estado='Cesado'
    ).count()

    ausentismo_pct = None
    try:
        from asistencia.models import RegistroTareo
        registros = RegistroTareo.objects.filter(
            fecha__gte=inicio_mes, fecha__lte=hoy)
        total_reg = registros.count()
        faltas = registros.filter(codigo_dia__in=['F', 'FALTA']).count()
        if total_reg > 0:
            ausentismo_pct = round(faltas / total_reg * 100, 1)
    except Exception:
        pass

    return JsonResponse({
        'headcount_hoy': headcount_hoy,
        'nuevos_mes': nuevos_mes,
        'bajas_mes': bajas_mes,
        'ausentismo_pct': ausentismo_pct,
    })


# ─────────────────────────────────────────────────
# SNAPSHOTS KPI
# ─────────────────────────────────────────────────

@solo_admin
def snapshots_list(request):
    """Lista de snapshots KPI mensuales."""
    snapshots = KPISnapshot.objects.all()[:24]
    return render(request, 'analytics/snapshots.html', {'snapshots': snapshots})


@solo_admin
def generar_snapshot_view(request):
    """Genera snapshot KPI del mes actual (POST)."""
    if request.method == 'POST':
        hoy = date.today()
        snapshot = generar_snapshot(hoy.year, hoy.month, request.user)
        messages.success(request, f"Snapshot KPI generado para {hoy.strftime('%B %Y')}.")
        return redirect('analytics_snapshots')
    return redirect('analytics_dashboard')


# ─────────────────────────────────────────────────
# ALERTAS
# ─────────────────────────────────────────────────

@solo_admin
def alertas_list(request):
    """Lista de alertas RRHH."""
    estado = request.GET.get('estado', 'ACTIVA')
    alertas = AlertaRRHH.objects.all()
    if estado != 'TODAS':
        alertas = alertas.filter(estado=estado)
    return render(request, 'analytics/alertas.html', {
        'alertas': alertas[:50],
        'estado_filtro': estado,
    })


@solo_admin
def resolver_alerta(request, pk):
    """Marcar alerta como resuelta (POST)."""
    if request.method == 'POST':
        alerta = get_object_or_404(AlertaRRHH, pk=pk)
        alerta.estado = 'RESUELTA'
        alerta.resuelta_por = request.user
        alerta.fecha_resolucion = timezone.now()
        alerta.notas_resolucion = request.POST.get('notas', '')
        alerta.save()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': True})
        messages.success(request, "Alerta marcada como resuelta.")
    return redirect('analytics_alertas')


@solo_admin
def generar_alertas_view(request):
    """Ejecuta generación de alertas (POST)."""
    if request.method == 'POST':
        alertas = generar_alertas()
        messages.success(request, f"Se generaron {len(alertas)} alerta(s) nuevas.")
    return redirect('analytics_alertas')


# ─────────────────────────────────────────────────
# API ENDPOINTS (para gráficos AJAX)
# ─────────────────────────────────────────────────

@solo_admin
def api_kpi_actual(request):
    """Retorna KPIs en tiempo real como JSON."""
    from personal.models import Personal

    activos = Personal.objects.filter(estado='Activo')
    hoy = date.today()
    inicio_mes = date(hoy.year, hoy.month, 1)

    data = {
        'total_empleados': activos.count(),
        'staff': activos.filter(grupo_tareo='STAFF').count(),
        'rco': activos.filter(grupo_tareo='RCO').count(),
        'altas_mes': Personal.objects.filter(
            fecha_alta__gte=inicio_mes).count(),
        'bajas_mes': Personal.objects.filter(
            fecha_cese__gte=inicio_mes, estado='Cesado').count(),
    }
    return JsonResponse(data)


@solo_admin
def ai_dashboard(request):
    """Dashboard ejecutivo con gráficos + análisis IA."""
    from personal.models import Personal, Area

    activos = Personal.objects.filter(estado='Activo')
    total = activos.count()
    staff = activos.filter(grupo_tareo='STAFF').count()
    rco = activos.filter(grupo_tareo='RCO').count()

    hoy = date.today()
    inicio_mes = date(hoy.year, hoy.month, 1)

    altas_mes = Personal.objects.filter(
        fecha_alta__gte=inicio_mes, fecha_alta__lte=hoy).count()
    bajas_mes = Personal.objects.filter(
        fecha_cese__gte=inicio_mes, fecha_cese__lte=hoy, estado='Cesado').count()

    # Distribución por área
    areas_data = (
        activos
        .values('subarea__area__nombre')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    areas_labels = [a['subarea__area__nombre'] or 'Sin Área' for a in areas_data]
    areas_values = [a['total'] for a in areas_data]

    # Tendencia histórica
    snapshots = KPISnapshot.objects.order_by('-periodo')[:12][::-1]
    trend_labels = [s.periodo.strftime('%b %Y') for s in snapshots]
    trend_headcount = [s.total_empleados for s in snapshots]
    trend_rotacion = [float(s.tasa_rotacion) for s in snapshots]
    trend_asistencia = [float(s.tasa_asistencia) for s in snapshots]
    trend_he = [float(s.total_he_mes) for s in snapshots]

    # Antigüedad
    antiguedad = {
        'Menos de 1 año': activos.filter(fecha_alta__gte=hoy - timedelta(days=365)).count(),
        '1-3 años': activos.filter(
            fecha_alta__lt=hoy - timedelta(days=365),
            fecha_alta__gte=hoy - timedelta(days=365 * 3)).count(),
        '3-5 años': activos.filter(
            fecha_alta__lt=hoy - timedelta(days=365 * 3),
            fecha_alta__gte=hoy - timedelta(days=365 * 5)).count(),
        '+5 años': activos.filter(fecha_alta__lt=hoy - timedelta(days=365 * 5)).count(),
    }

    # Género
    genero_m = activos.filter(sexo='M').count()
    genero_f = activos.filter(sexo='F').count()
    genero_otro = total - genero_m - genero_f

    # Distribución etaria
    edad_rangos = {'18-25': 0, '26-35': 0, '36-45': 0, '46-55': 0, '56+': 0}
    con_nacimiento = activos.filter(fecha_nacimiento__isnull=False)
    for p in con_nacimiento.only('fecha_nacimiento'):
        try:
            e = (hoy - p.fecha_nacimiento).days // 365
            if e <= 25:
                edad_rangos['18-25'] += 1
            elif e <= 35:
                edad_rangos['26-35'] += 1
            elif e <= 45:
                edad_rangos['36-45'] += 1
            elif e <= 55:
                edad_rangos['46-55'] += 1
            else:
                edad_rangos['56+'] += 1
        except Exception:
            pass

    # People Risk
    hoy_60 = hoy + timedelta(days=60)
    contratos_vencen = 0
    try:
        contratos_vencen = Personal.objects.filter(
            estado='Activo',
            tipo_contrato='PLAZO_FIJO',
            fecha_fin_contrato__gte=hoy,
            fecha_fin_contrato__lte=hoy_60,
        ).count()
    except Exception:
        pass

    ausentismo_critico = 0
    try:
        from asistencia.models import RegistroTareo
        from django.db.models import Count as DjCount
        ausentismo_critico = (
            RegistroTareo.objects.filter(
                fecha__gte=inicio_mes, fecha__lte=hoy,
                codigo_dia__in=['F', 'FALTA'],
            )
            .values('personal_id')
            .annotate(faltas=DjCount('id'))
            .filter(faltas__gt=3)
        ).count()
    except Exception:
        pass

    # Tasa asistencia mes actual
    tasa_asistencia_actual = None
    try:
        from asistencia.models import RegistroTareo
        registros_mes = RegistroTareo.objects.filter(fecha__gte=inicio_mes, fecha__lte=hoy)
        total_reg = registros_mes.count()
        asistidos = registros_mes.exclude(
            codigo_dia__in=['F', 'FALTA', 'SIN_MARCACION', 'FERIADO']).count()
        if total_reg > 0:
            tasa_asistencia_actual = round(asistidos / total_reg * 100, 1)
    except Exception:
        pass

    # Snapshots para deltas
    snapshots_recientes = KPISnapshot.objects.order_by('-periodo')[:2]
    ultimo_snapshot = snapshots_recientes[0] if snapshots_recientes else None
    penultimo_snapshot = snapshots_recientes[1] if len(snapshots_recientes) > 1 else None

    # Alertas
    total_alertas = AlertaRRHH.objects.filter(estado='ACTIVA').count()
    top_alertas = list(AlertaRRHH.objects.filter(estado='ACTIVA').order_by('-creado_en')[:3])

    context = {
        'total_empleados': total,
        'empleados_staff': staff,
        'empleados_rco': rco,
        'altas_mes': altas_mes,
        'bajas_mes': bajas_mes,
        'areas_labels': json.dumps(areas_labels),
        'areas_values': json.dumps(areas_values),
        'trend_labels': json.dumps(trend_labels),
        'trend_headcount': json.dumps(trend_headcount),
        'trend_rotacion': json.dumps(trend_rotacion),
        'trend_asistencia': json.dumps(trend_asistencia),
        'trend_he': json.dumps(trend_he, cls=DecimalEncoder),
        'antiguedad_labels': json.dumps(list(antiguedad.keys())),
        'antiguedad_values': json.dumps(list(antiguedad.values())),
        # Género y edad
        'genero_m': genero_m,
        'genero_f': genero_f,
        'genero_otro': genero_otro,
        'edad_labels': json.dumps(list(edad_rangos.keys())),
        'edad_values': json.dumps(list(edad_rangos.values())),
        'total_con_nacimiento': con_nacimiento.count(),
        # People Risk
        'contratos_vencen': contratos_vencen,
        'ausentismo_critico': ausentismo_critico,
        'tasa_asistencia_actual': tasa_asistencia_actual,
        'ultimo_snapshot': ultimo_snapshot,
        'penultimo_snapshot': penultimo_snapshot,
        'total_alertas': total_alertas,
        'top_alertas': top_alertas,
    }
    return render(request, 'analytics/ai_dashboard.html', context)


# ─────────────────────────────────────────────────
# DASHBOARD WIDGETS — Gráficos personalizados
# ─────────────────────────────────────────────────

@login_required
@require_GET
def list_widgets(request):
    """Lista los widgets guardados del usuario."""
    from .models import DashboardWidget
    widgets = DashboardWidget.objects.filter(
        user=request.user, activo=True).order_by('posicion', '-creado_en')
    data = [{
        'id': w.id,
        'titulo': w.titulo,
        'chart_type': w.chart_type,
        'data_source': w.data_source,
        'config': w.config_json,
        'posicion': w.posicion,
    } for w in widgets]
    return JsonResponse({'widgets': data})


@login_required
@require_POST
def save_widget(request):
    """Guarda un widget personalizado en el dashboard del usuario."""
    from .models import DashboardWidget
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    titulo = body.get('titulo', 'Gráfico')[:200]
    chart_type = body.get('chart_type', 'bar')[:50]
    data_source = body.get('data_source', 'custom')[:100]
    config = body.get('config', {})

    # Límite: máximo 8 widgets por usuario
    count = DashboardWidget.objects.filter(user=request.user, activo=True).count()
    if count >= 8:
        return JsonResponse({'error': 'Máximo 8 widgets en el dashboard'}, status=400)

    widget = DashboardWidget.objects.create(
        user=request.user,
        titulo=titulo,
        chart_type=chart_type,
        data_source=data_source,
        config_json=config,
        posicion=count,
    )
    return JsonResponse({'ok': True, 'id': widget.id, 'titulo': titulo})


@login_required
def delete_widget(request, pk):
    """Elimina (desactiva) un widget del dashboard."""
    from .models import DashboardWidget
    if request.method not in ('DELETE', 'POST'):
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        widget = DashboardWidget.objects.get(pk=pk, user=request.user)
        widget.activo = False
        widget.save()
        return JsonResponse({'ok': True})
    except DashboardWidget.DoesNotExist:
        return JsonResponse({'error': 'No encontrado'}, status=404)


@solo_admin
def api_tendencias(request):
    """Retorna tendencias de los últimos N meses."""
    meses = int(request.GET.get('meses', 12))
    snapshots = KPISnapshot.objects.order_by('-periodo')[:meses][::-1]
    data = {
        'labels': [s.periodo.strftime('%b %Y') for s in snapshots],
        'headcount': [s.total_empleados for s in snapshots],
        'rotacion': [float(s.tasa_rotacion) for s in snapshots],
        'asistencia': [float(s.tasa_asistencia) for s in snapshots],
        'he': [float(s.total_he_mes) for s in snapshots],
    }
    return JsonResponse(data)


# ─────────────────────────────────────────────────
# API WIDGETS HOME — Team Health + Riesgo Rotación
# ─────────────────────────────────────────────────

@solo_admin
def api_team_health(request):
    """
    Composite Team Health Score (0-100) para widget en home.
    Ponderación: asistencia 35% + retención 25% + evaluaciones 20% + capacitaciones 20%.
    """
    from personal.models import Personal

    hoy = date.today()
    inicio_mes = date(hoy.year, hoy.month, 1)
    hace_6m = hoy - timedelta(days=180)
    hace_1y = hoy - timedelta(days=365)

    activos = Personal.objects.filter(estado='Activo')
    total = activos.count()
    if not total:
        return JsonResponse({
            'score': 0, 'label': 'Sin datos', 'color': '#94a3b8',
            'factores': [], 'total_activos': 0,
        })

    # 1. Asistencia este mes (35%) — % registros sin falta
    asistencia_score = 80.0  # default razonable si no hay tareo aún
    try:
        from asistencia.models import RegistroTareo
        total_reg = RegistroTareo.objects.filter(fecha__gte=inicio_mes, fecha__lte=hoy).count()
        if total_reg > 0:
            faltas = RegistroTareo.objects.filter(
                fecha__gte=inicio_mes, fecha__lte=hoy,
                codigo_dia__in=['F', 'FALTA'],
            ).count()
            asistencia_score = round((1 - faltas / total_reg) * 100, 1)
    except Exception:
        pass

    # 2. Retención últimos 90 días (25%) — 100 menos tasa de bajas amplificada
    retencion_score = 95.0
    try:
        bajas_3m = Personal.objects.filter(
            fecha_cese__gte=hoy - timedelta(days=90), estado='Cesado'
        ).count()
        tasa = (bajas_3m / total) * 100
        retencion_score = max(0.0, round(100 - tasa * 4, 1))
    except Exception:
        pass

    # 3. Cobertura evaluaciones (20%) — % con resultado consolidado últimos 6m
    eval_score = 0.0
    try:
        from evaluaciones.models import ResultadoConsolidado
        con_eval = (
            ResultadoConsolidado.objects
            .filter(fecha_consolidacion__gte=hace_6m)
            .values('personal_id').distinct().count()
        )
        eval_score = round(con_eval / total * 100, 1)
    except Exception:
        pass

    # 4. Cobertura capacitaciones (20%) — % con asistencia último año
    cap_score = 0.0
    try:
        from capacitaciones.models import AsistenciaCapacitacion
        con_cap = (
            AsistenciaCapacitacion.objects
            .filter(capacitacion__fecha_inicio__gte=hace_1y, estado__in=['ASISTIO', 'PARCIAL'])
            .values('personal_id').distinct().count()
        )
        cap_score = round(con_cap / total * 100, 1)
    except Exception:
        pass

    composite = round(
        asistencia_score * 0.35 +
        retencion_score  * 0.25 +
        eval_score       * 0.20 +
        cap_score        * 0.20,
        1,
    )

    if composite >= 80:
        label = 'Equipo en forma'
        color = '#16a34a'
    elif composite >= 65:
        label = 'Equipo estable'
        color = '#0f766e'
    elif composite >= 50:
        label = 'Atención requerida'
        color = '#f59e0b'
    else:
        label = 'Alerta crítica'
        color = '#dc2626'

    return JsonResponse({
        'score': composite,
        'label': label,
        'color': color,
        'total_activos': total,
        'factores': [
            {'nombre': 'Asistencia',     'valor': asistencia_score, 'peso': 35},
            {'nombre': 'Retención',      'valor': retencion_score,  'peso': 25},
            {'nombre': 'Evaluaciones',   'valor': eval_score,       'peso': 20},
            {'nombre': 'Capacitaciones', 'valor': cap_score,        'peso': 20},
        ],
    })


@solo_admin
def api_rotacion_riesgo_top(request):
    """
    Top 5 empleados con mayor riesgo de rotación. Para widget en home dashboard.
    Retorna solo empleados con score >= 20 (MEDIUM o HIGH).
    """
    from personal.models import Personal

    hoy = date.today()
    inicio_mes = date(hoy.year, hoy.month, 1)
    hace_6m = hoy - timedelta(days=180)
    hace_1y = hoy - timedelta(days=365)
    en_60d = hoy + timedelta(days=60)

    activos = Personal.objects.filter(estado='Activo').select_related('subarea', 'subarea__area')

    # Datos para scoring (misma lógica que attrition_risk)
    faltas_por_persona = {}
    try:
        from asistencia.models import RegistroTareo
        for row in (
            RegistroTareo.objects
            .filter(fecha__gte=inicio_mes, fecha__lte=hoy,
                    codigo_dia__in=['F', 'FALTA'], personal__isnull=False)
            .values('personal_id').annotate(n=Count('id'))
        ):
            faltas_por_persona[row['personal_id']] = row['n']
    except Exception:
        pass

    con_evaluacion = set()
    try:
        from evaluaciones.models import ResultadoConsolidado
        con_evaluacion = set(
            ResultadoConsolidado.objects
            .filter(fecha_consolidacion__gte=hace_6m)
            .values_list('personal_id', flat=True)
        )
    except Exception:
        pass

    con_capacitacion = set()
    try:
        from capacitaciones.models import AsistenciaCapacitacion
        con_capacitacion = set(
            AsistenciaCapacitacion.objects
            .filter(capacitacion__fecha_inicio__gte=hace_1y, estado__in=['ASISTIO', 'PARCIAL'])
            .values_list('personal_id', flat=True)
        )
    except Exception:
        pass

    bandas_min = {}
    try:
        from salarios.models import BandaSalarial
        for banda in BandaSalarial.objects.filter(activa=True):
            k = banda.cargo.strip().lower()
            if k not in bandas_min or banda.minimo < bandas_min[k]:
                bandas_min[k] = float(banda.minimo)
    except Exception:
        pass

    scored = []
    for emp in activos:
        score = 0
        factores = []

        if (emp.tipo_contrato == 'PLAZO_FIJO' and emp.fecha_fin_contrato and
                hoy <= emp.fecha_fin_contrato <= en_60d):
            score += 30
            factores.append(f'Contrato en {(emp.fecha_fin_contrato - hoy).days}d')

        faltas = faltas_por_persona.get(emp.id, 0)
        if faltas > 3:
            score += 20
            factores.append(f'{faltas} faltas/mes')

        if emp.sueldo_base and emp.cargo:
            bm = bandas_min.get(emp.cargo.strip().lower())
            if bm and float(emp.sueldo_base) < bm:
                score += 15
                factores.append('Sueldo bajo banda')

        if emp.id not in con_evaluacion:
            score += 10
            factores.append('Sin evaluación')

        if emp.id not in con_capacitacion:
            score += 10
            factores.append('Sin capacitación')

        if score >= 20:
            nivel = 'HIGH' if score >= 40 else 'MEDIUM'
            area_nombre = (emp.subarea.area.nombre if emp.subarea and emp.subarea.area else 'Sin área')
            scored.append({
                'pk': emp.pk,
                'nombre': emp.apellidos_nombres,
                'cargo': emp.cargo or '',
                'area': area_nombre,
                'score': score,
                'nivel': nivel,
                'factores': factores[:3],
            })

    scored.sort(key=lambda x: -x['score'])

    return JsonResponse({
        'top': scored[:5],
        'total_riesgo': len(scored),
        'riesgo_alto': sum(1 for e in scored if e['nivel'] == 'HIGH'),
    })
