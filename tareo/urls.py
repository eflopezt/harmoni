"""
URLs del módulo Tareo.
Todas las vistas requieren superusuario (admin).
"""
from django.urls import path
from tareo import views

urlpatterns = [
    # Dashboard principal
    path('', views.tareo_dashboard, name='tareo_dashboard'),

    # Vistas de datos
    path('staff/', views.vista_staff, name='tareo_staff'),
    path('rco/', views.vista_rco, name='tareo_rco'),
    path('banco-horas/', views.banco_horas_view, name='tareo_banco_horas'),

    # Importación web
    path('importar/', views.importar_view, name='tareo_importar'),

    # Parámetros / configuración
    path('parametros/', views.parametros_view, name='tareo_parametros'),

    # Endpoints AJAX
    path('ajax/staff-data/', views.ajax_staff_data, name='tareo_ajax_staff'),
    path('ajax/rco-data/', views.ajax_rco_data, name='tareo_ajax_rco'),
    path('ajax/importaciones/', views.ajax_importaciones, name='tareo_ajax_imports'),
]
