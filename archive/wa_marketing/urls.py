from django.urls import path
from . import views

urlpatterns = [
    # Webhook entrante del sidecar (sin login, autenticado por token)
    path('api/wa/incoming/', views.webhook_incoming, name='wa_webhook_incoming'),

    # UI staff
    path('wa/', views.inbox, name='wa_inbox'),
    path('wa/leads/', views.leads, name='wa_leads'),
    path('wa/broadcast/', views.broadcast, name='wa_broadcast'),
    path('wa/<int:pk>/', views.conversacion_detalle, name='wa_conversacion'),
    path('wa/<int:pk>/responder/', views.responder, name='wa_responder'),
    path('wa/<int:pk>/estado/', views.cambiar_estado, name='wa_cambiar_estado'),

    # Sidecar status / QR
    path('wa/sidecar/status/', views.sidecar_status, name='wa_sidecar_status'),
    path('wa/sidecar/qr/', views.sidecar_qr, name='wa_sidecar_qr'),
]
