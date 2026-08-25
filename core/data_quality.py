"""Colas accionables de calidad de datos para el ciclo laboral."""
from __future__ import annotations

from datetime import timedelta

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from empresas.acceso import empresas_del_request
from empresas.completitud import datos_pendientes


def _legajo_incidencias(personal):
    incidencias = []
    if personal.fecha_alta is None:
        incidencias.append({
            'campo': 'fecha_alta',
            'label': 'Fecha de alta',
            'severity': 'critical',
            'impacto': 'Impide calcular correctamente antiguedad y beneficios.',
        })
    if personal.sueldo_base is None or personal.sueldo_base <= 0:
        incidencias.append({
            'campo': 'sueldo_base',
            'label': 'Sueldo base',
            'severity': 'critical',
            'impacto': 'Bloquea planilla, beneficios y liquidacion.',
        })
    if not (personal.cargo or '').strip():
        incidencias.append({
            'campo': 'cargo',
            'label': 'Cargo',
            'severity': 'warning',
            'impacto': 'Deja contratos, organigrama y reportes sin funcion definida.',
        })
    if not (personal.tipo_trab or '').strip():
        incidencias.append({
            'campo': 'tipo_trab',
            'label': 'Tipo de trabajador',
            'severity': 'warning',
            'impacto': 'Puede aplicar reglas laborales incorrectas.',
        })
    return incidencias


def _liquidacion_priority(liquidacion, now):
    age = max((now - liquidacion.creado_en).days, 0)
    if age > 30:
        return age, 'critical', 'Vencida'
    if age > 7:
        return age, 'warning', 'Por atender'
    return age, 'info', 'Reciente'


def _liquidacion_action(estado):
    return {
        'BORRADOR': 'Calcular y revisar',
        'CALCULADA': 'Revisar y aprobar',
        'APROBADA': 'Gestionar firma',
        'FIRMADA': 'Registrar pago',
        'PAGADA': 'Cerrar evidencia',
    }.get(estado, 'Abrir liquidacion')


def build_data_quality_snapshot(request, *, row_limit=100):
    """Devuelve solo datos del alcance autorizado y una cola global aislada."""
    from nominas.models import LiquidacionLaboral
    from personal.models import Personal

    now = timezone.now()
    empresas = empresas_del_request(request)
    empresa_ids = list(empresas.values_list('pk', flat=True))

    company_rows = []
    legal_critical = 0
    legal_recommended = 0
    for empresa in empresas.order_by('razon_social'):
        estado = datos_pendientes(empresa)
        legal_critical += len(estado['criticos'])
        legal_recommended += len(estado['recomendados'])
        if estado['total_pendientes']:
            company_rows.append({
                'empresa': empresa,
                'criticos': estado['criticos'],
                'recomendados': estado['recomendados'],
                'total': estado['total_pendientes'],
                'url': reverse('empresa_datos', args=[empresa.pk]),
            })

    legajo_qs = (
        Personal.objects.filter(empresa_id__in=empresa_ids, estado='Activo')
        .filter(
            Q(fecha_alta__isnull=True)
            | Q(sueldo_base__isnull=True)
            | Q(sueldo_base__lte=0)
            | Q(cargo='')
            | Q(tipo_trab='')
        )
        .select_related('empresa', 'subarea__area')
        .order_by('empresa__razon_social', 'apellidos_nombres')
    )
    legajo_total = legajo_qs.count()
    legajo_rows = []
    for personal in legajo_qs[:row_limit]:
        incidencias = _legajo_incidencias(personal)
        legajo_rows.append({
            'personal': personal,
            'incidencias': incidencias,
            'url': reverse('personal_update', args=[personal.pk]),
        })
    # El conteo critico debe cubrir toda la cola, no solo las filas renderizadas.
    legajo_critical = legajo_qs.filter(
        Q(fecha_alta__isnull=True)
        | Q(sueldo_base__isnull=True)
        | Q(sueldo_base__lte=0)
    ).count()

    liquidacion_qs = (
        LiquidacionLaboral.objects.filter(personal__empresa_id__in=empresa_ids)
        .exclude(estado='CERRADA')
        .select_related('personal', 'personal__empresa')
        .order_by('creado_en', 'pk')
    )
    liquidacion_total = liquidacion_qs.count()
    liquidacion_overdue = liquidacion_qs.filter(
        creado_en__lt=now - timedelta(days=30),
    ).count()
    liquidacion_rows = []
    for liquidacion in liquidacion_qs[:row_limit]:
        age, priority, age_label = _liquidacion_priority(liquidacion, now)
        liquidacion_rows.append({
            'liquidacion': liquidacion,
            'age': age,
            'priority': priority,
            'age_label': age_label,
            'action': _liquidacion_action(liquidacion.estado),
            'url': reverse(
                'nominas_liquidacion_laboral_detalle',
                args=[liquidacion.pk],
            ),
        })

    orphan_rows = []
    orphan_total = 0
    orphan_active = 0
    orphan_liquidations = 0
    if request.user.is_superuser:
        orphan_qs = Personal.objects.filter(empresa__isnull=True)
        orphan_total = orphan_qs.count()
        orphan_active = orphan_qs.filter(estado='Activo').count()
        orphan_liquidations = LiquidacionLaboral.objects.filter(
            personal__empresa__isnull=True,
        ).exclude(estado='CERRADA').count()
        for personal in orphan_qs.order_by('-estado', 'apellidos_nombres')[:row_limit]:
            orphan_rows.append({
                'personal': personal,
                'url': reverse('personal_update', args=[personal.pk]),
            })

    return {
        'empresas': empresas,
        'company_rows': company_rows,
        'legal_critical': legal_critical,
        'legal_recommended': legal_recommended,
        'legajo_rows': legajo_rows,
        'legajo_total': legajo_total,
        'legajo_critical': legajo_critical,
        'legajo_truncated': legajo_total > row_limit,
        'liquidacion_rows': liquidacion_rows,
        'liquidacion_total': liquidacion_total,
        'liquidacion_overdue': liquidacion_overdue,
        'liquidacion_truncated': liquidacion_total > row_limit,
        'orphan_rows': orphan_rows,
        'orphan_total': orphan_total,
        'orphan_active': orphan_active,
        'orphan_liquidations': orphan_liquidations,
        'orphan_truncated': orphan_total > row_limit,
        'total_blockers': legal_critical + legajo_critical + liquidacion_total,
        'generated_at': now,
    }
