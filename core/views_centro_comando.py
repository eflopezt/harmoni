"""Centro de Comando: siguiente accion del ciclo de personas."""
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from core.permisos import requiere_modulo_o_staff
from core.process_journey import build_process_journey


@login_required
@requiere_modulo_o_staff('analytics')
def centro_comando(request):
    """Vista operativa con datos verificables y alcance por empresa."""
    from asistencia.models import BriefingServicio
    from nominas.models import PeriodoNomina
    from onboarding.models import PasoOnboarding
    from personal.models import Contrato

    hoy = timezone.localdate()
    snapshot = build_process_journey(request)
    empresas = snapshot['empresas']

    contratos_map = dict(
        Contrato.objects.filter(
            personal__empresa__in=empresas,
            estado='VIGENTE',
            fecha_fin__range=(hoy, hoy + timedelta(days=30)),
        ).values('personal__empresa_id').annotate(total=Count('pk'))
        .values_list('personal__empresa_id', 'total')
    )
    onboarding_map = dict(
        PasoOnboarding.objects.filter(
            proceso__personal__empresa__in=empresas,
            proceso__estado='EN_CURSO',
            estado__in=['PENDIENTE', 'EN_PROGRESO'],
            fecha_limite__lt=hoy,
        ).values('proceso__personal__empresa_id').annotate(total=Count('pk'))
        .values_list('proceso__personal__empresa_id', 'total')
    )

    operaciones = []
    empresas_con_personal = (
        empresas.annotate(
            activos=Count('personal', filter=Q(personal__estado='Activo')),
        ).filter(activos__gt=0).order_by('razon_social')[:12]
    )
    for empresa in empresas_con_personal:
        ultimo_periodo = (
            PeriodoNomina.objects.filter(empresa=empresa, tipo='REGULAR')
            .order_by('-anio', '-mes', '-pk').first()
        )
        operaciones.append({
            'empresa': empresa,
            'activos': empresa.activos,
            'contratos_por_vencer': contratos_map.get(empresa.pk, 0),
            'onboarding_vencido': onboarding_map.get(empresa.pk, 0),
            'nomina': ultimo_periodo,
        })

    briefings_hoy = list(
        BriefingServicio.objects.filter(
            fecha=hoy, empresa__in=empresas, estado='PUBLICADO',
        ).select_related('empresa').order_by('servicio')[:6]
    )

    return render(request, 'comando/centro.html', {
        'fecha_hoy': hoy,
        'usuario': request.user,
        'modo_consolidado': getattr(request, 'modo_consolidado', False),
        'operaciones': operaciones,
        'briefings_hoy': briefings_hoy,
        **snapshot,
    })
