"""
Tour interactivo del demo EDO Enterprise.

URL: /tour/edo/

Muestra grid de features estrella con descripción y CTA. Pensado para que
el vendedor lo use como atajo durante un demo, o para que el cliente que
recibió el link `/d/enterprise/` tenga un punto de partida claro.
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


HIGHLIGHTS = [
    {
        'icon':        'fa-users',
        'color':       '#0f766e',
        'titulo':      'Multi-empresa (24 RUCs)',
        'descripcion': '9 razones sociales gestionadas como un solo grupo — consolidado para el dueño, separado contablemente.',
        'url':         '/empresas/',
        'cta':         'Ver empresas',
        'duracion':    '1 min',
    },
    {
        'icon':        'fa-chart-line',
        'color':       '#0891b2',
        'titulo':      'Dashboard Ejecutivo',
        'descripcion': 'Cross-empresa: rotación, attrition, costo planilla, salud cultural. KPIs que importan al CEO.',
        'url':         '/sistema/dashboard/ejecutivo/',
        'cta':         'Entrar al dashboard',
        'duracion':    '2 min',
    },
    {
        'icon':        'fa-pulse',
        'color':       '#a855f7',
        'titulo':      'Pulse del Grupo',
        'descripcion': 'Termómetro semanal de las 9 locales — quién está bien, quién pide atención. Comparativo en tiempo real.',
        'url':         '/empresas/pulse/',
        'cta':         'Ver Pulse',
        'duracion':    '2 min',
    },
    {
        'icon':        'fa-clipboard-list',
        'color':       '#f59e0b',
        'titulo':      'Briefing del Día',
        'descripcion': 'Handover pre-shift para cocina y salón. El admin escribe el briefing y el mozo lo lee al entrar.',
        'url':         '/asistencia/briefing/',
        'cta':         'Ver briefings',
        'duracion':    '2 min',
    },
    {
        'icon':        'fa-th',
        'color':       '#0d2b27',
        'titulo':      'Cuadrícula Semanal',
        'descripcion': 'Asignación de turnos con drag&drop. Cubrir 7 días × 3 turnos × N posiciones — en minutos.',
        'url':         '/roster/',
        'cta':         'Ver roster',
        'duracion':    '2 min',
    },
    {
        'icon':        'fa-rocket',
        'color':       '#16a34a',
        'titulo':      'Pipeline Reclutamiento (IA)',
        'descripcion': 'Kanban con score IA de match al perfil — bulk actions, plantillas email, banco de talento.',
        'url':         '/reclutamiento/pipeline/',
        'cta':         'Ver pipeline',
        'duracion':    '3 min',
    },
    {
        'icon':        'fa-brain',
        'color':       '#7c3aed',
        'titulo':      'Predictor IA de Rotación',
        'descripcion': 'Modelo de ML que identifica trabajadores con riesgo alto de irse — proactivo, no reactivo.',
        'url':         '/analytics/predictive/',
        'cta':         'Ver predictor',
        'duracion':    '2 min',
    },
    {
        'icon':        'fa-shield-virus',
        'color':       '#dc2626',
        'titulo':      'BPM / HACCP gastro',
        'descripcion': 'Tracking de capacitaciones obligatorias para manipuladores de alimentos. Vencimientos con alerta automática.',
        'url':         '/capacitaciones/gastro/',
        'cta':         'Ver capacitaciones',
        'duracion':    '1 min',
    },
    {
        'icon':        'fa-file-invoice-dollar',
        'color':       '#0f766e',
        'titulo':      'Boleta PDF + QR público',
        'descripcion': 'Boleta con QR que cualquiera puede escanear sin login — banco, contador, sindicato verifican autenticidad.',
        'url':         '/nominas/',
        'cta':         'Ver nóminas',
        'duracion':    '2 min',
    },
    {
        'icon':        'fa-mobile-alt',
        'color':       '#0ea5e9',
        'titulo':      'Portal del trabajador',
        'descripcion': 'Boletas, vacaciones, asistencia, préstamos — todo desde el celular. Cero llamadas a RRHH.',
        'url':         '/mi-portal/',
        'cta':         'Ver portal (logout demo)',
        'duracion':    '5 min',
    },
    {
        'icon':        'fa-file-excel',
        'color':       '#16a34a',
        'titulo':      'PLAME / AFPnet / Concar',
        'descripcion': 'Exportes legales de SUNAT y contables. Lo que antes tomaba 2 días de un contador — 2 minutos.',
        'url':         '/nominas/',
        'cta':         'Ver exportes',
        'duracion':    '2 min',
    },
    {
        'icon':        'fa-chart-bar',
        'color':       '#a855f7',
        'titulo':      'BI Excel cross-modulo',
        'descripcion': '8 tabs de análisis BI: headcount, rotación, costos, ausentismo. Editable en Excel, refresh con 1 click.',
        'url':         '/sistema/reporte-bi-mensual/',
        'cta':         'Generar BI Excel',
        'duracion':    '1 min',
    },
]


@login_required
def tour_edo(request):
    """Tour interactivo con highlights del demo Enterprise."""
    return render(request, 'tour/edo.html', {
        'highlights':       HIGHLIGHTS,
        'total_features':   len(HIGHLIGHTS),
        'duracion_total':   '25-30 min',
    })
