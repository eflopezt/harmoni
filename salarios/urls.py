"""URLs del módulo de Estructura Salarial."""
from django.urls import path
from . import views

urlpatterns = [
    # Bandas Salariales
    path('bandas/', views.bandas_panel, name='bandas_panel'),
    path('bandas/crear/', views.banda_crear, name='banda_crear'),
    path('bandas/<int:pk>/editar/', views.banda_editar, name='banda_editar'),
    path('bandas/grafico/', views.bandas_grafico, name='bandas_grafico'),

    # Historial Salarial
    path('historial/', views.historial_panel, name='historial_salarial_panel'),
    path('historial/crear/', views.historial_crear, name='historial_salarial_crear'),

    # Exportación Excel
    path('exportar/analisis/', views.exportar_analisis_salarial, name='salarios_exportar_analisis'),

    # Simulaciones de Incremento
    path('simulaciones/', views.simulacion_panel, name='simulacion_panel'),
    path('simulaciones/crear/', views.simulacion_crear, name='simulacion_crear'),
    path('simulaciones/<int:pk>/', views.simulacion_detalle, name='simulacion_detalle'),
    path('simulaciones/<int:pk>/agregar/', views.simulacion_agregar_detalle, name='simulacion_agregar_detalle'),
    path('simulaciones/<int:pk>/detalle/<int:detalle_pk>/toggle/', views.simulacion_toggle_detalle, name='simulacion_toggle_detalle'),
    path('simulaciones/<int:pk>/aprobar/', views.simulacion_aprobar, name='simulacion_aprobar'),
    path('simulaciones/<int:pk>/aplicar/', views.simulacion_aplicar, name='simulacion_aplicar'),

    # Nuevas vistas analíticas
    path('simulador-comparativo/', views.simulacion_comparativa, name='simulacion_comparativa'),
    path('equidad/', views.equidad_salarial, name='equidad_salarial'),
    path('equidad/simular-ajuste/', views.simular_ajuste_equidad, name='simular_ajuste_equidad'),

    # Portal
    path('mi-historial/', views.mi_historial_salarial, name='mi_historial_salarial'),
]
