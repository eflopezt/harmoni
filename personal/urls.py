"""
URLs para vistas del módulo personal.
"""
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Home
    path('', views.home, name='home'),
    
    # Auth
    path('login/', auth_views.LoginView.as_view(), name='login'),
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
    path('personal/crear/', views.personal_create, name='personal_create'),
    path('personal/<int:pk>/', views.personal_detail, name='personal_detail'),
    path('personal/<int:pk>/timeline/', views.timeline_empleado, name='timeline_empleado'),
    path('personal/<int:pk>/editar/', views.personal_update, name='personal_update'),
    path('personal/exportar/', views.personal_export, name='personal_export'),
    path('personal/importar/', views.personal_import, name='personal_import'),
    
    # Roster
    # path('roster/', views.roster_list, name='roster_list'),  # Oculto
    path('roster/matricial/', views.roster_matricial, name='roster_matricial'),
    path('roster/crear/', views.roster_create, name='roster_create'),
    path('roster/<int:pk>/editar/', views.roster_update, name='roster_update'),
    path('roster/exportar/', views.roster_export, name='roster_export'),
    path('roster/importar/', views.roster_import, name='roster_import'),
    path('roster/update-cell/', views.roster_update_cell, name='roster_update_cell'),
    
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

    # Gestión de Accesos (RBAC)
    path('accesos/', views.accesos_gestion, name='accesos_gestion'),
    path('accesos/asignar/', views.accesos_asignar_perfil, name='accesos_asignar_perfil'),
    path('accesos/usuario/<int:personal_pk>/', views.accesos_detalle_usuario, name='accesos_detalle_usuario'),
    path('accesos/modulo/', views.accesos_toggle_modulo, name='accesos_toggle_modulo'),

    # Contratos y Período de Prueba
    path('contratos/', views.contratos_panel, name='contratos_panel'),
    path('contratos/lista/', views.contratos_lista, name='contratos_lista'),
    path('contratos/<int:pk>/editar/', views.contrato_editar, name='contrato_editar'),
    path('contratos/api/stats/', views.contratos_api_stats, name='contratos_api_stats'),

    # Command Palette + Smart Alerts + HR Ask (APIs globales)
    path('api/cmd-search/', views.cmd_search, name='cmd_search'),
    path('api/alertas-dia/', views.alertas_dia, name='alertas_dia'),
    path('api/hr-ask/', views.hr_ask, name='hr_ask'),

    # Cese y Reactivación
    path('personal/<int:pk>/dar-baja/', views.personal_dar_baja, name='personal_dar_baja'),
    path('personal/<int:pk>/reactivar/', views.personal_reactivar, name='personal_reactivar'),

    # Reportes RRHH
    path('reportes/', views.reportes_panel, name='reportes_panel'),
    path('reportes/plantilla/', views.reporte_plantilla, name='reporte_plantilla'),
    path('reportes/asistencia/', views.reporte_asistencia_mensual, name='reporte_asistencia'),
    path('reportes/he/', views.reporte_he_detallado, name='reporte_he'),
    path('reportes/vacaciones/', views.reporte_vacaciones, name='reporte_vacaciones'),
    path('reportes/contratos/', views.reporte_contratos, name='reporte_contratos'),
]
