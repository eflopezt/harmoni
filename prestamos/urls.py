"""URLs del módulo de Préstamos."""
from django.urls import path
from . import views

urlpatterns = [
    path('', views.prestamos_panel, name='prestamos_panel'),
    path('nuevo/', views.prestamo_crear, name='prestamo_crear'),
    path('<int:pk>/', views.prestamo_detalle, name='prestamo_detalle'),
    path('<int:pk>/aprobar/', views.prestamo_aprobar, name='prestamo_aprobar'),
    path('<int:pk>/desembolsar/', views.prestamo_desembolsar, name='prestamo_desembolsar'),
    path('<int:pk>/rechazar/', views.prestamo_rechazar, name='prestamo_rechazar'),
    path('<int:pk>/cancelar/', views.prestamo_cancelar, name='prestamo_cancelar'),
    path('<int:pk>/cronograma/', views.prestamo_cronograma, name='prestamo_cronograma'),
    path('<int:pk>/contrato-pdf/', views.prestamo_contrato_pdf, name='prestamo_contrato_pdf'),
    path('cuota/<int:pk>/pagar/', views.cuota_pagar, name='cuota_pagar'),
    path('mis/', views.mis_prestamos, name='mis_prestamos'),
    path('mis/solicitar/', views.mis_prestamos_solicitar, name='mis_prestamos_solicitar'),
]
