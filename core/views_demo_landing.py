"""
Vista pública para landings comerciales /demo/ y /demo2/.

Separado para mantener config/urls.py simple.
"""
from django.shortcuts import render


DEMOS = {
    'demo': {
        'titulo':       'Grupo Sabores — Gastronomía Premium',
        'descripcion':  'Cadena gastronómica con 24 RUCs y ~800 trabajadores. Restaurantes, bares y catering.',
        'plan':         'Enterprise (multi-empresa + integraciones)',
        'trabajadores': 800,
        'empresas':     24,
        'usuario':      'admin',
        'password':     'demo',
        'features': [
            'Multi-empresa (24 RUCs consolidados)',
            'Pipeline Reclutamiento Kanban',
            'Briefing del Día (pre-shift)',
            'Cuadrícula Semanal de turnos',
            'BPM / HACCP tracking',
            'Pulse del Grupo (multi-local)',
            'Dashboard Ejecutivo',
            'Predictor IA de Rotación',
        ],
        'color': '#0f766e',
    },
    'demo2': {
        'titulo':       'Pixel Motion — Agencia Diseño & Audiovisual',
        'descripcion':  'Agencia creativa pequeña: diseño gráfico, motion graphics, post-producción. 25 trabajadores.',
        'plan':         'Starter (S/ 149 + IGV / mes — hasta 30 colaboradores)',
        'trabajadores': 25,
        'empresas':     1,
        'usuario':      'demo2',
        'password':     'demo',
        'features': [
            'Personal (CRUD básico)',
            'Asistencia + papeletas (admin)',
            'Planilla mensual completa',
            'Boleta PDF (descarga local)',
            'Vacaciones (gestión admin)',
            'Exportes contables y SUNAT',
            'Soporte por email',
        ],
        'features_no': [
            'Sin portal del colaborador',
            'Sin envío de boletas',
            'Sin solicitudes desde portal',
            'Sin IA / Reclutamiento / BI',
        ],
        'color': '#a855f7',
    },
}


def demo_landing(request, demo_slug='demo'):
    return render(request, 'demo_landing.html', {
        'demo_slug': demo_slug,
        'demo':      DEMOS.get(demo_slug, DEMOS['demo']),
    })


def demo_landing_1(request):
    return demo_landing(request, 'demo')


def demo_landing_2(request):
    return demo_landing(request, 'demo2')
