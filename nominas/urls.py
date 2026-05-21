from django.urls import path
from . import views
from . import views_liquidacion
from . import views_legacy_import

urlpatterns = [
    # Panel y portal
    path('', views.nominas_panel, name='nominas_panel'),
    path('mis-recibos/', views.mis_recibos, name='mis_recibos'),

    # Migración legacy (Spring u otro sistema)
    path('importar-legacy/', views_legacy_import.importar_legacy, name='nominas_importar_legacy'),

    # Constancia de Entrega y Recepción (DS 009-2011-TR) — trail completo del trabajador
    path('registros/<int:pk>/constancia.pdf',
         views.constancia_recepcion_pdf,
         name='nominas_constancia_recepcion'),

    # Conceptos remunerativos
    path('conceptos/', views.conceptos_panel, name='nominas_conceptos'),
    path('conceptos/crear/', views.concepto_crear, name='nominas_concepto_crear'),
    path('conceptos/<int:pk>/eliminar/', views.concepto_eliminar, name='nominas_concepto_eliminar'),

    # Períodos
    path('periodos/nuevo/', views.periodo_crear, name='nominas_periodo_crear'),
    path('periodos/<int:pk>/', views.periodo_detalle, name='nominas_periodo_detalle'),
    path('periodos/<int:pk>/generar/', views.periodo_generar, name='nominas_periodo_generar'),
    path('periodos/<int:pk>/aprobar/', views.periodo_aprobar, name='nominas_periodo_aprobar'),
    path('periodos/<int:pk>/cerrar/', views.periodo_cerrar, name='nominas_periodo_cerrar'),
    path('periodos/<int:pk>/exportar/', views.periodo_exportar, name='nominas_periodo_exportar'),
    path('periodos/<int:pk>/resumen/', views.periodo_resumen_ajax, name='nominas_periodo_resumen'),
    path('periodos/<int:pk>/boletas.zip', views.periodo_boletas_zip, name='nominas_periodo_boletas_zip'),
    path('periodos/<int:pk>/plame/', views.periodo_exportar_plame, name='nominas_periodo_plame'),
    path('periodos/<int:pk>/tregistro/', views.periodo_exportar_tregistro, name='nominas_periodo_tregistro'),

    # Registros individuales
    path('registros/<int:pk>/', views.registro_detalle, name='nominas_registro_detalle'),
    path('registros/<int:pk>/editar/', views.registro_editar, name='nominas_registro_editar'),

    # Boleta PDF
    path('registros/<int:pk>/boleta.pdf', views.boleta_pdf, name='nominas_boleta_pdf'),

    # Acuse de recibo (firma electrónica DS 009-2011-TR Art. 18-A)
    path('registros/<int:pk>/confirmar-recibo/', views.confirmar_recibo_boleta,
         name='nominas_confirmar_recibo'),

    # Consentimiento previo para boleta electrónica (DS 009-2011-TR)
    path('consentimiento-boleta/', views.aceptar_consentimiento_boleta,
         name='aceptar_consentimiento_boleta'),

    # Panel de Emisión y Entrega de Boletas (con tracking SmartBoletas)
    path('boletas/', views.emision_boletas_panel, name='nominas_emision_boletas'),
    path('boletas/<int:pk>/notificar/', views.notificar_periodo_boletas,
         name='nominas_notificar_periodo_boletas'),

    # Configuración tasas AFP (admin)
    path('config/tasas-afp/', views.config_tasas_afp, name='config_tasas_afp'),

    # Verificación pública de boleta (QR) — sin login
    path('verificar/<str:token>/', views.verificar_boleta, name='verificar_boleta'),

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

    # API: Explicador IA de boleta
    path('registros/<int:pk>/explicar/', views.explicar_boleta_ia, name='nominas_explicar_boleta'),

    # Recargas de Alimentación (Edenred/Sodexo)
    path('alimentacion/', views.alimentacion_panel, name='alimentacion_panel'),
    path('alimentacion/generar/', views.alimentacion_generar, name='alimentacion_generar'),
    path('alimentacion/exportar/', views.alimentacion_exportar, name='alimentacion_exportar'),
    path('alimentacion/procesar/', views.alimentacion_procesar, name='alimentacion_procesar'),
]
