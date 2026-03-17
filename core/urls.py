"""URLs del módulo core."""
from django.urls import path
from core import views
from core import views_reports

urlpatterns = [
    path('auditoria/', views.audit_log_view, name='audit_log'),
    path('buscar/', views.global_search, name='global_search'),
    path('buscar/pagina/', views.busqueda_pagina, name='busqueda_pagina'),
    path('preferencias/', views.preferencias_usuario, name='preferencias_usuario'),
    path('preferencias/api/', views.preferencias_api, name='preferencias_api'),
    path('permisos-modulos/', views.permisos_panel, name='permisos_modulos_panel'),
    path('permisos-modulos/<int:user_id>/guardar/', views.permisos_guardar, name='permisos_modulos_guardar'),

    # Reportes PDF ejecutivos
    path('reportes/planilla/pdf/', views_reports.reporte_planilla_pdf, name='reporte_planilla_pdf'),
    path('reportes/personal/pdf/', views_reports.reporte_personal_pdf, name='reporte_personal_pdf'),
    path('reportes/asistencia/pdf/', views_reports.reporte_asistencia_pdf, name='reporte_asistencia_pdf'),
    path('reportes/vacaciones/pdf/', views_reports.reporte_vacaciones_pdf, name='reporte_vacaciones_pdf'),
]
