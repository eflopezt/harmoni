from django.urls import path
from . import views
from . import views_liquidacion

urlpatterns = [
    # Panel y portal
    path('', views.nominas_panel, name='nominas_panel'),
    path('mis-recibos/', views.mis_recibos, name='mis_recibos'),

    # Conceptos remunerativos
    path('conceptos/', views.conceptos_panel, name='nominas_conceptos'),
    path('conceptos/crear/', views.concepto_crear, name='nominas_concepto_crear'),
    path('conceptos/<int:pk>/eliminar/', views.concepto_eliminar, name='nominas_concepto_eliminar'),

    # Períodos
    path('periodos/nuevo/', views.periodo_crear, name='nominas_periodo_crear'),
    path('periodos/<int:pk>/', views.periodo_detalle, name='nominas_periodo_detalle'),
    path('periodos/<int:pk>/generar/', views.periodo_generar, name='nominas_periodo_generar'),
    path('periodos/<int:pk>/aprobar/', views.periodo_aprobar, name='nominas_periodo_aprobar'),
    path('periodos/<int:pk>/exportar/', views.periodo_exportar, name='nominas_periodo_exportar'),
    path('periodos/<int:pk>/resumen/', views.periodo_resumen_ajax, name='nominas_periodo_resumen'),
    path('periodos/<int:pk>/boletas.zip', views.periodo_boletas_zip, name='nominas_periodo_boletas_zip'),

    # Registros individuales
    path('registros/<int:pk>/', views.registro_detalle, name='nominas_registro_detalle'),
    path('registros/<int:pk>/editar/', views.registro_editar, name='nominas_registro_editar'),

    # Boleta PDF
    path('registros/<int:pk>/boleta.pdf', views.boleta_pdf, name='nominas_boleta_pdf'),

    # Gratificaciones y períodos especiales
    path('gratificaciones/', views.gratificacion_panel, name='nominas_gratificaciones'),
    path('periodos/especial/crear/', views.crear_periodo_especial, name='nominas_crear_especial'),

    # Liquidación al Cese
    path('liquidaciones/', views_liquidacion.liquidaciones_panel, name='nominas_liquidaciones'),
    path('liquidaciones/<int:pk>/', views_liquidacion.liquidacion_detalle, name='nominas_liquidacion_detalle'),
    path('liquidaciones/<int:pk>/generar/', views_liquidacion.liquidacion_generar, name='nominas_liquidacion_generar'),
    path('liquidaciones/<int:pk>/pdf/', views_liquidacion.liquidacion_pdf, name='nominas_liquidacion_pdf'),

    # IR 5ta Categoría
    path('ir5ta/', views.ir5ta_panel, name='nominas_ir5ta'),
    path('registros/<int:pk>/ir5ta/', views.registro_ir5ta_ajax, name='nominas_registro_ir5ta'),

    # Flujo de Caja de Planilla
    path('flujo-caja/', views.flujo_caja_panel, name='nominas_flujo_caja'),
    path('presupuesto/guardar/', views.presupuesto_guardar, name='nominas_presupuesto_guardar'),
    path('presupuesto/<int:anio>/<int:mes>/eliminar/', views.presupuesto_eliminar, name='nominas_presupuesto_eliminar'),

    # Planes de Plantilla
    path('planes/', views.planes_panel, name='nominas_planes'),
    path('planes/crear/', views.plan_crear, name='nominas_plan_crear'),
    path('planes/plantilla-excel/', views.plan_plantilla_excel, name='nominas_plan_plantilla_excel'),
    path('planes/<int:pk>/', views.plan_detalle, name='nominas_plan_detalle'),
    path('planes/<int:pk>/estado/', views.plan_actualizar_estado, name='nominas_plan_estado'),
    path('planes/<int:pk>/exportar-excel/', views.plan_export_excel, name='nominas_plan_export_excel'),
    path('planes/<int:pk>/importar-excel/', views.plan_import_excel, name='nominas_plan_import_excel'),
    path('planes/<int:plan_pk>/lineas/', views.plan_linea_upsert, name='nominas_plan_linea_upsert'),
    path('planes/<int:plan_pk>/lineas/<int:linea_pk>/eliminar/', views.plan_linea_eliminar, name='nominas_plan_linea_eliminar'),
]
