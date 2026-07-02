"""
URLs del modulo de Reclutamiento y Seleccion.
"""
from django.urls import path
from . import views
from . import views_requisicion

urlpatterns = [
    # ── Admin: Vacantes ──
    path('', views.vacantes_panel, name='vacantes_panel'),
    path('nueva/', views.vacante_crear, name='vacante_crear'),
    path('<int:pk>/', views.vacante_detalle, name='vacante_detalle'),
    path('<int:pk>/editar/', views.vacante_editar, name='vacante_editar'),

    # ── Aprobación de requisición ──
    path('<int:pk>/solicitar-aprobacion/', views_requisicion.vacante_solicitar_aprobacion, name='vacante_solicitar_aprobacion'),
    path('<int:pk>/aprobar/', views_requisicion.vacante_aprobar, name='vacante_aprobar'),
    path('<int:pk>/rechazar/', views_requisicion.vacante_rechazar, name='vacante_rechazar'),

    # ── Admin: Postulaciones ──
    path('<int:vacante_pk>/postulacion/nueva/', views.postulacion_crear, name='postulacion_crear'),
    path('cv/express/', views.subir_cv_express, name='subir_cv_express'),
    path('<int:vacante_pk>/cv/express/', views.subir_cv_express, name='subir_cv_express_vacante'),
    path('funnel/', views.funnel_reclutamiento, name='funnel_reclutamiento'),
    path('candidatos/bulk/', views.candidatos_bulk_import, name='candidatos_bulk_import'),
    path('candidatos/bulk/plantilla.xlsx', views.candidatos_bulk_plantilla, name='candidatos_bulk_plantilla'),
    path('postulacion/<int:pk>/score/', views.postulacion_score_detalle, name='postulacion_score_detalle'),
    path('postulacion/<int:pk>/ai-summary/', views.postulacion_ai_summary, name='postulacion_ai_summary'),
    path('postulacion/<int:pk>/pdf/', views.postulacion_pdf, name='postulacion_pdf'),
    path('comparar/', views.comparar_candidatos, name='comparar_candidatos'),
    path('banco-talento/', views.banco_de_talento, name='banco_de_talento'),
    path('calendario/', views.calendario_entrevistas, name='calendario_entrevistas'),
    path('stats-reclutadores/', views.stats_reclutadores, name='stats_reclutadores'),
    path('stats-reclutadores/pdf/', views.stats_reclutadores_pdf, name='stats_reclutadores_pdf'),
    path('mi-dia/', views.mi_dia_reclutador, name='mi_dia_reclutador'),
    path('postulacion/<int:pk>/reactivar/', views.reactivar_candidato, name='reactivar_candidato'),
    path('postulacion/<int:pk>/', views.postulacion_detalle, name='postulacion_detalle'),
    path('postulacion/<int:pk>/mover/', views.postulacion_mover_etapa, name='postulacion_mover_etapa'),
    path('postulacion/<int:pk>/descartar/', views.postulacion_descartar, name='postulacion_descartar'),
    path('postulacion/<int:pk>/contratar/', views.contratar_candidato, name='contratar_candidato'),

    # ── Admin: Notas y Entrevistas ──
    path('postulacion/<int:postulacion_pk>/nota/', views.nota_agregar, name='nota_agregar'),
    path('postulacion/<int:postulacion_pk>/entrevista/', views.entrevista_crear, name='entrevista_crear'),
    path('entrevista/<int:pk>/resultado/', views.entrevista_resultado, name='entrevista_resultado'),

    # ── Admin: Pipeline ──
    path('pipeline/', views.pipeline_panel, name='pipeline_panel'),
    path('pipeline/bulk/', views.pipeline_bulk_action, name='pipeline_bulk_action'),
    path('postulacion/<int:pk>/tag/', views.postulacion_toggle_tag, name='postulacion_toggle_tag'),

    # ── Admin: Exportar candidatos Excel ──
    path('<int:pk>/candidatos/exportar/', views.exportar_candidatos_excel, name='reclutamiento_exportar_candidatos'),

    # ── Admin: Configuracion Etapas ──
    path('etapas/', views.etapas_config, name='etapas_config'),
    path('etapas/crear/', views.etapa_crear, name='etapa_crear'),

    # ── Admin: Publicar en Plataformas Externas ──
    path('<int:pk>/publicar/', views.publicar_en_plataformas, name='reclutamiento_publicar'),

    # ── Admin: Scoring de candidatos ──
    path('<int:pk>/scoring/', views.scoring_candidatos, name='reclutamiento_scoring'),

    # ── Admin: Historial de postulacion ──
    path('postulaciones/<int:pk>/historial/', views.postulacion_historial, name='postulacion_historial'),

    # ── Admin: Agendar entrevista (standalone) ──
    path('postulaciones/<int:pk>/entrevista/', views.entrevista_agendar, name='entrevista_agendar'),

    # ── Admin: Publicar oferta (accion rapida) ──
    path('<int:pk>/publicar-rapido/', views.publicar_oferta, name='vacante_publicar'),

    # ── Admin: Dashboard de reclutamiento (legacy → redirect a Mi Día) ──
    path('dashboard/', views.dashboard_reclutamiento, name='reclutamiento_dashboard'),

    # ── Publico: Portal de Empleo ──
    path('empleo/', views.portal_empleo, name='portal_empleo'),
    path('empleo/<int:pk>/postular/', views.portal_postular, name='portal_postular'),

    # ── API: IA ──
    path('api/generar-descripcion/', views.api_generar_descripcion, name='reclutamiento_api_generar_desc'),
]
