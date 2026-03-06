"""
Analytics & People Intelligence — URLs.
"""
from django.urls import path
from . import views

urlpatterns = [
    # Dashboard principal
    path('', views.dashboard, name='analytics_dashboard'),
    path('headcount/', views.headcount, name='analytics_headcount'),

    # Nuevas vistas analíticas
    path('attrition/', views.attrition_risk, name='analytics_attrition'),
    path('salarios/', views.salary_analytics, name='analytics_salarios'),
    path('predictive/', views.predictive_insights, name='analytics_predictive'),

    # Snapshots KPI
    path('snapshots/', views.snapshots_list, name='analytics_snapshots'),
    path('snapshots/generar/', views.generar_snapshot_view, name='analytics_generar_snapshot'),

    # Alertas
    path('alertas/', views.alertas_list, name='analytics_alertas'),
    path('alertas/<int:pk>/resolver/', views.resolver_alerta, name='analytics_resolver_alerta'),
    path('alertas/generar/', views.generar_alertas_view, name='analytics_generar_alertas'),

    # Dashboard IA Ejecutivo
    path('ia/', views.ai_dashboard, name='analytics_ai_dashboard'),

    # Dashboard Widgets personalizados (IA → guardar gráficos)
    path('widgets/', views.list_widgets, name='analytics_list_widgets'),
    path('widgets/guardar/', views.save_widget, name='analytics_save_widget'),
    path('widgets/<int:pk>/eliminar/', views.delete_widget, name='analytics_delete_widget'),

    # API JSON (para gráficos y widgets)
    path('api/kpi/', views.api_kpi_actual, name='analytics_api_kpi'),
    path('api/tendencias/', views.api_tendencias, name='analytics_api_tendencias'),
    path('api/resumen/', views.analytics_resumen_ajax, name='analytics_resumen_ajax'),
    path('api/team-health/', views.api_team_health, name='analytics_api_team_health'),
    path('api/rotacion-riesgo/', views.api_rotacion_riesgo_top, name='analytics_api_rotacion_riesgo'),
]
