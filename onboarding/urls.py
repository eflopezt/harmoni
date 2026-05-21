"""URLs del módulo de Onboarding y Offboarding."""
from django.urls import path
from . import views

urlpatterns = [
    # ── Dashboard ──
    path('dashboard/', views.onboarding_dashboard, name='onboarding_dashboard'),

    # ── Onboarding — Procesos ──
    path('', views.onboarding_panel, name='onboarding_panel'),
    path('crear/', views.onboarding_crear, name='onboarding_crear'),
    path('<int:pk>/', views.onboarding_detalle, name='onboarding_detalle'),
    path('<int:pk>/progreso/', views.proceso_progreso, name='proceso_progreso'),
    path('paso/<int:pk>/completar/', views.paso_completar, name='paso_on_completar'),
    path('paso/<int:pk>/omitir/', views.paso_omitir, name='paso_on_omitir'),
    path('<int:proc_pk>/paso/<int:paso_pk>/completar/', views.onboarding_completar_paso, name='onboarding_completar_paso'),

    # ── Offboarding — Procesos ──
    path('offboarding/', views.offboarding_panel, name='offboarding_panel'),
    path('offboarding/crear/', views.offboarding_crear, name='offboarding_crear'),
    path('offboarding/<int:pk>/', views.offboarding_detalle, name='offboarding_detalle'),
    path('offboarding/paso/<int:pk>/completar/', views.paso_off_completar, name='paso_off_completar'),
    path('offboarding/paso/<int:pk>/omitir/', views.paso_off_omitir, name='paso_off_omitir'),

    # ── Plantillas ──
    path('plantillas/', views.plantillas_onboarding, name='plantillas_onboarding'),
    path('plantillas/crear/', views.plantilla_crear, name='plantilla_onboarding_crear'),
    path('plantillas/<str:tipo>/<int:pk>/', views.plantilla_detalle, name='plantilla_detalle'),
    path('plantillas/<str:tipo>/<int:pk>/agregar-paso/', views.paso_plantilla_agregar, name='paso_plantilla_agregar'),
    path('plantillas/<str:tipo>/paso/<int:pk>/eliminar/', views.paso_plantilla_eliminar, name='paso_plantilla_eliminar'),
    path('plantilla-ajax/<int:pk>/', views.plantilla_ajax, name='onboarding_plantilla_ajax'),

    # ── Portal ──
    path('mi/', views.mi_onboarding, name='mi_onboarding'),

    # ── Checklist Gastronomía 30/60/90 ──
    path('gastro/', views.checklist_gastro_panel, name='checklist_gastro_panel'),
    path('gastro/auto-crear/', views.checklist_gastro_auto_crear, name='checklist_gastro_auto_crear'),
    path('gastro/<int:pk>/', views.checklist_gastro_detalle, name='checklist_gastro_detalle'),
    path('gastro/<int:pk>/toggle/', views.checklist_gastro_toggle, name='checklist_gastro_toggle'),
]
