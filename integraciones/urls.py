"""URLs del módulo Integraciones Perú."""
from django.urls import path
from integraciones import views

urlpatterns = [
    path('', views.panel, name='integraciones_panel'),

    # T-Registro SUNAT
    path('t-registro/altas/', views.exportar_t_registro_altas, name='integ_treg_altas'),
    path('t-registro/bajas/', views.exportar_t_registro_bajas, name='integ_treg_bajas'),

    # Planilla
    path('planilla/', views.exportar_planilla_excel, name='integ_planilla'),

    # AFP Net
    path('afp-net/', views.exportar_afp_net, name='integ_afp_net'),
    path('afp-net/panel/', views.afp_net_panel, name='integ_afp_net_panel'),

    # Bancos
    path('bancos/', views.exportar_pago_banco, name='integ_banco'),

    # ESSALUD
    path('essalud/', views.exportar_essalud, name='integ_essalud'),

    # Preview AJAX
    path('preview/', views.preview_exportacion, name='integ_preview'),

    # PLAME
    path('plame/', views.exportar_plame, name='integ_plame'),
    path('plame/preview/', views.plame_preview, name='integ_plame_preview'),

    # Bancos especificos
    path('bancos/<str:banco>/', views.exportar_banco_especifico, name='integ_banco_especifico'),

    # Contabilidad (CONCAR, SIGO, SAP, SIRE)
    path('contable/', views.panel_contable, name='integ_contable_panel'),
    path('contable/<str:formato>/', views.exportar_contable, name='integ_contable_exportar'),

    # Biometrico
    path('biometrico/', views.biometrico_import, name='integ_biometrico'),

    # Configuracion del sistema
    path('configuracion/', views.configuracion_sistema, name='configuracion_sistema'),

    # SCTR — Seguro Complementario de Trabajo de Riesgo
    path('sctr/', views.sctr_panel, name='sctr_panel'),
    path('sctr/crear/', views.sctr_crear, name='sctr_crear'),
    path('sctr/<int:pk>/editar/', views.sctr_editar, name='sctr_editar'),
    path('sctr/<int:pk>/estado/', views.sctr_estado, name='sctr_estado'),
]
