from django.urls import path

from . import views_mfa

urlpatterns = [
    path('', views_mfa.mfa_estado, name='mfa_estado'),
    path('activar/', views_mfa.mfa_activar, name='mfa_activar'),
    path('verificar/', views_mfa.mfa_verificar, name='mfa_verificar'),
    path('desactivar/', views_mfa.mfa_desactivar, name='mfa_desactivar'),
]
