"""URLs del módulo de Capacitaciones / LMS."""
from django.urls import path
from . import views

urlpatterns = [
    # Admin — Panel
    path('', views.capacitaciones_panel, name='capacitaciones_panel'),
    path('nueva/', views.capacitacion_crear, name='capacitacion_crear'),
    path('<int:pk>/', views.capacitacion_detalle, name='capacitacion_detalle'),
    path('<int:pk>/completar/', views.capacitacion_completar, name='capacitacion_completar'),

    # Admin — Participantes
    path('<int:cap_pk>/agregar/', views.participante_agregar, name='participante_agregar'),
    path('asistencia/<int:pk>/', views.participante_asistencia, name='participante_asistencia'),

    # Admin — Exportaciones y documentos
    path('<int:capacitacion_pk>/exportar/excel/', views.exportar_asistentes_excel, name='capacitacion_export_asistentes'),
    path('asistencia/<int:asistencia_pk>/certificado/', views.generar_certificado_pdf, name='capacitacion_certificado_pdf'),

    # Admin — Requerimientos y cumplimiento
    path('requerimientos/', views.requerimientos_panel, name='requerimientos_panel'),
    path('incumplimientos/', views.incumplimientos_panel, name='incumplimientos_panel'),
    path('gastro/', views.certificaciones_gastro, name='certificaciones_gastro'),

    # Admin — Nuevas funcionalidades
    path('asignacion-masiva/', views.asignacion_masiva, name='capacitacion_asignacion'),
    path('<int:pk>/estadisticas/', views.capacitacion_estadisticas, name='capacitacion_estadisticas'),
    path('mis-requerimientos/', views.mis_requerimientos, name='capacitacion_requerimientos'),
    path('calendario/', views.calendario_capacitaciones, name='capacitacion_calendario'),
    path('<int:pk>/duplicar/', views.capacitacion_duplicar, name='capacitacion_duplicar'),

    # Portal trabajador
    path('mis/', views.mis_capacitaciones, name='mis_capacitaciones'),
]
