"""
URLs del módulo Tareo.
"""
from django.urls import path
from tareo import views

urlpatterns = [
    # Dashboard principal
    path('', views.tareo_dashboard, name='tareo_dashboard'),

    # KPIs
    path('kpis/', views.kpi_dashboard_view, name='tareo_kpis'),

    # Vistas de datos
    path('staff/', views.vista_staff, name='tareo_staff'),
    path('rco/', views.vista_rco, name='tareo_rco'),
    path('banco-horas/', views.banco_horas_view, name='tareo_banco_horas'),

    # Importaciones
    path('importar/', views.importar_view, name='tareo_importar'),
    path('importar/synkro/', views.importar_synkro_view, name='tareo_importar_synkro'),
    path('importar/sunat/', views.importar_sunat_view, name='tareo_importar_sunat'),
    path('importar/s10/', views.importar_s10_view, name='tareo_importar_s10'),

    # Exportaciones
    path('exportar/carga-s10/', views.exportar_carga_s10_view, name='tareo_exportar_s10'),
    path('exportar/cierre/', views.exportar_cierre_view, name='tareo_exportar_cierre'),

    # Configuración
    path('configuracion/', views.configuracion_view, name='tareo_configuracion'),

    # Parámetros (homologaciones, feriados, regímenes)
    path('parametros/', views.parametros_view, name='tareo_parametros'),

    # Endpoints AJAX
    path('ajax/staff-data/', views.ajax_staff_data, name='tareo_ajax_staff'),
    path('ajax/rco-data/', views.ajax_rco_data, name='tareo_ajax_rco'),
    path('ajax/importaciones/', views.ajax_importaciones, name='tareo_ajax_imports'),
]
