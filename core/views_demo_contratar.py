"""
Demo guiado interactivo — "Contratar a un cocinero en 5 minutos".

URL: /demos/contratar/

Muestra paso a paso con animaciones cómo es el flujo end-to-end de Harmoni
para contratar a una persona nueva. Pensado para ver SIN tener que tocar.
"""
from django.shortcuts import render


PASOS = [
    {
        'numero': 1,
        'titulo': 'Publicar la vacante',
        'tiempo': '30 segundos',
        'descripcion': 'Llenas título, área, salario, requisitos. Harmoni publica automáticamente en Computrabajo, LinkedIn y tu pool interno.',
        'screenshot_url': '/reclutamiento/vacante/nueva/',
        'icon': 'fa-bullhorn',
        'color': '#0f766e',
        'highlights': [
            'Template gastronomía pre-cargado (Mozo, Cocinero, Bartender, etc.)',
            'Sueldo en banda automático según el cargo',
            'Auto-publicación cross-platform',
        ],
    },
    {
        'numero': 2,
        'titulo': 'Pipeline IA filtra candidatos',
        'tiempo': 'En tiempo real',
        'descripcion': 'Los CVs entran al Pipeline Kanban. Cada uno recibe score 0-100 de match con tu vacante (IA Gemini). Los duplicados se detectan automático.',
        'screenshot_url': '/reclutamiento/pipeline/',
        'icon': 'fa-rocket',
        'color': '#a855f7',
        'highlights': [
            'CV Parser extrae experiencia, idiomas, certificaciones',
            'Score explicado: "92% match porque tiene experiencia gastronomía + Lima + nivel senior"',
            'Detección de duplicados (DNI/email/teléfono)',
        ],
    },
    {
        'numero': 3,
        'titulo': 'Entrevistas con scorecard',
        'tiempo': '15-30 min/candidato',
        'descripcion': 'Programas entrevistas desde el calendario integrado. Cada entrevistador llena scorecard estructurado. Comparativa side-by-side de los finalistas.',
        'screenshot_url': '/reclutamiento/calendario/',
        'icon': 'fa-comments',
        'color': '#0891b2',
        'highlights': [
            'Calendario sin choque con otros entrevistadores',
            'Scorecard customizable por cargo',
            'Compare side-by-side hasta 4 candidatos',
        ],
    },
    {
        'numero': 4,
        'titulo': 'Contrato + onboarding express',
        'tiempo': '2 minutos',
        'descripcion': 'Click "Contratar". Harmoni genera contrato PDF con sus datos, lo manda a firma digital y abre el flow de onboarding 30/60/90.',
        'screenshot_url': '/contratos/',
        'icon': 'fa-file-signature',
        'color': '#16a34a',
        'highlights': [
            'Plantilla contrato 728/727 (privado/construcción)',
            'PDF generado con datos auto-llenos',
            'Onboarding 30/60/90 con checklist por área',
        ],
    },
    {
        'numero': 5,
        'titulo': 'Trabajador en planilla',
        'tiempo': 'Inmediato',
        'descripcion': 'Aparece en /personal/, en la asistencia, en la planilla del mes. El primer día recibe email de bienvenida con sus credenciales del portal mobile.',
        'screenshot_url': '/personal/',
        'icon': 'fa-users',
        'color': '#f59e0b',
        'highlights': [
            'T-Registro generado automático para SUNAT',
            'Email bienvenida con QR de portal mobile',
            'Asignación a turnos del local (cuadrícula)',
        ],
    },
]


def demo_contratar(request):
    return render(request, 'demos/contratar.html', {
        'pasos': PASOS,
        'tiempo_total': '5 minutos',
    })
