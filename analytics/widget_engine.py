"""
Widget Engine para el Dashboard Personalizable de Harmoni.

Define todos los widgets disponibles, sus funciones de datos,
y el catálogo completo para el frontend.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Count, Q, Sum, Avg

logger = logging.getLogger('analytics.widget_engine')

# ─────────────────────────────────────────────────────────────────────────────
# WIDGET REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

WIDGET_CATALOG = {}


def register_widget(widget_id, **kwargs):
    """Registra un widget en el catálogo global."""
    WIDGET_CATALOG[widget_id] = {
        'id': widget_id,
        'title': kwargs.get('title', widget_id),
        'icon': kwargs.get('icon', 'fa-chart-bar'),
        'size': kwargs.get('size', 'small'),       # small | medium | large
        'category': kwargs.get('category', 'general'),
        'color': kwargs.get('color', '#0f766e'),
        'description': kwargs.get('description', ''),
        'data_fn': kwargs.get('data_fn'),
        'template': kwargs.get('template', 'analytics/widgets/kpi_small.html'),
        'requires_superuser': kwargs.get('requires_superuser', False),
        'refresh_seconds': kwargs.get('refresh_seconds', 300),
    }


def get_widget_data(widget_id, user):
    """Obtiene los datos de un widget por su ID."""
    widget = WIDGET_CATALOG.get(widget_id)
    if not widget:
        return {'error': f'Widget "{widget_id}" no encontrado'}
    if widget.get('requires_superuser') and not user.is_superuser:
        return {'error': 'Sin permisos'}
    try:
        data = widget['data_fn'](user)
        return {
            'id': widget_id,
            'title': widget['title'],
            'icon': widget['icon'],
            'size': widget['size'],
            'color': widget['color'],
            'template': widget['template'],
            'data': data,
        }
    except Exception as e:
        logger.exception(f'Error cargando widget {widget_id}')
        return {
            'id': widget_id,
            'title': widget['title'],
            'icon': widget['icon'],
            'size': widget['size'],
            'color': widget['color'],
            'template': widget['template'],
            'data': {'error': str(e)},
        }


def get_catalog(user):
    """Retorna el catálogo de widgets disponibles para el usuario."""
    items = []
    for wid, w in WIDGET_CATALOG.items():
        if w.get('requires_superuser') and not user.is_superuser:
            continue
        items.append({
            'id': wid,
            'title': w['title'],
            'icon': w['icon'],
            'size': w['size'],
            'category': w['category'],
            'color': w['color'],
            'description': w['description'],
        })
    return items


def get_default_layout(user):
    """Layout por defecto para nuevos usuarios."""
    if user.is_superuser:
        return [
            'headcount_total', 'asistencia_hoy', 'vacaciones_pendientes',
            'solicitudes_pendientes', 'headcount_by_area', 'asistencia_mes',
            'planilla_resumen', 'contratos_por_vencer', 'cumpleanos_hoy',
            'tardanzas_mes', 'kpi_rotacion', 'alertas_criticas',
            'actividad_reciente', 'headcount_by_contract', 'ai_insights',
        ]
    return [
        'headcount_total', 'asistencia_hoy', 'vacaciones_pendientes',
        'solicitudes_pendientes', 'cumpleanos_hoy', 'actividad_reciente',
    ]


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: filtrar personal según permisos del usuario
# ─────────────────────────────────────────────────────────────────────────────

def _personal_activo(user):
    from personal.permissions import filtrar_personal
    return filtrar_personal(user).filter(estado='Activo')


# ─────────────────────────────────────────────────────────────────────────────
# DATA FUNCTIONS — cada una retorna un dict con los datos del widget
# ─────────────────────────────────────────────────────────────────────────────

def _headcount_total(user):
    qs = _personal_activo(user)
    total = qs.count()
    dist = {d['grupo_tareo']: d['n'] for d in qs.values('grupo_tareo').annotate(n=Count('id'))}
    staff = dist.get('STAFF', 0)
    rco = dist.get('RCO', 0)
    # Tendencia: altas/bajas del mes
    hoy = date.today()
    inicio_mes = hoy.replace(day=1)
    from personal.models import Personal
    altas = Personal.objects.filter(fecha_alta__gte=inicio_mes, fecha_alta__lte=hoy).count()
    bajas = Personal.objects.filter(estado='Cesado', fecha_cese__gte=inicio_mes, fecha_cese__lte=hoy).count()
    return {
        'total': total, 'staff': staff, 'rco': rco,
        'altas_mes': altas, 'bajas_mes': bajas,
        'tendencia': altas - bajas,
    }


def _headcount_by_area(user):
    qs = _personal_activo(user)
    areas = list(
        qs.values('subarea__area__nombre')
        .annotate(n=Count('id'))
        .order_by('-n')[:8]
    )
    labels = [a['subarea__area__nombre'] or 'Sin area' for a in areas]
    values = [a['n'] for a in areas]
    colors = ['#0f766e', '#0891b2', '#7c3aed', '#d97706', '#dc2626', '#16a34a', '#6366f1', '#ea580c']
    return {'labels': labels, 'values': values, 'colors': colors[:len(labels)]}


def _headcount_by_contract(user):
    qs = _personal_activo(user)
    dist = list(
        qs.values('tipo_contrato')
        .annotate(n=Count('id'))
        .order_by('-n')
    )
    TIPO_LABELS = {
        'PLAZO_FIJO': 'Plazo Fijo', 'INDETERMINADO': 'Indeterminado',
        'LOCACION': 'Locacion', 'PRACTICAS': 'Practicas',
        'FORMACION': 'Formacion', 'PART_TIME': 'Part Time',
    }
    labels = [TIPO_LABELS.get(d['tipo_contrato'], d['tipo_contrato'] or 'Otro') for d in dist]
    values = [d['n'] for d in dist]
    colors = ['#0f766e', '#0891b2', '#7c3aed', '#d97706', '#dc2626', '#16a34a']
    return {'labels': labels, 'values': values, 'colors': colors[:len(labels)]}


def _asistencia_hoy(user):
    hoy = date.today()
    activos = _personal_activo(user)
    total_activos = activos.count()
    try:
        from asistencia.models import RegistroTareo
        tareo = RegistroTareo.objects.filter(fecha=hoy, personal__in=activos)
        stats = tareo.aggregate(
            total=Count('id'),
            presentes=Count('id', filter=Q(codigo_dia__in=['T', 'NOR', 'TR', 'SS', 'A', 'CDT', 'CPF', 'LCG', 'ATM', 'CHE', 'LIM'])),
            faltas=Count('id', filter=Q(codigo_dia__in=['FA', 'LSG'])),
            permisos=Count('id', filter=Q(codigo_dia__in=[
                'V', 'DL', 'DLA', 'DM', 'LCG', 'LF', 'LP', 'LM',
                'CAP', 'CT', 'CHE', 'CDT', 'CPF', 'ATM',
            ])),
        )
        sin_registro = total_activos - (stats['total'] or 0)
        pct = round((stats['presentes'] or 0) / total_activos * 100) if total_activos else 0
        return {
            'presentes': stats['presentes'] or 0,
            'faltas': stats['faltas'] or 0,
            'permisos': stats['permisos'] or 0,
            'sin_registro': sin_registro,
            'total': total_activos,
            'pct_asistencia': pct,
        }
    except Exception:
        return {'presentes': 0, 'faltas': 0, 'permisos': 0, 'sin_registro': 0, 'total': total_activos, 'pct_asistencia': 0}


def _asistencia_mes(user):
    hoy = date.today()
    inicio_mes = hoy.replace(day=1)
    activos = _personal_activo(user)
    try:
        from asistencia.models import RegistroTareo
        from django.db.models import F as DbF
        tareo = RegistroTareo.objects.filter(
            fecha__gte=inicio_mes, fecha__lte=hoy, personal__in=activos
        ).exclude(
            personal__fecha_cese__isnull=False,
            fecha__gt=DbF('personal__fecha_cese')
        ).exclude(
            personal__fecha_alta__isnull=False,
            fecha__lt=DbF('personal__fecha_alta')
        )
        total = tareo.count()
        presentes = tareo.filter(codigo_dia__in=['T', 'NOR', 'TR', 'SS', 'A', 'CDT', 'CPF', 'LCG', 'ATM', 'CHE', 'LIM']).count()
        # Faltas reales: excluir domingos LOCAL (son DS)
        faltas = tareo.filter(codigo_dia__in=['FA', 'LSG']).exclude(
            condicion__in=['LOCAL', 'LIMA', ''], dia_semana=6
        ).count()
        pct = round(presentes / total * 100, 1) if total else 0
        # Stats por dia para mini chart
        dias = list(
            tareo.values('fecha')
            .annotate(
                p=Count('id', filter=Q(codigo_dia__in=['T', 'NOR', 'TR', 'SS', 'A', 'CDT', 'CPF', 'LCG', 'ATM', 'CHE', 'LIM'])),
                t=Count('id')
            )
            .order_by('fecha')
        )
        chart_labels = [d['fecha'].strftime('%d') for d in dias[-14:]]
        chart_values = [round(d['p'] / d['t'] * 100) if d['t'] else 0 for d in dias[-14:]]
        return {
            'total_registros': total, 'presentes': presentes, 'faltas': faltas,
            'pct_asistencia': pct,
            'chart_labels': chart_labels, 'chart_values': chart_values,
        }
    except Exception:
        return {'total_registros': 0, 'presentes': 0, 'faltas': 0, 'pct_asistencia': 0, 'chart_labels': [], 'chart_values': []}


def _tardanzas_mes(user):
    hoy = date.today()
    inicio_mes = hoy.replace(day=1)
    activos = _personal_activo(user)
    try:
        from asistencia.models import RegistroTareo
        tareo = RegistroTareo.objects.filter(
            fecha__gte=inicio_mes, fecha__lte=hoy, personal__in=activos
        )
        tardanzas = tareo.filter(codigo_dia='TR').count()
        total = tareo.filter(codigo_dia__in=['T', 'NOR', 'TR', 'SS', 'A', 'CDT', 'CPF', 'LCG', 'ATM', 'CHE', 'LIM']).count()
        pct = round(tardanzas / total * 100, 1) if total else 0
        return {'tardanzas': tardanzas, 'total_presentes': total, 'pct': pct}
    except Exception:
        return {'tardanzas': 0, 'total_presentes': 0, 'pct': 0}


def _planilla_resumen(user):
    try:
        from nominas.models import PeriodoNomina
        ultimo = PeriodoNomina.objects.filter(
            tipo='REGULAR', estado__in=['CALCULADO', 'APROBADO', 'CERRADO']
        ).order_by('-anio', '-mes').first()
        if ultimo:
            return {
                'periodo': f'{ultimo.get_mes_display()} {ultimo.anio}',
                'neto': float(ultimo.total_neto or 0),
                'bruto': float(ultimo.total_bruto or 0),
                'trabajadores': ultimo.total_trabajadores or 0,
                'estado': ultimo.get_estado_display(),
            }
    except Exception:
        pass
    return {'periodo': '-', 'neto': 0, 'bruto': 0, 'trabajadores': 0, 'estado': '-'}


def _planilla_neto_chart(user):
    try:
        from nominas.models import PeriodoNomina
        periodos = list(
            PeriodoNomina.objects.filter(
                tipo='REGULAR', estado__in=['CALCULADO', 'APROBADO', 'CERRADO']
            ).order_by('anio', 'mes')[:6]
        )
        labels = [f'{p.get_mes_display()[:3]}' for p in periodos]
        netos = [float(p.total_neto or 0) for p in periodos]
        brutos = [float(p.total_bruto or 0) for p in periodos]
        return {'labels': labels, 'netos': netos, 'brutos': brutos}
    except Exception:
        return {'labels': [], 'netos': [], 'brutos': []}


def _vacaciones_pendientes(user):
    activos = _personal_activo(user)
    try:
        from vacaciones.models import SolicitudVacacion
        pendientes = SolicitudVacacion.objects.filter(
            estado='PENDIENTE', personal__in=activos
        ).count()
        aprobadas = SolicitudVacacion.objects.filter(
            estado='APROBADA', personal__in=activos,
            fecha_inicio__gte=date.today(),
        ).count()
        return {'pendientes': pendientes, 'proximas': aprobadas}
    except Exception:
        return {'pendientes': 0, 'proximas': 0}


def _solicitudes_pendientes(user):
    activos = _personal_activo(user)
    hoy = date.today()
    inicio_mes = hoy.replace(day=1)
    result = {'papeletas': 0, 'horas_extra': 0, 'justificaciones': 0, 'total': 0}
    try:
        from asistencia.models import RegistroPapeleta, SolicitudHE, JustificacionNoMarcaje
        result['papeletas'] = RegistroPapeleta.objects.filter(
            personal__in=activos, estado='PENDIENTE'
        ).count()
        result['horas_extra'] = SolicitudHE.objects.filter(
            personal__in=activos, estado='PENDIENTE'
        ).count()
        result['justificaciones'] = JustificacionNoMarcaje.objects.filter(
            personal__in=activos, estado='PENDIENTE'
        ).count()
        result['total'] = result['papeletas'] + result['horas_extra'] + result['justificaciones']
    except Exception:
        pass
    return result


def _cumpleanos_hoy(user):
    hoy = date.today()
    activos = _personal_activo(user)
    cumple_hoy = list(
        activos.filter(
            fecha_nacimiento__month=hoy.month,
            fecha_nacimiento__day=hoy.day,
        ).values('pk', 'apellidos_nombres', 'cargo', 'fecha_nacimiento')[:5]
    )
    # Proximos 7 dias
    proximos = []
    for delta in range(1, 8):
        dia = hoy + timedelta(days=delta)
        ps = activos.filter(
            fecha_nacimiento__month=dia.month,
            fecha_nacimiento__day=dia.day,
        ).values('pk', 'apellidos_nombres', 'cargo', 'fecha_nacimiento')[:3]
        for p in ps:
            p['dias'] = delta
            proximos.append(p)
    for c in cumple_hoy:
        c['edad'] = hoy.year - c['fecha_nacimiento'].year
        c['nombre_corto'] = c['apellidos_nombres'].split(',')[0].strip() if ',' in c['apellidos_nombres'] else c['apellidos_nombres']
    for p in proximos:
        p['nombre_corto'] = p['apellidos_nombres'].split(',')[0].strip() if ',' in p['apellidos_nombres'] else p['apellidos_nombres']
    return {'hoy': cumple_hoy, 'proximos': proximos[:5], 'total_hoy': len(cumple_hoy)}


def _contratos_por_vencer(user):
    hoy = date.today()
    activos = _personal_activo(user)
    en_7d = hoy + timedelta(days=7)
    en_30d = hoy + timedelta(days=30)
    en_60d = hoy + timedelta(days=60)
    urgentes = activos.filter(
        fecha_fin_contrato__gte=hoy, fecha_fin_contrato__lte=en_7d
    ).count()
    en_30 = activos.filter(
        fecha_fin_contrato__gt=en_7d, fecha_fin_contrato__lte=en_30d
    ).count()
    en_60 = activos.filter(
        fecha_fin_contrato__gt=en_30d, fecha_fin_contrato__lte=en_60d
    ).count()
    proximos = list(
        activos.filter(
            fecha_fin_contrato__gte=hoy, fecha_fin_contrato__lte=en_30d
        ).values('pk', 'apellidos_nombres', 'cargo', 'fecha_fin_contrato')
        .order_by('fecha_fin_contrato')[:5]
    )
    for p in proximos:
        p['dias'] = (p['fecha_fin_contrato'] - hoy).days
        p['nombre_corto'] = p['apellidos_nombres'].split(',')[0].strip() if ',' in p['apellidos_nombres'] else p['apellidos_nombres']
        p['fecha_fin_contrato'] = p['fecha_fin_contrato'].strftime('%d/%m/%Y')
    return {'urgentes': urgentes, 'en_30d': en_30, 'en_60d': en_60, 'lista': proximos}


def _alertas_criticas(user):
    try:
        from analytics.models import AlertaRRHH
        alertas = list(
            AlertaRRHH.objects.filter(estado='ACTIVA')
            .order_by('-severidad', '-creado_en')[:5]
            .values('pk', 'titulo', 'severidad', 'categoria', 'creado_en')
        )
        total = AlertaRRHH.objects.filter(estado='ACTIVA').count()
        criticas = AlertaRRHH.objects.filter(estado='ACTIVA', severidad='CRITICAL').count()
        for a in alertas:
            a['creado_en'] = a['creado_en'].strftime('%d/%m %H:%M') if a['creado_en'] else ''
        return {'alertas': alertas, 'total': total, 'criticas': criticas}
    except Exception:
        return {'alertas': [], 'total': 0, 'criticas': 0}


def _kpi_rotacion(user):
    try:
        from analytics.models import KPISnapshot
        ultimo = KPISnapshot.objects.order_by('-periodo').first()
        if ultimo:
            return {
                'tasa': float(ultimo.tasa_rotacion),
                'tasa_voluntaria': float(ultimo.tasa_rotacion_voluntaria),
                'periodo': ultimo.periodo.strftime('%b %Y'),
                'total_empleados': ultimo.total_empleados,
                'altas': ultimo.altas_mes,
                'bajas': ultimo.bajas_mes,
            }
    except Exception:
        pass
    # Calcular en vivo si no hay snapshot
    hoy = date.today()
    from personal.models import Personal
    total = Personal.objects.filter(estado='Activo').count()
    inicio_mes = hoy.replace(day=1)
    bajas = Personal.objects.filter(estado='Cesado', fecha_cese__gte=inicio_mes).count()
    tasa = round(bajas / total * 100, 1) if total else 0
    return {'tasa': tasa, 'tasa_voluntaria': 0, 'periodo': hoy.strftime('%b %Y'), 'total_empleados': total, 'altas': 0, 'bajas': bajas}


def _actividad_reciente(user):
    hoy = date.today()
    hace_7d = hoy - timedelta(days=7)
    activos = _personal_activo(user)
    actividad = []
    try:
        from asistencia.models import RegistroPapeleta, SolicitudHE, JustificacionNoMarcaje
        for p in RegistroPapeleta.objects.filter(
            creado_en__date__gte=hace_7d, personal__in=activos
        ).select_related('personal').order_by('-creado_en')[:4]:
            actividad.append({
                'icono': 'fa-file-alt', 'color': '#0f766e',
                'texto': f'{p.personal.apellidos_nombres.split(",")[0]} - {p.get_tipo_permiso_display()}',
                'estado': p.get_estado_display(), 'fecha': p.creado_en.strftime('%d/%m %H:%M'),
            })
        for s in SolicitudHE.objects.filter(
            creado_en__date__gte=hace_7d, personal__in=activos
        ).select_related('personal').order_by('-creado_en')[:3]:
            actividad.append({
                'icono': 'fa-clock', 'color': '#7c3aed',
                'texto': f'{s.personal.apellidos_nombres.split(",")[0]} - HE {s.horas_estimadas}h',
                'estado': s.get_estado_display(), 'fecha': s.creado_en.strftime('%d/%m %H:%M'),
            })
        for j in JustificacionNoMarcaje.objects.filter(
            creado_en__date__gte=hace_7d, personal__in=activos
        ).select_related('personal').order_by('-creado_en')[:3]:
            actividad.append({
                'icono': 'fa-clipboard-check', 'color': '#ea580c',
                'texto': f'{j.personal.apellidos_nombres.split(",")[0]} - {j.get_tipo_display()}',
                'estado': j.get_estado_display(), 'fecha': j.creado_en.strftime('%d/%m %H:%M'),
            })
    except Exception:
        pass
    actividad.sort(key=lambda x: x['fecha'], reverse=True)
    return {'items': actividad[:8]}


def _ai_insights(user):
    """Retorna insights del AI si está disponible."""
    try:
        from django.core.cache import cache
        cached = cache.get(f'ai_insights_{user.pk}')
        if cached:
            return {'insights': cached, 'available': True}
    except Exception:
        pass
    return {
        'available': False,
        'insights': 'Haz clic en "Actualizar" para generar insights con IA.',
    }


# ─────────────────────────────────────────────────────────────────────────────
# REGISTER ALL WIDGETS
# ─────────────────────────────────────────────────────────────────────────────

register_widget('headcount_total',
    title='Headcount Total', icon='fa-users', size='small',
    category='personal', color='#0f766e',
    description='Total de colaboradores activos con desglose STAFF/RCO',
    data_fn=_headcount_total,
    template='analytics/widgets/kpi_small.html',
)

register_widget('headcount_by_area',
    title='Personal por Area', icon='fa-building', size='medium',
    category='personal', color='#0891b2',
    description='Distribucion del personal por area/gerencia',
    data_fn=_headcount_by_area,
    template='analytics/widgets/chart_bar.html',
)

register_widget('headcount_by_contract',
    title='Tipos de Contrato', icon='fa-file-contract', size='medium',
    category='personal', color='#7c3aed',
    description='Distribucion por tipo de contrato laboral',
    data_fn=_headcount_by_contract,
    template='analytics/widgets/chart_doughnut.html',
)

register_widget('asistencia_hoy',
    title='Asistencia Hoy', icon='fa-fingerprint', size='small',
    category='asistencia', color='#10b981',
    description='Estado de asistencia del dia actual',
    data_fn=_asistencia_hoy,
    template='analytics/widgets/kpi_small.html',
)

register_widget('asistencia_mes',
    title='Asistencia del Mes', icon='fa-chart-area', size='medium',
    category='asistencia', color='#1d4ed8',
    description='Tendencia de asistencia de los ultimos 14 dias',
    data_fn=_asistencia_mes,
    template='analytics/widgets/chart_line.html',
)

register_widget('tardanzas_mes',
    title='Tardanzas del Mes', icon='fa-clock', size='small',
    category='asistencia', color='#f59e0b',
    description='Cantidad y porcentaje de tardanzas del mes',
    data_fn=_tardanzas_mes,
    template='analytics/widgets/kpi_small.html',
)

register_widget('planilla_resumen',
    title='Resumen Planilla', icon='fa-file-invoice-dollar', size='small',
    category='nominas', color='#059669',
    description='Ultimo periodo de nomina procesado',
    data_fn=_planilla_resumen,
    template='analytics/widgets/kpi_small.html',
    requires_superuser=True,
)

register_widget('planilla_neto_chart',
    title='Tendencia Neto Planilla', icon='fa-chart-line', size='large',
    category='nominas', color='#059669',
    description='Evolucion del neto de planilla ultimos 6 meses',
    data_fn=_planilla_neto_chart,
    template='analytics/widgets/chart_line.html',
    requires_superuser=True,
)

register_widget('vacaciones_pendientes',
    title='Vacaciones Pendientes', icon='fa-umbrella-beach', size='small',
    category='vacaciones', color='#0891b2',
    description='Solicitudes de vacaciones pendientes de aprobacion',
    data_fn=_vacaciones_pendientes,
    template='analytics/widgets/kpi_small.html',
)

register_widget('solicitudes_pendientes',
    title='Solicitudes Pendientes', icon='fa-tasks', size='small',
    category='aprobaciones', color='#f59e0b',
    description='Papeletas, HE y justificaciones pendientes',
    data_fn=_solicitudes_pendientes,
    template='analytics/widgets/kpi_small.html',
)

register_widget('cumpleanos_hoy',
    title='Cumpleanos', icon='fa-birthday-cake', size='medium',
    category='personal', color='#ec4899',
    description='Cumpleanos del dia y de la semana',
    data_fn=_cumpleanos_hoy,
    template='analytics/widgets/list_medium.html',
)

register_widget('contratos_por_vencer',
    title='Contratos por Vencer', icon='fa-file-contract', size='medium',
    category='personal', color='#dc2626',
    description='Contratos que vencen en los proximos 30/60 dias',
    data_fn=_contratos_por_vencer,
    template='analytics/widgets/list_medium.html',
    requires_superuser=True,
)

register_widget('alertas_criticas',
    title='Alertas RRHH', icon='fa-exclamation-triangle', size='medium',
    category='analytics', color='#dc2626',
    description='Alertas activas del sistema de analytics',
    data_fn=_alertas_criticas,
    template='analytics/widgets/list_medium.html',
    requires_superuser=True,
)

register_widget('kpi_rotacion',
    title='Rotacion de Personal', icon='fa-sync-alt', size='small',
    category='analytics', color='#ef4444',
    description='Tasa de rotacion mensual del equipo',
    data_fn=_kpi_rotacion,
    template='analytics/widgets/kpi_small.html',
    requires_superuser=True,
)

register_widget('actividad_reciente',
    title='Actividad Reciente', icon='fa-stream', size='large',
    category='general', color='#f59e0b',
    description='Ultimos movimientos: papeletas, HE, justificaciones',
    data_fn=_actividad_reciente,
    template='analytics/widgets/list_large.html',
)

register_widget('ai_insights',
    title='Insights IA', icon='fa-brain', size='large',
    category='analytics', color='#0f766e',
    description='Analisis inteligente generado por IA',
    data_fn=_ai_insights,
    template='analytics/widgets/ai_insights.html',
)
