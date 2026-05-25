"""
URLs para vistas del módulo personal.
"""
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Home
    path('', views.home, name='home'),
    
    # Auth — login con rate limit (security audit fix 2026-05-20)
    path('login/', views.RateLimitedLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('cuenta/cambiar-password/',
         auth_views.PasswordChangeView.as_view(
             template_name='registration/password_change.html',
             success_url='/cuenta/cambiar-password/hecho/',
         ),
         name='password_change'),
    path('cuenta/cambiar-password/hecho/',
         auth_views.PasswordChangeDoneView.as_view(
             template_name='registration/password_change_done.html',
         ),
         name='password_change_done'),
    # Recuperación de contraseña
    path('cuenta/recuperar/',
         auth_views.PasswordResetView.as_view(
             template_name='registration/password_reset_form.html',
             email_template_name='registration/password_reset_email.txt',
             subject_template_name='registration/password_reset_subject.txt',
             success_url='/cuenta/recuperar/enviado/',
         ),
         name='password_reset'),
    path('cuenta/recuperar/enviado/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='registration/password_reset_done.html',
         ),
         name='password_reset_done'),
    path('cuenta/recuperar/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html',
             success_url='/cuenta/recuperar/completado/',
         ),
         name='password_reset_confirm'),
    path('cuenta/recuperar/completado/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html',
         ),
         name='password_reset_complete'),
    
    # Áreas
    path('areas/', views.area_list, name='area_list'),
    path('areas/crear/', views.area_create, name='area_create'),
    path('areas/exportar/', views.area_export, name='area_export'),
    path('areas/importar/', views.area_import, name='area_import'),
    path('areas/<int:pk>/', views.area_detail, name='area_detail'),
    path('areas/<int:pk>/editar/', views.area_update, name='area_update'),
    path('areas/<int:pk>/toggle/', views.area_toggle, name='area_toggle'),
    path('areas/<int:pk>/eliminar/', views.area_delete, name='area_delete'),

    # SubÁreas
    path('subareas/', views.subarea_list, name='subarea_list'),
    path('subareas/crear/', views.subarea_create, name='subarea_create'),
    path('subareas/exportar/', views.subarea_export, name='subarea_export'),
    path('subareas/importar/', views.subarea_import, name='subarea_import'),
    path('subareas/<int:pk>/', views.subarea_detail, name='subarea_detail'),
    path('subareas/<int:pk>/editar/', views.subarea_update, name='subarea_update'),
    path('subareas/<int:pk>/toggle/', views.subarea_toggle, name='subarea_toggle'),
    path('subareas/<int:pk>/eliminar/', views.subarea_delete, name='subarea_delete'),
    
    # Personal
    path('personal/', views.personal_list, name='personal_list'),
    # Aliases populares
    path('empleados/', views.personal_list, name='empleados_list_alias'),
    path('personal/crear/', views.personal_create, name='personal_create'),
    path('personal/express/', views.personal_create_express, name='personal_create_express'),
    path('personal/express/exito/<int:pk>/', views.personal_express_exito, name='personal_express_exito'),
    path('personal/<int:pk>/', views.personal_detail, name='personal_detail'),
    path('personal/<int:pk>/drawer/', views.personal_drawer_data, name='personal_drawer_data'),
    path('personal/<int:pk>/inline-edit/', views.personal_inline_edit, name='personal_inline_edit'),
    path('personal/cesar-batch/', views.personal_cesar_batch, name='personal_cesar_batch'),
    path('personal/empleado/<int:pk>/', views.personal_detail, name='personal_detail_alias'),
    path('personal/<int:pk>/timeline/', views.timeline_empleado, name='timeline_empleado'),
    path('personal/<int:pk>/editar/', views.personal_update, name='personal_update'),
    path('personal/exportar/', views.personal_export, name='personal_export'),
    path('personal/importar/', views.personal_import, name='personal_import'),

    # Importación masiva (nuevo sistema con preview)
    path('personal/importar/v2/', views.import_upload, name='personal_import_upload'),
    path('personal/importar/confirmar/', views.import_confirm, name='personal_import_confirm'),
    path('personal/importar/plantilla/', views.import_template_download, name='personal_import_template'),
    path('personal/importar/validar/', views.import_validate_ajax, name='personal_import_validate'),
    
    # Roster
    # path('roster/', views.roster_list, name='roster_list'),  # Oculto
    path('roster/matricial/', views.roster_matricial, name='roster_matricial'),
    path('roster/crear/', views.roster_create, name='roster_create'),
    path('roster/<int:pk>/editar/', views.roster_update, name='roster_update'),
    path('roster/exportar/', views.roster_export, name='roster_export'),
    path('roster/importar/', views.roster_import, name='roster_import'),
    path('roster/update-cell/', views.roster_update_cell, name='roster_update_cell'),

    # Roster Quincenal Gastronomico (drag&drop)
    path('roster/gastro/', views.roster_gastro_grid, name='roster_gastro_grid'),
    path('roster/gastro/asignar/', views.roster_gastro_asignar, name='roster_gastro_asignar'),
    path('roster/gastro/asignar-bulk/', views.roster_gastro_asignar_bulk, name='roster_gastro_asignar_bulk'),
    path('roster/gastro/validar/', views.roster_gastro_validar, name='roster_gastro_validar'),
    path('roster/gastro/pdf/', views.roster_gastro_pdf, name='roster_gastro_pdf'),
    
    # Sistema de Aprobaciones
    path('aprobaciones/', views.dashboard_aprobaciones, name='dashboard_aprobaciones'),
    path('roster/cambios-pendientes/', views.cambios_pendientes, name='cambios_pendientes'),
    path('roster/aprobar/<int:pk>/', views.aprobar_cambio, name='aprobar_cambio'),
    path('roster/rechazar/<int:pk>/', views.rechazar_cambio, name='rechazar_cambio'),
    path('roster/enviar-aprobacion/', views.enviar_cambios_aprobacion, name='enviar_cambios_aprobacion'),
    path('roster/aprobar-lote/', views.aprobar_lote, name='aprobar_lote'),
    path('roster/rechazar-lote/', views.rechazar_lote, name='rechazar_lote'),
    
    # Gestión de Usuarios
    path('usuarios/', views.usuario_list, name='usuario_list'),
    path('usuarios/vincular/', views.usuario_vincular, name='usuario_vincular'),
    path('usuarios/crear-vincular/', views.usuario_crear_y_vincular, name='usuario_crear_y_vincular'),
    path('usuarios/desvincular/<int:user_id>/', views.usuario_desvincular, name='usuario_desvincular'),
    path('usuarios/sincronizar/', views.usuario_sincronizar, name='usuario_sincronizar'),
    path('personal/<int:personal_pk>/portal/crear/', views.portal_crear_acceso, name='portal_crear_acceso'),
    path('personal/<int:personal_pk>/portal/reset/', views.portal_reset_credenciales, name='portal_reset_credenciales'),

    # Gestión Completa de Usuarios (interfaz ERP)
    path('gestion-usuarios/', views.gestion_usuario_lista, name='gestion_usuario_lista'),
    path('gestion-usuarios/crear/', views.gestion_usuario_crear, name='gestion_usuario_crear'),
    path('gestion-usuarios/<int:pk>/', views.gestion_usuario_detalle, name='gestion_usuario_detalle'),
    path('gestion-usuarios/<int:pk>/editar/', views.gestion_usuario_editar, name='gestion_usuario_editar'),
    path('gestion-usuarios/<int:pk>/toggle-activo/', views.gestion_usuario_toggle_activo, name='gestion_usuario_toggle_activo'),
    path('gestion-usuarios/<int:pk>/reset-password/', views.gestion_usuario_reset_password, name='gestion_usuario_reset_password'),
    path('gestion-usuarios/<int:pk>/impersonar/', views.gestion_usuario_impersonar, name='gestion_usuario_impersonar'),
    path('gestion-usuarios/dejar-impersonar/', views.gestion_usuario_dejar_impersonar, name='gestion_usuario_dejar_impersonar'),
    path('gestion-usuarios/bulk/', views.gestion_usuario_bulk, name='gestion_usuario_bulk'),
    path('gestion-usuarios/permiso-ajax/', views.gestion_usuario_permiso_ajax, name='gestion_usuario_permiso_ajax'),
    path('gestion-usuarios/prefill-perfil/', views.gestion_usuario_prefill_perfil, name='gestion_usuario_prefill_perfil'),

    # Gestión de Accesos (RBAC)
    path('accesos/', views.accesos_gestion, name='accesos_gestion'),
    path('accesos/asignar/', views.accesos_asignar_perfil, name='accesos_asignar_perfil'),
    path('accesos/usuario/<int:personal_pk>/', views.accesos_detalle_usuario, name='accesos_detalle_usuario'),
    path('accesos/modulo/', views.accesos_toggle_modulo, name='accesos_toggle_modulo'),

    # Contratos y Período de Prueba
    path('contratos/', views.contratos_panel, name='contratos_panel'),
    path('contratos/lista/', views.contratos_lista, name='contratos_lista'),
    path('contratos/exportar/', views.contratos_exportar_excel, name='contratos_exportar_excel'),
    path('contratos/<int:pk>/detalle/', views.contrato_detalle, name='contrato_detalle'),
    path('contratos/<int:pk>/editar/', views.contrato_editar, name='contrato_editar'),
    path('contratos/<int:personal_pk>/crear/', views.contrato_crear, name='contrato_crear'),
    path('contratos/obj/<int:pk>/editar/', views.contrato_editar_obj, name='contrato_editar_obj'),
    path('contratos/obj/<int:pk>/renovar/', views.contrato_renovar, name='contrato_renovar'),
    path('contratos/obj/<int:contrato_pk>/adenda/', views.adenda_crear, name='adenda_crear'),
    path('contratos/obj/<int:pk>/pdf/', views.contrato_generar_pdf, name='contrato_generar_pdf'),
    path('contratos/obj/<int:pk>/prorroga-pdf/', views.prorroga_generar_pdf, name='prorroga_generar_pdf'),
    path('contratos/adenda/<int:pk>/pdf/', views.adenda_generar_pdf, name='adenda_generar_pdf'),
    path('contratos/obj/<int:pk>/importar/', views.contrato_importar_plantilla, name='contrato_importar_plantilla'),
    path('contratos/obj/<int:pk>/analizar-ia/', views.contrato_analizar_ia, name='contrato_analizar_ia'),
    path('contratos/obj/<int:pk>/enviar-email/', views.contrato_enviar_email, name='contrato_enviar_email'),
    path('contratos/envio-masivo/', views.contratos_envio_masivo, name='contratos_envio_masivo'),
    path('contratos/api/stats/', views.contratos_api_stats, name='contratos_api_stats'),
    path('contratos/api/alertas/', views.contratos_alertas_json, name='contratos_alertas_json'),

    # Plantillas de Contrato (CRUD)
    path('contratos/plantillas/', views.plantilla_contrato_lista, name='plantilla_contrato_lista'),
    path('contratos/plantillas/crear/', views.plantilla_contrato_crear, name='plantilla_contrato_crear'),
    path('contratos/plantillas/importar/', views.plantilla_contrato_importar, name='plantilla_contrato_importar'),
    path('contratos/plantillas/<int:pk>/editar/', views.plantilla_contrato_editar, name='plantilla_contrato_editar'),
    path('contratos/plantillas/<int:pk>/eliminar/', views.plantilla_contrato_eliminar, name='plantilla_contrato_eliminar'),
    path('contratos/plantillas/<int:pk>/ia/', views.plantilla_contrato_ia, name='plantilla_contrato_ia'),
    path('contratos/plantillas/<int:pk>/aplicar-ia/', views.plantilla_contrato_aplicar_ia, name='plantilla_contrato_aplicar_ia'),
    path('contratos/plantillas/<int:pk>/', views.plantilla_contrato_detalle, name='plantilla_contrato_detalle'),

    # Command Palette + Smart Alerts + HR Ask (APIs globales)
    path('api/cmd-search/', views.cmd_search, name='cmd_search'),
    path('api/alertas-dia/', views.alertas_dia, name='alertas_dia'),
    path('api/hr-ask/', views.hr_ask, name='hr_ask'),

    # Cese y Reactivación
    path('personal/<int:pk>/dar-baja/', views.personal_dar_baja, name='personal_dar_baja'),
    path('personal/<int:pk>/reactivar/', views.personal_reactivar, name='personal_reactivar'),

    # Wizard "Cesar trabajador" (Sprint 2 Liquidaciones — 3 pasos)
    path('personal/<int:personal_id>/cesar/',           views.cesar_wizard_paso1,
         name='personal_cesar_paso1'),
    path('personal/<int:personal_id>/cesar/preview/',   views.cesar_wizard_preview,
         name='personal_cesar_preview'),
    path('personal/<int:personal_id>/cesar/confirmar/', views.cesar_wizard_confirmar,
         name='personal_cesar_confirmar'),

    # Organigrama
    path('organigrama/', views.organigrama_view, name='organigrama_erp'),
    path('organigrama/gestion/', views.organigrama_gestion, name='organigrama_gestion'),
    path('api/organigrama/data/', views.organigrama_data, name='organigrama_data'),
    path('api/organigrama/update-parent/', views.organigrama_update_parent, name='organigrama_update_parent'),
    path('api/organigrama/analizar/', views.organigrama_analizar, name='organigrama_analizar'),
    path('api/organigrama/auto-asignar/', views.organigrama_auto_asignar, name='organigrama_auto_asignar'),
    path('api/organigrama/asignar-jefe/', views.organigrama_asignar_jefe_area, name='organigrama_asignar_jefe'),
    path('api/organigrama/bulk-reporta/', views.organigrama_bulk_reporta, name='organigrama_bulk_reporta'),

    # Reportes RRHH
    path('reportes/', views.reportes_panel, name='reportes_panel'),
    path('reportes/plantilla/', views.reporte_plantilla, name='reporte_plantilla'),
    path('reportes/asistencia/', views.reporte_asistencia_mensual, name='reporte_asistencia'),
    path('reportes/he/', views.reporte_he_detallado, name='reporte_he'),
    path('reportes/vacaciones/', views.reporte_vacaciones, name='reporte_vacaciones'),
    path('reportes/contratos/', views.reporte_contratos, name='reporte_contratos'),

    # Activos / Herramientas asignadas
    path('activos/', views.activos_panel, name='activos_panel'),
    path('activos/<int:personal_pk>/asignar/', views.activo_asignar, name='activo_asignar'),
    path('activos/<int:pk>/devolver/', views.activo_devolver, name='activo_devolver'),
]
