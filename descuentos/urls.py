from django.urls import path

from . import views


urlpatterns = [
    # Admin
    path('', views.panel, name='descuentos_panel'),
    path('crear/', views.crear, name='descuentos_crear'),
    path('<int:pk>/', views.detalle, name='descuentos_detalle'),
    path('<int:pk>/aprobar/', views.aprobar, name='descuentos_aprobar'),
    path('<int:pk>/anular/', views.anular, name='descuentos_anular'),
    # Portal trabajador
    path('mis/', views.mis_descuentos, name='mis_descuentos'),
]
