from django.urls import path
from . import views
from . import views_okr
from . import views_360

urlpatterns = [
    # ── Evaluaciones 360° (módulo dedicado) ──
    path('360/', views_360.panel_360, name='evaluacion_360_panel'),
    path('360/crear/', views_360.crear_360, name='evaluacion_360_crear'),
    path('360/<int:pk>/', views_360.detalle_360, name='evaluacion_360_detalle'),
    path('360/<int:pk>/pdf/', views_360.pdf_360, name='evaluacion_360_pdf'),
    path('360/<int:pk>/cerrar/', views_360.cerrar_360, name='evaluacion_360_cerrar'),
    path('360/<int:pk>/responder/<int:participante_pk>/', views_360.responder_360,
         name='evaluacion_360_responder'),

    # Dashboard ejecutivo
    path('dashboard/', views.evaluaciones_dashboard, name='evaluaciones_dashboard'),

    # 9-Box Grid global
    path('ninebox/', views.ninebox_grid, name='ninebox_grid'),

    # Comparativa de Competencias
    path('comparativa/', views.comparativa_competencias, name='comparativa_competencias'),

    # Admin — Ciclos
    path('', views.ciclos_panel, name='ciclos_panel'),
    path('crear/', views.ciclo_crear, name='ciclo_crear'),
    path('<int:pk>/', views.ciclo_detalle, name='ciclo_detalle'),
    path('<int:pk>/generar/', views.ciclo_generar_evaluaciones, name='ciclo_generar_evaluaciones'),
    path('<int:pk>/abrir/', views.ciclo_abrir, name='ciclo_abrir'),
    path('<int:pk>/cerrar/', views.ciclo_cerrar, name='ciclo_cerrar'),

    # Admin — 9-Box
    path('<int:ciclo_pk>/nine-box/', views.nine_box, name='nine_box'),
    path('resultado/<int:pk>/clasificar/', views.resultado_clasificar, name='resultado_clasificar'),

    # Admin — Competencias y Plantillas
    path('competencias/', views.competencias_panel, name='competencias_panel'),
    path('competencias/crear/', views.competencia_crear, name='competencia_crear'),
    path('plantillas/', views.plantillas_panel, name='plantillas_panel'),

    # Admin — Planes de Desarrollo
    path('planes/', views.planes_panel, name='planes_panel'),
    path('planes/<int:pk>/', views.plan_detalle, name='plan_detalle'),
    path('acciones/<int:pk>/completar/', views.accion_completar, name='accion_completar'),

    # Evaluador + Portal
    path('evaluar/<int:pk>/', views.evaluacion_completar, name='evaluacion_completar'),
    path('mis-evaluaciones/', views.mis_evaluaciones, name='mis_evaluaciones'),

    # Exportar Excel
    path('<int:pk>/exportar/', views.exportar_evaluacion_excel, name='evaluacion_exportar_excel'),

    # ── OKRs ──
    path('okrs/', views_okr.okr_panel, name='okr_panel'),
    path('okrs/nuevo/', views_okr.okr_crear, name='okr_crear'),
    path('okrs/<int:pk>/', views_okr.okr_detalle, name='okr_detalle'),
    path('okrs/<int:pk>/editar/', views_okr.okr_editar, name='okr_editar'),
    path('okrs/<int:pk>/status/', views_okr.okr_cambiar_status, name='okr_cambiar_status'),
    path('okrs/<int:pk>/eliminar/', views_okr.okr_eliminar, name='okr_eliminar'),

    # KRs (AJAX)
    path('okrs/<int:objetivo_pk>/kr/nuevo/', views_okr.kr_crear, name='kr_crear'),
    path('okrs/kr/<int:pk>/actualizar/', views_okr.kr_actualizar, name='kr_actualizar'),
    path('okrs/kr/<int:pk>/eliminar/', views_okr.kr_eliminar, name='kr_eliminar'),

    # Check-ins (AJAX)
    path('okrs/kr/<int:kr_pk>/checkin/', views_okr.checkin_registrar, name='checkin_registrar'),

    # Portal
    path('mis-okrs/', views_okr.mis_okrs, name='mis_okrs'),
]
