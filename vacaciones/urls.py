"""URLs del módulo de Vacaciones y Permisos."""
from django.urls import path
from . import views

urlpatterns = [
    # Admin — Vacaciones
    path('', views.vacaciones_panel, name='vacaciones_panel'),
    path('nueva/', views.vacacion_crear, name='vacacion_crear'),
    path('<int:pk>/aprobar/', views.vacacion_aprobar, name='vacacion_aprobar'),
    path('<int:pk>/rechazar/', views.vacacion_rechazar, name='vacacion_rechazar'),

    # Admin — Permisos
    path('permisos/', views.permisos_panel, name='permisos_panel'),
    path('permisos/<int:pk>/aprobar/', views.permiso_aprobar, name='permiso_aprobar'),
    path('permisos/<int:pk>/rechazar/', views.permiso_rechazar, name='permiso_rechazar'),

    # Admin — Saldos
    path('saldos/', views.saldos_panel, name='saldos_panel'),
    path('saldos/generar/', views.saldo_generar_masivo, name='saldo_generar_masivo'),
    path('saldos/exportar/', views.saldos_exportar_excel, name='saldos_exportar_excel'),

    # Admin — Calendario (mensual existente + anual nuevo)
    path('calendario/', views.vacaciones_calendario, name='vacaciones_calendario'),
    path('calendario/anual/', views.vacaciones_calendario_anual,
         name='vacaciones_calendario_anual'),

    # Admin — Vista enfocada en gestión (alias de panel)
    path('admin/', views.vacaciones_admin_lista, name='vacaciones_admin'),

    # Admin — Config tipos
    path('tipos-permiso/', views.tipos_permiso, name='tipos_permiso'),
    path('tipos-permiso/crear/', views.tipo_permiso_crear, name='tipo_permiso_crear'),
    path('tipos-permiso/<int:pk>/editar/', views.tipo_permiso_editar, name='tipo_permiso_editar'),

    # Portal trabajador
    path('mis/', views.mis_vacaciones, name='mis_vacaciones'),
    path('mis/solicitar/', views.vacacion_solicitar, name='vacacion_solicitar'),
    path('mis/solicitar-wizard/', views.vacacion_solicitar_wizard,
         name='vacacion_solicitar_wizard'),

    # PDF Constancia de Vacaciones (post-aprobacion)
    path('<int:pk>/constancia/', views.vacacion_constancia_pdf,
         name='vacacion_constancia_pdf'),

    path('mis-permisos/', views.mis_permisos, name='mis_permisos'),
    path('mis-permisos/solicitar/', views.permiso_solicitar, name='permiso_solicitar'),
    path('anular/<str:tipo>/<int:pk>/', views.solicitud_anular, name='solicitud_anular'),

    # Admin — Detalle de Saldo
    path('saldos/<int:pk>/', views.saldo_detalle, name='saldo_detalle'),

    # Admin — Venta de Vacaciones
    path('ventas/', views.venta_vacaciones_lista, name='venta_vacaciones_lista'),
    path('ventas/crear/', views.venta_vacaciones_crear, name='venta_vacaciones_crear'),
]
