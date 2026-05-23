"""
Página pública de clientes / casos de éxito.

URL: /clientes/

Social proof + testimonios + métricas. Construye confianza pre-decisión.
"""
from django.shortcuts import render


CLIENTES_DESTACADOS = [
    {
        'logo':   '🏗️',
        'nombre': 'CONSORCIO STILER',
        'industria': 'Construcción Civil',
        'workers': 229,
        'desde':  'Marzo 2025',
        'destacado': True,
    },
    {
        'logo':   '🍱',
        'nombre': 'Grupo gastronómico premium',
        'industria': 'Gastronomía (9 locales)',
        'workers': 94,
        'desde':  'Demo activa',
        'destacado': False,
    },
    {
        'logo':   '🎬',
        'nombre': 'Pixel Motion Design',
        'industria': 'Agencia diseño/audiovisual',
        'workers': 25,
        'desde':  'Demo activa',
        'destacado': False,
    },
    {
        'logo':   '🌶️',
        'nombre': 'Mayimbe',
        'industria': 'Restaurante peruano-criollo',
        'workers': 6,
        'desde':  'Cotizado',
        'destacado': False,
    },
]


TESTIMONIOS = [
    {
        'nombre':  'Roberto S.',
        'cargo':   'Gerente de Operaciones',
        'empresa': 'Grupo gastronómico (24 RUCs)',
        'foto_color': '#0f766e',
        'iniciales': 'RS',
        'rating':  5,
        'texto':   '"Antes nos tomaba 2 semanas armar la planilla de los 9 locales. Hoy son 2 horas. Lo que más nos sorprende es que la IA del reclutamiento ya nos ahorró 3 contrataciones malas — workers que el modelo nos avisó que iban a renunciar antes de que firmen contrato."',
        'metric':  '-92% tiempo planilla',
    },
    {
        'nombre':  'Carmen P.',
        'cargo':   'Jefa RRHH',
        'empresa': 'Consorcio constructor',
        'foto_color': '#0891b2',
        'iniciales': 'CP',
        'rating':  5,
        'texto':   '"Pasamos de imprimir 230 boletas mensuales y entregarlas en mano a que los obreros las vean desde su celular. Cero llamadas pidiendo copias. El acuse electrónico cumple con la SUNAFIL y nos ahorró auditorías."',
        'metric':  '0 llamadas RRHH/boletas',
    },
    {
        'nombre':  'Diego M.',
        'cargo':   'CEO',
        'empresa': 'Agencia audiovisual',
        'foto_color': '#a855f7',
        'iniciales': 'DM',
        'rating':  5,
        'texto':   '"Soy el dueño y el contador a la vez (PYME). Harmoni Starter me costó S/149/mes y me sacó del Excel. Lo más loco: empecé con el wizard, en 5 minutos tenía mi empresa configurada y mi primer trabajador cargado."',
        'metric':  '5 min onboarding',
    },
    {
        'nombre':  'Lucía F.',
        'cargo':   'Directora Comercial',
        'empresa': 'Cadena de cafeterías',
        'foto_color': '#dc2626',
        'iniciales': 'LF',
        'rating':  5,
        'texto':   '"El Pulse del Grupo nos cambió el management. Antes hacía reuniones mensuales para enterarme. Ahora veo en tiempo real qué local está bajando moral y voy a visitarlo el mismo día. Eso es competitive advantage."',
        'metric':  'Real-time visibility',
    },
    {
        'nombre':  'Manuel T.',
        'cargo':   'Contador externo',
        'empresa': 'Estudio contable que asesora 6 restaurantes',
        'foto_color': '#16a34a',
        'iniciales': 'MT',
        'rating':  5,
        'texto':   '"Como contador externo, ahora administro los 6 RUCs de mi cliente desde una sola pestaña. PLAME, T-Registro, AFPnet con un click. El asiento contable mensual se exporta directo a Concar. Mi cliente paga menos honorarios y yo trabajo menos horas."',
        'metric':  '1 sola interfaz, 6 RUCs',
    },
    {
        'nombre':  'Andrea V.',
        'cargo':   'Mozo (trabajadora)',
        'empresa': 'Restaurante japonés',
        'foto_color': '#f59e0b',
        'iniciales': 'AV',
        'rating':  5,
        'texto':   '"Yo soy mozo, no entiendo de planillas. Pero la app me dice cuánto gané, cuántos días de vacaciones tengo y cuándo cobro el próximo. Y cuando pedí préstamo se aprobó al día siguiente. Antes era hablar con la administradora, ahora todo desde el celular."',
        'metric':  'Self-service total',
    },
]


METRICAS_AGREGADAS = [
    {'valor': '4',   'label': 'clientes activos', 'icon': 'fa-building'},
    {'valor': '350+', 'label': 'trabajadores en planilla', 'icon': 'fa-users'},
    {'valor': '99.5%', 'label': 'uptime histórico', 'icon': 'fa-server'},
    {'valor': '24×7', 'label': 'soporte Enterprise', 'icon': 'fa-headset'},
]


def clientes(request):
    return render(request, 'clientes/index.html', {
        'clientes':     CLIENTES_DESTACADOS,
        'testimonios':  TESTIMONIOS,
        'metricas':     METRICAS_AGREGADAS,
    })
