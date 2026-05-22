"""
Vista pública /upgrade/ que muestra al user Starter las opciones de upgrade.
"""
from django.shortcuts import render


def upgrade_plan(request):
    """Página de upgrade — muestra planes superiores con features incluidas."""
    plan_actual = 'Starter'
    if request.user.is_authenticated:
        # Heredar del middleware: si demo2 está en starter
        from core.middleware_plan_starter import is_starter_user
        if not is_starter_user(request.user):
            plan_actual = 'Profesional'

    planes = [
        {
            'codigo':       'STARTER',
            'nombre':       'Starter',
            'precio':       'S/ 149',
            'colaboradores': 'Hasta 30',
            'color':        '#94a3b8',
            'destacado':    False,
            'features': [
                'Personal (CRUD básico)',
                'Asistencia y papeletas (admin)',
                'Planilla mensual completa',
                'Boleta PDF (generación local)',
                'Vacaciones (gestión admin)',
                'Exportes contables y SUNAT',
                'Soporte por email',
            ],
            'features_no': [
                'Portal del colaborador',
                'Envío/notificación de boletas',
                'Solicitudes desde el portal',
                'Reclutamiento + IA',
                'Capacitaciones',
                'Contratos formales',
                'Organigrama / Calendario',
                'Dashboard Ejecutivo + BI',
            ],
        },
        {
            'codigo':       'PROFESIONAL',
            'nombre':       'Profesional',
            'precio':       'S/ 399',
            'colaboradores': 'Hasta 100',
            'color':        '#0f766e',
            'destacado':    True,
            'features': [
                'Todo lo del Plan Starter +',
                'Reclutamiento con CV parser',
                'Pipeline Kanban + tags',
                'Capacitaciones + certificaciones',
                'Evaluaciones de desempeño',
                'Préstamos y adelantos',
                'Comunicados internos',
                'Reportes ejecutivos PDF',
                'Soporte por chat',
            ],
            'features_no': [
                'IA Predictor de Rotación',
                'Evaluaciones 360 con radar',
                'BI Excel multi-empresa',
                'Multi-empresa avanzado',
            ],
        },
        {
            'codigo':       'BUSINESS',
            'nombre':       'Business',
            'precio':       'S/ 799',
            'colaboradores': 'Hasta 300',
            'color':        '#0d2b27',
            'destacado':    False,
            'features': [
                'Todo lo del Plan Profesional +',
                'IA Predictor de Rotación',
                'Evaluaciones 360 con radar',
                'AI Summary de CV',
                'Dashboard Ejecutivo',
                'BI Excel mensual',
                'Workflows de aprobación',
                'Bandas salariales + equidad',
                'API REST integraciones',
                'Soporte prioritario',
            ],
            'features_no': [],
        },
        {
            'codigo':       'ENTERPRISE',
            'nombre':       'Enterprise',
            'precio':       'Personalizado',
            'colaboradores': '300+',
            'color':        '#a855f7',
            'destacado':    False,
            'features': [
                'Todo lo del Plan Business +',
                'Multi-empresa ilimitado',
                'SSO / Active Directory',
                'Integración con Synkro / SAP',
                'Soporte 24×7 con SLA',
                'Onboarding dedicado',
                'Features customizadas',
            ],
            'features_no': [],
        },
    ]

    return render(request, 'upgrade_plan.html', {
        'plan_actual': plan_actual,
        'planes':      planes,
    })
