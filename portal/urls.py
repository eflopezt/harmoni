"""
URLs del portal de autoservicio del colaborador.
"""
from django.urls import path
from . import views
from . import api_views
from calendario.views import mi_calendario, mi_calendario_eventos
from onboarding.views import mi_onboarding as mi_onboarding_portal
from salarios.views import mi_historial_salarial
from disciplinaria.views import mi_portal_disciplinaria

urlpatterns = [
    path('', views.portal_home, name='portal_home'),
    path('perfil/', views.mi_perfil, name='mi_perfil'),
    path('asistencia/', views.mi_asistencia, name='mi_asistencia'),
    path('banco-horas/', views.mi_banco_horas, name='mi_banco_horas'),
    path('roster/', views.mi_roster, name='mi_roster'),
    path('organigrama/', views.organigrama, name='organigrama'),
    path('directorio/', views.directorio, name='directorio'),
    # Justificaciones de No-Marcaje
    path('justificaciones/', views.mis_justificaciones, name='mis_justificaciones'),
    path('justificaciones/crear/', views.justificacion_crear, name='justificacion_crear'),
    path('justificaciones/<int:pk>/anular/', views.justificacion_anular, name='justificacion_anular'),
    # Solicitudes de Horas Extra
    path('solicitudes-he/', views.mis_solicitudes_he, name='mis_solicitudes_he'),
    path('solicitudes-he/crear/', views.solicitud_he_crear, name='solicitud_he_crear_portal'),
    path('solicitudes-he/<int:pk>/anular/', views.solicitud_he_anular, name='solicitud_he_anular'),
    # Papeletas (vacaciones, licencias, compensaciones, etc.)
    path('papeletas/', views.mis_papeletas, name='mis_papeletas'),
    path('papeletas/crear/', views.papeleta_crear_portal, name='papeleta_crear_portal'),
    path('papeletas/<int:pk>/anular/', views.papeleta_anular_portal, name='papeleta_anular_portal'),
    # Mi Timeline
    path('timeline/', views.mi_timeline, name='mi_timeline'),
    # Mis Documentos (legajo digital del trabajador)
    path('documentos/', views.mis_documentos, name='mis_documentos'),
    # Mi Historial Salarial
    path('historial-salarial/', mi_historial_salarial, name='mi_historial_salarial'),
    # Mi Calendario
    path('mi-calendario/', mi_calendario, name='mi_calendario'),
    path('mi-calendario/eventos/', mi_calendario_eventos, name='mi_calendario_eventos'),
    # Mi Onboarding
    path('mi-onboarding/', mi_onboarding_portal, name='mi_onboarding_portal'),
    # Mi Nómina / Recibos de Sueldo
    path('mi-nomina/', views.mi_nomina, name='portal_mi_nomina'),
    # Mis Evaluaciones de Desempeño
    path('mis-evaluaciones/', views.mis_evaluaciones, name='portal_mis_evaluaciones'),
    # Mis Capacitaciones
    path('mis-capacitaciones/', views.mis_capacitaciones, name='portal_mis_capacitaciones'),
    # Mis Vacaciones
    path('mis-vacaciones/', views.mis_vacaciones, name='portal_mis_vacaciones'),
    # Mis medidas disciplinarias
    path('disciplinaria/', mi_portal_disciplinaria, name='mi_portal_disciplinaria'),
    # Archivos HR
    path('mis-archivos/', views.mis_archivos_hr, name='mis_archivos_hr'),
    # ── API endpoints for mobile ──
    path('api/me/', api_views.api_portal_me, name='api_portal_me'),
    path('api/boletas/', api_views.api_portal_boletas, name='api_portal_boletas'),
    path('api/asistencia/', api_views.api_portal_asistencia, name='api_portal_asistencia'),
    path('api/vacaciones/', api_views.api_portal_vacaciones, name='api_portal_vacaciones'),
]
