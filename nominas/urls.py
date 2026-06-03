from django.urls import path
from . import views
from . import views_liquidacion
from . import views_legacy_import
from . import views_conceptos
from . import views_wizard_planilla
from . import views_onboarding_validator
from . import views_mi_dia
from . import views_calculadora
from . import views_workflow_mes
from . import views_anomalias
from . import views_reporte_mes
from . import views_calc_especializadas
from . import views_interanual
from . import views_agente_ia
from . import views_propinas
from . import views_conceptos_masivos
from . import views_archivo_banco

urlpatterns = [
    # Panel y portal
    path('', views.nominas_panel, name='nominas_panel'),
    path('mis-recibos/', views.mis_recibos, name='mis_recibos'),
    # Calculadora simple para trabajador — sin secciones de costos empresa
    path('mi-calculadora/', views_calculadora.calculadora_planilla, name='mi_calculadora_trabajador'),

    # Migración legacy (Spring u otro sistema)
    path('importar-legacy/', views_legacy_import.importar_legacy, name='nominas_importar_legacy'),

    # Constancia de Entrega y Recepción (DS 009-2011-TR) — trail completo del trabajador
    path('registros/<int:pk>/constancia.pdf',
         views.constancia_recepcion_pdf,
         name='nominas_constancia_recepcion'),

    # ── NUEVO: Configuración de Conceptos (CRUD + flags + PLAME) ──
    path('conceptos/configurar/',              views_conceptos.conceptos_lista,           name='conceptos_lista'),
    path('conceptos/configurar/nuevo/',        views_conceptos.concepto_nuevo,            name='concepto_nuevo'),
    path('conceptos/configurar/<int:pk>/editar/', views_conceptos.concepto_editar,        name='concepto_editar'),
    path('conceptos/configurar/<int:pk>/autofix/', views_conceptos.concepto_autofix,      name='concepto_autofix'),
    path('conceptos/configurar/templates/',    views_conceptos.conceptos_templates,       name='conceptos_templates'),
    path('conceptos/configurar/templates/<str:key>/aplicar/',
                                               views_conceptos.concepto_aplicar_template, name='concepto_aplicar_template'),
    path('conceptos/configurar/export/csv/',   views_conceptos.conceptos_export_csv,      name='conceptos_export_csv'),
    path('conceptos/configurar/bulk/',         views_conceptos.conceptos_bulk_action,     name='conceptos_bulk_action'),
    path('conceptos/configurar/wizard/',       views_wizard_planilla.wizard_step1,         name='wizard_step1'),
    path('conceptos/configurar/wizard/seleccionar/', views_wizard_planilla.wizard_step2,   name='wizard_step2'),

    # Audit log de conceptos (compliance + diagnóstico)
    path('conceptos/configurar/audit-log/',            views_conceptos.conceptos_audit_log,
                                                       name='conceptos_audit_log'),
    path('conceptos/configurar/audit-log/csv/',        views_conceptos.conceptos_audit_log_csv,
                                                       name='conceptos_audit_log_csv'),
    path('conceptos/configurar/comparar/',             views_conceptos.conceptos_comparador,
                                                       name='conceptos_comparador'),
    path('conceptos/configurar/<int:pk>/historial/',   views_conceptos.concepto_historial,
                                                       name='concepto_historial'),

    # Validador de Onboarding y Mi Día Nóminas (admin)
    path('onboarding/validador/',     views_onboarding_validator.onboarding_validador,
                                      name='onboarding_validador'),
    path('onboarding/validador.pdf',  views_onboarding_validator.onboarding_validador_pdf,
                                      name='onboarding_validador_pdf'),
    path('mi-dia/',                   views_mi_dia.mi_dia_nominas,
                                      name='mi_dia_nominas'),
    path('workflow-mes/',             views_workflow_mes.workflow_mes,
                                      name='workflow_mes'),
    path('anomalias/<int:pk>/',       views_anomalias.anomalias_periodo,
                                      name='nominas_anomalias_periodo'),
    path('periodos/<int:pk>/reporte-ejecutivo.pdf', views_reporte_mes.reporte_ejecutivo_pdf,
                                      name='nominas_reporte_ejecutivo_pdf'),
    path('calculadora/',              views_calculadora.calculadora_planilla,
                                      name='calculadora_planilla'),
    path('calculadora/comparar/',     views_calculadora.calculadora_comparar,
                                      name='calculadora_comparar'),
    path('calculadora/afp/',          views_calculadora.calculadora_afp_comparar,
                                      name='calculadora_afp'),
    path('calculadora/reversa/',      views_calc_especializadas.calc_reversa,
                                      name='calc_reversa'),
    path('calculadora/gratificacion/', views_calc_especializadas.calc_gratificacion,
                                      name='calc_gratificacion'),
    path('calculadora/cts/',          views_calc_especializadas.calc_cts,
                                      name='calc_cts'),
    path('calculadora/liquidacion/',  views_calc_especializadas.calc_liquidacion,
                                      name='calc_liquidacion'),
    path('calculadora/pdf/',          views_calculadora.calculadora_pdf,
                                      name='calculadora_pdf'),

    # Conceptos remunerativos (panel legacy/existing — read-only resumen)
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

    # Conceptos manuales masivos (Excel) — propinas, bonificaciones, comisiones por trabajador
    path('periodos/<int:pk>/conceptos/exportar/',
         views_conceptos_masivos.periodo_conceptos_exportar,
         name='nominas_periodo_conceptos_exportar'),
    path('periodos/<int:pk>/conceptos/importar/',
         views_conceptos_masivos.periodo_conceptos_importar,
         name='nominas_periodo_conceptos_importar'),

    # Archivo plano bancario para depósito masivo de haberes
    path('periodos/<int:pk>/archivo-banco/',
         views_archivo_banco.periodo_archivo_banco,
         name='nominas_periodo_archivo_banco'),
    path('periodos/<int:pk>/resumen/', views.periodo_resumen_ajax, name='nominas_periodo_resumen'),
    path('periodos/<int:pk>/boletas.zip', views.periodo_boletas_zip, name='nominas_periodo_boletas_zip'),
    path('periodos/<int:pk>/plame/', views.periodo_exportar_plame, name='nominas_periodo_plame'),
    path('periodos/<int:pk>/tregistro/', views.periodo_exportar_tregistro, name='nominas_periodo_tregistro'),
    path('tregistro/alta/<int:personal_id>/', views.tregistro_alta_personal, name='nominas_tregistro_alta_personal'),
    path('tregistro/baja/<int:personal_id>/', views.tregistro_baja_personal, name='nominas_tregistro_baja_personal'),

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

    # Reporte ejecutivo PDF del período (admin)
    path('periodos/<int:pk>/reporte.pdf', views.reporte_periodo_pdf,
         name='nominas_reporte_periodo_pdf'),

    # Comparativo Mensual — evolución últimos N meses (gerencia)
    path('comparativo/', views.comparativo_mensual,
         name='nominas_comparativo_mensual'),
    path('interanual/', views_interanual.comparativo_interanual,
         name='nominas_comparativo_interanual'),

    # ── Agente IA Nóminas (chat + reintegros) ──
    path('agente/',                       views_agente_ia.agente_lista,        name='agente_lista'),
    path('agente/nueva/',                 views_agente_ia.agente_nueva,        name='agente_nueva'),
    path('agente/<int:pk>/',              views_agente_ia.agente_chat,         name='agente_chat'),
    path('agente/<int:pk>/mensaje/',      views_agente_ia.agente_mensaje,      name='agente_mensaje'),
    path('reintegros/',                   views_agente_ia.reintegros_lista,    name='reintegros_lista'),
    path('reintegros/<int:pk>/',          views_agente_ia.reintegro_detalle,   name='reintegro_detalle'),
    path('reintegros/<int:pk>/aprobar/',  views_agente_ia.reintegro_aprobar,   name='reintegro_aprobar'),
    path('reintegros/<int:pk>/aplicar/',  views_agente_ia.reintegro_aplicar,   name='reintegro_aplicar'),
    path('reintegros/<int:pk>/revertir/', views_agente_ia.reintegro_revertir,  name='reintegro_revertir'),

    # Saldos de Apertura — Onboarding Express (Wizard)
    path('apertura/', views.saldos_apertura,
         name='nominas_saldos_apertura'),
    path('apertura/plantilla.xlsx', views.saldos_apertura_plantilla,
         name='nominas_saldos_apertura_plantilla'),

    # Configuración tasas AFP (admin)
    path('config/tasas-afp/', views.config_tasas_afp, name='config_tasas_afp'),

    # Verificación pública de boleta (QR) — sin login
    path('verificar/<str:token>/', views.verificar_boleta, name='verificar_boleta'),

    # Gratificaciones y períodos especiales
    path('gratificaciones/', views.gratificacion_panel, name='nominas_gratificaciones'),
    path('periodos/especial/crear/', views.crear_periodo_especial, name='nominas_crear_especial'),

    # Liquidación al Cese (vistas legacy sobre RegistroNomina)
    path('liquidaciones/', views_liquidacion.liquidaciones_panel, name='nominas_liquidaciones'),
    path('liquidaciones/<int:pk>/', views_liquidacion.liquidacion_detalle, name='nominas_liquidacion_detalle'),
    path('liquidaciones/<int:pk>/generar/', views_liquidacion.liquidacion_generar, name='nominas_liquidacion_generar'),
    path('liquidaciones/<int:pk>/pdf/', views_liquidacion.liquidacion_pdf, name='nominas_liquidacion_pdf'),

    # Sprint 1 — LiquidacionLaboral (modelo header con motivo, totales, workflow)
    path('liquidacion/<int:liquidacion_id>/',
         views_liquidacion.liquidacion_laboral_detalle,
         name='nominas_liquidacion_laboral_detalle'),
    path('liquidacion/<int:liquidacion_id>/aprobar/',
         views_liquidacion.liquidacion_laboral_aprobar,
         name='nominas_liquidacion_laboral_aprobar'),
    path('liquidacion/<int:liquidacion_id>/pdf/',
         views_liquidacion.liquidacion_laboral_pdf,
         name='nominas_liquidacion_laboral_pdf'),

    # Sprint 1 — API liquidacion (JSON) accesible bajo /nominas/api/liquidacion/<personal_id>/
    path('api/liquidacion/<int:personal_id>/',
         views_liquidacion.api_liquidacion,
         name='nominas_api_liquidacion'),

    # Sprint 3 — Documentos al cese: carta de no adeudo (certificado de trabajo
    # se monta en personal/urls.py para que quede en /personal/<id>/certificado-trabajo/).
    path('liquidacion/<int:liquidacion_id>/carta-no-adeudo/',
         views_liquidacion.carta_no_adeudo_pdf,
         name='nominas_carta_no_adeudo_pdf'),

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

    # Pool de Propinas (gastronomía)
    path('propinas/',                       views_propinas.propinas_lista,      name='propinas_lista'),
    path('propinas/config/',                views_propinas.propinas_config,     name='propinas_config'),
    path('propinas/nuevo/',                 views_propinas.propinas_nuevo,      name='propinas_nuevo'),
    path('propinas/<int:pool_id>/',         views_propinas.propinas_detalle,    name='propinas_detalle'),
    path('propinas/<int:pool_id>/distribuir/',
         views_propinas.propinas_distribuir,
         name='propinas_distribuir'),
    path('propinas/<int:pool_id>/horas/',
         views_propinas.propinas_horas,
         name='propinas_horas'),
    path('propinas/<int:pool_id>/acta.pdf',
         views_propinas.propinas_acta_pdf,
         name='propinas_acta_pdf'),
]
