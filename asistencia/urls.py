"""
URLs del módulo Asistencia y Control.
"""
from django.urls import path
from asistencia import views, views_ai

urlpatterns = [
    # Dashboard principal
    path('', views.tareo_dashboard, name='asistencia_dashboard'),

    # KPIs
    path('kpis/', views.kpi_dashboard_view, name='asistencia_kpis'),

    # Vistas de datos
    path('vista/', views.vista_unificada, name='asistencia_vista'),
    path('staff/', views.vista_staff, name='asistencia_staff'),
    path('rco/', views.vista_rco, name='asistencia_rco'),
    path('banco-horas/', views.banco_horas_view, name='asistencia_banco_horas'),

    # Importaciones
    path('importar/', views.importar_view, name='asistencia_importar'),
    path('importar/synkro/', views.importar_synkro_view, name='asistencia_importar_synkro'),
    path('importar/sunat/', views.importar_sunat_view, name='asistencia_importar_sunat'),
    path('importar/s10/', views.importar_s10_view, name='asistencia_importar_s10'),

    # Exportaciones
    path('exportar/', views.reportes_exportar_panel, name='asistencia_exportar_panel'),
    path('exportar/carga-s10/', views.exportar_carga_s10_view, name='asistencia_exportar_s10'),
    path('exportar/cierre/', views.exportar_cierre_view, name='asistencia_exportar_cierre'),
    path('exportar/horas-rco/', views.exportar_horas_rco, name='asistencia_exportar_horas_rco'),

    # Relojes Biométricos ZKTeco
    path('relojes/', views.lista_relojes, name='asistencia_relojes_lista'),
    path('relojes/crear/', views.crear_reloj, name='asistencia_relojes_crear'),
    path('relojes/<int:pk>/', views.detalle_reloj, name='asistencia_relojes_detalle'),
    path('relojes/<int:pk>/editar/', views.editar_reloj, name='asistencia_relojes_editar'),
    path('relojes/<int:pk>/eliminar/', views.eliminar_reloj, name='asistencia_relojes_eliminar'),
    # AJAX — Relojes
    path('relojes/<int:pk>/test/', views.ajax_test_reloj, name='asistencia_relojes_test'),
    path('relojes/<int:pk>/sync/', views.ajax_sync_reloj, name='asistencia_relojes_sync'),
    path('relojes/<int:pk>/procesar/', views.ajax_procesar_reloj, name='asistencia_relojes_procesar'),
    path('relojes/<int:pk>/usuarios/', views.ajax_usuarios_reloj, name='asistencia_relojes_usuarios'),

    # Configuración
    path('configuracion/', views.configuracion_view, name='asistencia_configuracion'),
    path('configuracion/ia/test/', views.ia_test_connection, name='asistencia_ia_test'),

    # IA Chat & Insights
    path('ia/status/', views_ai.ai_status, name='ia_status'),
    path('ia/context/', views_ai.ai_context, name='ia_context'),
    path('ia/chat/', views_ai.ai_chat_stream, name='ia_chat'),
    path('ia/insights/', views_ai.ai_insights, name='ia_insights'),
    path('ia/analizar/', views_ai.ai_analyze_chart, name='ia_analyze_chart'),
    path('ia/preguntar/', views_ai.ai_ask_data, name='ia_ask_data'),
    path('ia/exportar/', views_ai.ai_export_report, name='ia_export_report'),
    path('ia/upload/', views_ai.ai_upload_file, name='ia_upload_file'),
    path('ia/documento-editado/', views_ai.ai_download_edited, name='ia_download_edited'),
    path('ia/indexar-embeddings/', views_ai.ai_index_embeddings, name='ia_index_embeddings'),

    # Parámetros (homologaciones, feriados, regímenes)
    path('parametros/', views.parametros_view, name='asistencia_parametros'),

    # Feriados CRUD
    path('feriados/crear/', views.feriado_crear, name='asistencia_feriado_crear'),
    path('feriados/<int:pk>/editar/', views.feriado_editar, name='asistencia_feriado_editar'),
    path('feriados/<int:pk>/eliminar/', views.feriado_eliminar, name='asistencia_feriado_eliminar'),
    path('feriados/cargar-peru/', views.feriados_cargar_peru, name='asistencia_feriados_peru'),

    # Solicitudes de Horas Extra
    path('solicitudes-he/', views.solicitudes_he_view, name='asistencia_solicitudes_he'),
    path('solicitudes-he/crear/', views.solicitud_he_crear, name='asistencia_solicitud_he_crear'),
    path('solicitudes-he/<int:pk>/editar/', views.solicitud_he_editar, name='asistencia_solicitud_he_editar'),
    path('solicitudes-he/<int:pk>/eliminar/', views.solicitud_he_eliminar, name='asistencia_solicitud_he_eliminar'),

    # Papeletas (unificado — importadas + manuales)
    path('papeletas/', views.papeletas_view, name='asistencia_papeletas'),
    path('papeletas/crear/', views.papeleta_crear, name='asistencia_papeleta_crear'),
    path('papeletas/<int:pk>/editar/', views.papeleta_editar, name='asistencia_papeleta_editar'),
    path('papeletas/<int:pk>/eliminar/', views.papeleta_eliminar, name='asistencia_papeleta_eliminar'),
    path('papeletas/<int:pk>/aprobar/', views.papeleta_aprobar, name='asistencia_papeleta_aprobar'),
    path('papeletas/exportar/', views.papeletas_exportar, name='asistencia_papeletas_exportar'),
    path('papeletas/reporte/', views.papeletas_reporte_agrupado, name='asistencia_papeletas_reporte'),

    # Homologaciones CRUD
    path('homologaciones/crear/', views.homologacion_crear, name='asistencia_homologacion_crear'),
    path('homologaciones/<int:pk>/editar/', views.homologacion_editar, name='asistencia_homologacion_editar'),
    path('homologaciones/<int:pk>/eliminar/', views.homologacion_eliminar, name='asistencia_homologacion_eliminar'),

    # Regímenes de Turno CRUD
    path('regimenes/crear/', views.regimen_crear, name='asistencia_regimen_crear'),
    path('regimenes/<int:pk>/editar/', views.regimen_editar, name='asistencia_regimen_editar'),
    path('regimenes/<int:pk>/eliminar/', views.regimen_eliminar, name='asistencia_regimen_eliminar'),

    # Horarios CRUD
    path('horarios/crear/', views.horario_crear, name='asistencia_horario_crear'),
    path('horarios/<int:pk>/editar/', views.horario_editar, name='asistencia_horario_editar'),
    path('horarios/<int:pk>/eliminar/', views.horario_eliminar, name='asistencia_horario_eliminar'),

    # Justificaciones de No-Marcaje (admin)
    path('justificaciones/', views.justificaciones_view, name='asistencia_justificaciones'),
    path('justificaciones/<int:pk>/revisar/', views.justificacion_revisar, name='asistencia_justificacion_revisar'),
    path('justificaciones/<int:pk>/eliminar/', views.justificacion_eliminar, name='asistencia_justificacion_eliminar'),

    # ── Panel Biométrico ──
    path('biometrico/', views.panel_biometrico, name='asistencia_biometrico_panel'),
    path('biometrico/agregar/', views.agregar_dispositivo, name='asistencia_biometrico_agregar'),
    path('biometrico/test/', views.test_dispositivo, name='asistencia_biometrico_test'),
    path('biometrico/logs/', views.logs_sincronizacion, name='asistencia_biometrico_logs'),

    # Reportes Individuales
    path('reportes/', views.reporte_panel, name='asistencia_reportes'),
    path('reportes/<int:personal_id>/pdf/', views.reporte_individual_pdf, name='asistencia_reporte_pdf'),
    path('reportes/<int:personal_id>/enviar/', views.enviar_reporte_email, name='asistencia_reporte_enviar'),
    path('reportes/masivo/', views.reporte_masivo_pdf, name='asistencia_reporte_masivo'),
    path('reportes/enviar-masivo/', views.enviar_reportes_masivo_email, name='asistencia_reporte_enviar_masivo'),

    # Calendario Grid
    path('calendario/', views.calendario_grid, name='asistencia_calendario'),
    path('calendario/exportar/', views.calendario_exportar, name='asistencia_calendario_export'),
    path('ajax/calendario/celda/<int:registro_id>/', views.ajax_calendario_detalle, name='asistencia_calendario_celda'),
    path('ajax/calendario/cambiar/<int:registro_id>/', views.ajax_calendario_cambiar, name='asistencia_calendario_cambiar'),

    # Endpoints AJAX
    path('ajax/staff-data/', views.ajax_staff_data, name='asistencia_ajax_staff'),
    path('ajax/rco-data/', views.ajax_rco_data, name='asistencia_ajax_rco'),
    path('ajax/importaciones/', views.ajax_importaciones, name='asistencia_ajax_imports'),
]
