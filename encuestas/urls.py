from django.urls import path
from . import views

urlpatterns = [
    # Admin
    path('', views.encuestas_panel, name='encuestas_panel'),
    path('crear/', views.encuesta_crear, name='encuesta_crear'),
    path('<int:pk>/', views.encuesta_detalle, name='encuesta_detalle'),
    path('<int:enc_pk>/pregunta/agregar/', views.pregunta_agregar, name='pregunta_agregar'),
    path('pregunta/<int:pk>/eliminar/', views.pregunta_eliminar, name='pregunta_eliminar'),
    path('<int:pk>/activar/', views.encuesta_activar, name='encuesta_activar'),
    path('<int:pk>/cerrar/', views.encuesta_cerrar, name='encuesta_cerrar'),
    path('<int:pk>/resultados/', views.encuesta_resultados, name='encuesta_resultados'),

    # Acciones adicionales
    path('<int:pk>/exportar/', views.encuesta_exportar_excel, name='encuesta_exportar'),
    path('<int:pk>/duplicar/', views.encuesta_duplicar, name='encuesta_duplicar'),
    path('<int:pk>/recordatorio/', views.encuesta_recordatorio, name='encuesta_recordatorio'),

    # Portal
    path('mis-encuestas/', views.mis_encuestas, name='mis_encuestas'),
    path('responder/<int:pk>/', views.responder_encuesta, name='responder_encuesta'),

    # ── Pulse Semanal ──
    path('pulse/', views.pulse_dashboard, name='pulse_dashboard'),
    path('pulse/historico/', views.pulse_historico, name='pulse_historico'),
    path('pulse/responder/', views.pulse_responder, name='pulse_responder'),
]
