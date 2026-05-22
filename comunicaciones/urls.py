"""
URLs del módulo Comunicaciones Inteligentes.
"""
from django.urls import path
from . import views
from . import views_notif
from . import views_whatsapp

urlpatterns = [
    # ── Admin: Notificaciones ──
    path('', views.notificaciones_panel, name='com_notificaciones_panel'),

    # ── Admin: Plantillas ──
    path('plantillas/', views.plantillas_panel, name='com_plantillas_panel'),
    path('plantillas/crear/', views.plantilla_crear, name='com_plantilla_crear'),
    path('plantillas/<int:pk>/editar/', views.plantilla_editar, name='com_plantilla_editar'),

    # ── Admin: Comunicados ──
    path('comunicados/', views.comunicados_panel, name='com_comunicados_panel'),
    path('comunicados/crear/', views.comunicado_crear, name='com_comunicado_crear'),
    path('comunicados/<int:pk>/', views.comunicado_detalle, name='com_comunicado_detalle'),
    path('comunicados/<int:pk>/enviar/', views.comunicado_enviar, name='com_comunicado_enviar'),

    # ── Admin: SMTP ──
    path('config-smtp/', views.config_smtp, name='com_config_smtp'),
    path('config-smtp/test/', views.test_smtp, name='com_test_smtp'),

    # ── Admin: WhatsApp ──
    path('whatsapp/', views_whatsapp.whatsapp_config, name='com_whatsapp_config'),
    path('whatsapp/test/', views_whatsapp.whatsapp_test, name='com_whatsapp_test'),
    path('whatsapp/test-connection/', views_whatsapp.whatsapp_test_connection, name='com_whatsapp_test_connection'),
    path('whatsapp/send-employee/', views_whatsapp.whatsapp_send_to_employee, name='com_whatsapp_send_employee'),

    # ── Portal: mis notificaciones ──
    path('mis-notificaciones/', views.mis_notificaciones, name='mis_notificaciones_com'),
    path('mis-notificaciones/<int:pk>/leer/', views.notificacion_leer, name='com_notificacion_leer'),

    # ── Portal: mis comunicados ──
    path('mis-comunicados/', views.mis_comunicados, name='mis_comunicados_com'),
    path('mis-comunicados/<int:pk>/confirmar/', views.comunicado_confirmar, name='com_comunicado_confirmar'),

    # ── API AJAX: notificaciones in-app (header badge) ──
    path('notificaciones/json/', views_notif.notificaciones_json, name='notificaciones_json'),
    path('notificaciones/<int:pk>/leer/', views_notif.notificacion_marcar_leida, name='notificacion_marcar_leida'),
    path('notificaciones/leer-todas/', views_notif.notificaciones_marcar_todas, name='notificaciones_marcar_todas'),

    # ── API: count no-leídas y recientes (para header bell externo) ──
    path('api/no-leidas/', views_notif.notificaciones_api_count, name='notificaciones_api_count'),
    path('api/recientes/', views_notif.notificaciones_api_recientes, name='notificaciones_api_recientes'),

    # ── Campañas masivas segmentadas ──
    path('campanas/', views.campanas_panel, name='campanas_panel'),
    path('campanas/', views.campanas_panel, name='com_campana_list'),
    path('campanas/', views.campanas_panel, name='com_campanas_panel'),
    path('campanas/crear/', views.campanas_panel, name='com_campana_crear'),
    path('campanas/<int:pk>/', views.campana_detalle, name='campana_detalle'),
    path('campanas/<int:pk>/', views.campana_detalle, name='com_campana_detalle'),
    path('campanas/<int:pk>/enviar/', views.campana_enviar, name='campana_enviar'),
    path('campanas/<int:pk>/enviar/', views.campana_enviar, name='com_campana_enviar'),
    path('campanas/preview-destinatarios/', views.campana_preview_destinatarios, name='campana_preview_destinatarios'),
]
