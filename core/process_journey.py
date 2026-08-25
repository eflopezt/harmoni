"""Lectura operativa del ciclo de RR. HH. basada solo en datos reales."""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db.models import Q, Sum
from django.urls import reverse
from django.utils import timezone

from empresas.acceso import empresas_del_request

STATUS_ORDER = {'critical': 0, 'warning': 1, 'info': 2, 'ready': 3}


def _stage(key, number, title, *, status, metric, metric_label, summary,
           action_url, action_label, icon, issues=None):
    return {
        'key': key,
        'number': number,
        'title': title,
        'status': status,
        'metric': metric,
        'metric_label': metric_label,
        'summary': summary,
        'action_url': action_url,
        'action_label': action_label,
        'icon': icon,
        'issues': issues or [],
    }


def _issue(stage, priority, title, description, url, action):
    return {
        'stage': stage,
        'priority': priority,
        'title': title,
        'description': description,
        'url': url,
        'action': action,
    }


def recruitment_scope(request, empresas):
    """Vacantes y postulaciones del alcance autorizado."""
    from reclutamiento.models import Postulacion, Vacante

    vacantes = Vacante.objects.filter(empresa__in=empresas)
    return vacantes, Postulacion.objects.filter(vacante__in=vacantes)


def build_process_journey(request):
    """Construye etapas, alertas y métricas para el alcance autorizado."""
    from empresas.completitud import datos_pendientes
    from nominas.models import LiquidacionLaboral, PeriodoNomina
    from onboarding.models import (
        PasoOffboarding,
        PasoOnboarding,
        ProcesoOffboarding,
        ProcesoOnboarding,
    )
    from personal.models import Contrato, Personal
    from vacaciones.models import SolicitudVacacion

    hoy = timezone.localdate()
    empresas = empresas_del_request(request)
    empresa_ids = list(empresas.values_list('pk', flat=True))
    personal = Personal.objects.filter(empresa_id__in=empresa_ids)
    activos = personal.filter(estado='Activo')
    issues = []
    stages = []

    # 1. Preparacion de empresa y legajo
    criticos_empresa = 0
    for empresa in empresas.only(
        'pk', 'ruc', 'razon_social', 'direccion', 'representante_legal',
        'nro_doc_representante', 'ubigeo', 'distrito', 'actividad_economica',
        'cargo_representante', 'logo', 'telefono', 'email_rrhh',
    ):
        criticos_empresa += len(datos_pendientes(empresa)['criticos'])
    sin_fecha_alta = activos.filter(fecha_alta__isnull=True).count()
    sin_sueldo = activos.filter(Q(sueldo_base__isnull=True) | Q(sueldo_base__lte=0)).count()
    setup_blockers = criticos_empresa + sin_fecha_alta + sin_sueldo
    setup_url = reverse('data_quality_center')
    if criticos_empresa:
        issues.append(_issue(
            'Preparacion', 'critical',
            f'{criticos_empresa} datos legales de empresa pendientes',
            'Pueden invalidar contratos, boletas o archivos SUNAT.',
            f'{setup_url}?cola=empresa', 'Completar empresa'))
    if sin_fecha_alta or sin_sueldo:
        issues.append(_issue(
            'Preparacion', 'critical',
            f'{sin_fecha_alta + sin_sueldo} incidencias criticas en legajos',
            f'{sin_fecha_alta} sin fecha de alta y {sin_sueldo} sin sueldo base.',
            f'{setup_url}?cola=legajos', 'Revisar legajos'))
    stages.append(_stage(
        'setup', '01', 'Preparar',
        status='critical' if setup_blockers else ('info' if not activos.exists() else 'ready'),
        metric=setup_blockers if setup_blockers else activos.count(),
        metric_label='bloqueos' if setup_blockers else 'personas activas',
        summary='Empresa, legajos y datos necesarios para operar sin reprocesos.',
        action_url=setup_url,
        action_label='Sanear datos', icon='fa-building-circle-check',
    ))

    # 2. Reclutamiento
    vacantes, postulaciones = recruitment_scope(request, empresas)
    vacantes_pendientes = vacantes.filter(estado__in=['POR_APROBAR', 'APROBADA']).count()
    vacantes_activas = vacantes.filter(estado__in=['PUBLICADA', 'EN_PROCESO']).count()
    candidatos_activos = postulaciones.filter(estado='ACTIVA').count()
    if vacantes_pendientes:
        issues.append(_issue(
            'Reclutamiento', 'warning',
            f'{vacantes_pendientes} requisiciones esperan publicacion o aprobacion',
            'La cobertura no avanza hasta resolver el siguiente estado.',
            reverse('vacantes_panel'), 'Revisar vacantes'))
    stages.append(_stage(
        'recruitment', '02', 'Atraer',
        status='warning' if vacantes_pendientes else ('info' if vacantes_activas else 'ready'),
        metric=vacantes_activas,
        metric_label='vacantes activas',
        summary=f'{candidatos_activos} candidatos activos dentro del alcance actual.',
        action_url=reverse('vacantes_panel'), action_label='Abrir pipeline',
        icon='fa-user-plus',
    ))

    # 3. Ingreso
    onboarding = ProcesoOnboarding.objects.filter(
        personal__empresa_id__in=empresa_ids, estado='EN_CURSO')
    pasos_on_vencidos = PasoOnboarding.objects.filter(
        proceso__in=onboarding,
        estado__in=['PENDIENTE', 'EN_PROGRESO'], fecha_limite__lt=hoy,
    ).count()
    if pasos_on_vencidos:
        issues.append(_issue(
            'Ingreso', 'critical', f'{pasos_on_vencidos} tareas de ingreso vencidas',
            'Documentos, accesos o inducciones siguen pendientes tras su fecha limite.',
            reverse('onboarding_panel'), 'Resolver onboarding'))
    stages.append(_stage(
        'onboarding', '03', 'Incorporar',
        status='critical' if pasos_on_vencidos else ('info' if onboarding.exists() else 'ready'),
        metric=onboarding.count(), metric_label='ingresos en curso',
        summary=f'{pasos_on_vencidos} tareas vencidas en los checklists activos.',
        action_url=reverse('onboarding_panel'), action_label='Ver ingresos',
        icon='fa-id-card',
    ))

    # 4. Operacion y aprobaciones
    vac_pend = SolicitudVacacion.objects.filter(
        personal__empresa_id__in=empresa_ids, estado='PENDIENTE').count()
    contratos_vence = Contrato.objects.filter(
        personal__empresa_id__in=empresa_ids, estado='VIGENTE',
        fecha_fin__range=(hoy, hoy + timedelta(days=30)),
    ).count()
    op_total = vac_pend + contratos_vence
    if contratos_vence:
        issues.append(_issue(
            'Operacion', 'critical', f'{contratos_vence} contratos vencen en 30 dias',
            'Renueva o programa el cierre antes de la fecha de termino.',
            reverse('contratos_panel'), 'Revisar contratos'))
    if vac_pend:
        issues.append(_issue(
            'Operacion', 'warning', f'{vac_pend} vacaciones esperan decision',
            'La bandeja central mantiene la trazabilidad de la aprobacion.',
            reverse('dashboard_aprobaciones'), 'Abrir bandeja'))
    stages.append(_stage(
        'operations', '04', 'Operar',
        status='critical' if contratos_vence else ('warning' if vac_pend else 'ready'),
        metric=op_total, metric_label='decisiones pendientes',
        summary='Contratos, solicitudes y excepciones que requieren una decision.',
        action_url=reverse('dashboard_aprobaciones'), action_label='Resolver pendientes',
        icon='fa-list-check',
    ))

    # 5. Pago
    periodos = PeriodoNomina.objects.filter(
        empresa_id__in=empresa_ids, tipo='REGULAR')
    ultimo_periodo = periodos.order_by('-anio', '-mes', '-pk').first()
    nomina_estado = ultimo_periodo.estado if ultimo_periodo else 'SIN_PERIODO'
    nomina_pendiente = ultimo_periodo is None or nomina_estado in ('BORRADOR', 'CALCULADO')
    if ultimo_periodo is None and activos.exists():
        issues.append(_issue(
            'Pago', 'warning', 'Aun no existe un periodo regular de planilla',
            'Valida datos y crea el primer periodo antes del cierre mensual.',
            reverse('onboarding_validador'), 'Validar planilla'))
    elif nomina_estado in ('BORRADOR', 'CALCULADO'):
        issues.append(_issue(
            'Pago', 'warning', f'Planilla {ultimo_periodo.mes:02d}/{ultimo_periodo.anio} por cerrar',
            f'El periodo permanece en estado {ultimo_periodo.get_estado_display()}.',
            reverse('nominas_panel'), 'Continuar cierre'))
    stages.append(_stage(
        'payroll', '05', 'Pagar',
        status='warning' if nomina_pendiente and activos.exists() else 'ready',
        metric=ultimo_periodo.get_estado_display() if ultimo_periodo else 'Sin periodo',
        metric_label='ultima planilla',
        summary='Validacion, calculo, aprobacion, pago y contabilizacion del periodo.',
        action_url=reverse('nominas_panel'), action_label='Abrir planilla',
        icon='fa-money-check-dollar',
    ))

    # 6. Salida
    offboardings = ProcesoOffboarding.objects.filter(
        personal__empresa_id__in=empresa_ids, estado='EN_CURSO')
    pasos_off_vencidos = PasoOffboarding.objects.filter(
        proceso__in=offboardings,
        estado__in=['PENDIENTE', 'EN_PROGRESO'], fecha_limite__lt=hoy,
    ).count()
    liquidaciones = LiquidacionLaboral.objects.filter(
        personal__empresa_id__in=empresa_ids,
    ).exclude(estado='CERRADA')
    salida_total = offboardings.count() + liquidaciones.count()
    if pasos_off_vencidos or liquidaciones.exists():
        issues.append(_issue(
            'Salida', 'critical' if pasos_off_vencidos else 'warning',
            f'{salida_total} cierres laborales en curso',
            f'{pasos_off_vencidos} tareas vencidas y {liquidaciones.count()} liquidaciones abiertas.',
            (f'{reverse("data_quality_center")}?cola=liquidaciones'
             if liquidaciones.exists() else reverse('offboarding_panel')),
            'Cerrar salidas'))
    stages.append(_stage(
        'offboarding', '06', 'Desvincular',
        status='critical' if pasos_off_vencidos else ('warning' if salida_total else 'ready'),
        metric=salida_total, metric_label='salidas abiertas',
        summary='Activos, accesos, documentos y liquidacion con evidencia de cierre.',
        action_url=(f'{reverse("data_quality_center")}?cola=liquidaciones'
                    if liquidaciones.exists() else reverse('offboarding_panel')),
        action_label='Ver salidas',
        icon='fa-person-walking-arrow-right',
    ))

    issues.sort(key=lambda item: (STATUS_ORDER.get(item['priority'], 9), item['stage']))
    base_salarial = activos.aggregate(total=Sum('sueldo_base'))['total'] or Decimal('0')

    return {
        'empresas': empresas,
        'empresa_ids': empresa_ids,
        'stages': stages,
        'issues': issues,
        'next_action': issues[0] if issues else None,
        'total_workers': activos.count(),
        'total_empresas': empresas.count(),
        'base_salarial': base_salarial,
        'total_pending': len(issues),
    }
