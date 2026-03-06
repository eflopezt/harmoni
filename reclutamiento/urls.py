"""
URLs del modulo de Reclutamiento y Seleccion.
"""
from django.urls import path
from . import views

urlpatterns = [
    # ── Admin: Vacantes ──
    path('', views.vacantes_panel, name='vacantes_panel'),
    path('nueva/', views.vacante_crear, name='vacante_crear'),
    path('<int:pk>/', views.vacante_detalle, name='vacante_detalle'),
    path('<int:pk>/editar/', views.vacante_editar, name='vacante_editar'),

    # ── Admin: Postulaciones ──
    path('<int:vacante_pk>/postulacion/nueva/', views.postulacion_crear, name='postulacion_crear'),
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

    # ── Admin: Mover etapa AJAX ──
    path('postulaciones/<int:pk>/mover/', views.mover_etapa, name='mover_etapa'),

    # ── Admin: Publicar oferta (accion rapida) ──
    path('<int:pk>/publicar-rapido/', views.publicar_oferta, name='vacante_publicar'),

    # ── Admin: Dashboard de reclutamiento ──
    path('dashboard/', views.dashboard_reclutamiento, name='reclutamiento_dashboard'),

    # ── Publico: Portal de Empleo ──
    path('empleo/', views.portal_empleo, name='portal_empleo'),
    path('empleo/<int:pk>/postular/', views.portal_postular, name='portal_postular'),
]
