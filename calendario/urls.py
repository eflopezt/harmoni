"""URLs del modulo Calendario Laboral."""
from django.urls import path

from . import views

urlpatterns = [
    path('', views.calendario_view, name='calendario_view'),
    path('eventos/', views.calendario_eventos, name='calendario_eventos'),
    path('eventos/crear/', views.evento_crear, name='evento_crear'),
    path('eventos/<int:pk>/eliminar/', views.evento_eliminar, name='evento_eliminar'),
    path('export/ical/', views.calendario_export_ical, name='calendario_export_ical'),
    path('stats/', views.calendario_stats, name='calendario_stats'),
    path('disponibilidad/', views.calendario_disponibilidad,
         name='calendario_disponibilidad'),
]
