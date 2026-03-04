"""
URLs del módulo Documentos - Legajo Digital.
"""
from django.urls import path
from documentos import views
from documentos import views_firma
from documentos import views_cese

urlpatterns = [
    # Panel principal (admin)
    path('', views.panel_documentos, name='documentos_panel'),

    # Legajo de un trabajador
    path('legajo/<int:personal_id>/', views.legajo_trabajador, name='documentos_legajo'),

    # CRUD documentos
    path('subir/', views.documento_subir, name='documentos_subir'),
    path('<int:pk>/eliminar/', views.documento_eliminar, name='documentos_eliminar'),

    # Tipos de documento (admin config)
    path('tipos/', views.tipos_documento, name='documentos_tipos'),
    path('tipos/crear/', views.tipo_crear, name='documentos_tipo_crear'),
    path('tipos/<int:pk>/editar/', views.tipo_editar, name='documentos_tipo_editar'),
    path('tipos/<int:pk>/eliminar/', views.tipo_eliminar, name='documentos_tipo_eliminar'),

    # Categorías CRUD
    path('categorias/crear/', views.categoria_crear, name='documentos_categoria_crear'),
    path('categorias/<int:pk>/editar/', views.categoria_editar, name='documentos_categoria_editar'),
    path('categorias/<int:pk>/eliminar/', views.categoria_eliminar, name='documentos_categoria_eliminar'),

    # Reporte de documentos faltantes
    path('faltantes/', views.documentos_faltantes, name='documentos_faltantes'),

    # Exportar inventario Excel
    path('exportar/inventario/', views.exportar_inventario_excel, name='documentos_exportar_inventario'),

    # AJAX
    path('ajax/stats/', views.ajax_stats, name='documentos_ajax_stats'),

    # Constancias / Generador de Documentos (admin)
    path('constancias/', views.constancias_panel, name='constancias_panel'),
    path('constancias/<int:plantilla_id>/generar/', views.constancia_generar, name='constancia_generar'),
    path('constancias/<int:plantilla_id>/preview/', views.constancia_preview, name='constancia_preview'),
    # Constancias / Portal del trabajador
    path('constancias/mis/', views.mis_constancias, name='mis_constancias'),
    path('constancias/<int:plantilla_id>/mi-generar/', views.portal_generar_constancia, name='portal_constancia_generar'),

    # Plantillas CRUD
    path('plantillas/', views.plantilla_list, name='plantilla_list'),
    path('plantillas/crear/', views.plantilla_editar, name='plantilla_crear'),
    path('plantillas/<int:pk>/editar/', views.plantilla_editar, name='plantilla_editar'),

    # ── Documentos Laborales (Fase 6.3) ──
    path('laborales/', views.docs_laborales_panel, name='docs_laborales_panel'),
    path('laborales/crear/', views.doc_laboral_crear, name='doc_laboral_crear'),
    path('laborales/<int:pk>/', views.doc_laboral_detalle, name='doc_laboral_detalle'),
    path('laborales/<int:pk>/publicar/', views.doc_laboral_publicar, name='doc_laboral_publicar'),
    path('laborales/<int:pk>/archivar/', views.doc_laboral_archivar, name='doc_laboral_archivar'),
    # Portal
    path('laborales/mis/', views.mis_documentos_laborales, name='mis_documentos_laborales'),
    path('laborales/<int:pk>/ver/', views.doc_laboral_ver, name='doc_laboral_ver'),
    path('laborales/<int:pk>/confirmar/', views.doc_laboral_confirmar, name='doc_laboral_confirmar'),

    # ── Boletas de Pago ──
    path('boletas/', views.boletas_panel, name='boletas_panel'),
    path('boletas/subir/', views.boleta_subir, name='boleta_subir'),
    path('boletas/<int:pk>/publicar/', views.boleta_publicar, name='boleta_publicar'),
    path('boletas/<int:pk>/anular/', views.boleta_anular, name='boleta_anular'),
    path('boletas/publicar-masivo/', views.boletas_publicar_masivo, name='boletas_publicar_masivo'),
    path('boletas/mis/', views.mis_boletas, name='mis_boletas'),
    path('boletas/<int:pk>/confirmar/', views.boleta_confirmar_lectura, name='boleta_confirmar'),

    # ── Dossier Documentario ──
    path('dossier/', views.dossier_list, name='dossier_list'),
    path('dossier/nuevo/', views.dossier_crear, name='dossier_crear'),
    path('dossier/<int:pk>/', views.dossier_detalle, name='dossier_detalle'),
    path('dossier/<int:pk>/agregar-personal/', views.dossier_agregar_personal, name='dossier_agregar_personal'),
    path('dossier/<int:pk>/generar-items/', views.dossier_generar_items, name='dossier_generar_items'),
    path('dossier/<int:pk>/vincular/', views.dossier_vincular, name='dossier_vincular'),
    path('dossier/<int:pk>/estado/', views.dossier_cambiar_estado, name='dossier_cambiar_estado'),
    path('dossier/item/<int:item_pk>/estado/', views.dossier_item_estado, name='dossier_item_estado'),
    # Plantillas Dossier
    path('dossier/plantillas/', views.plantilla_dossier_list, name='plantilla_dossier_list'),
    path('dossier/plantillas/nueva/', views.plantilla_dossier_form, name='plantilla_dossier_crear'),
    path('dossier/plantillas/<int:pk>/editar/', views.plantilla_dossier_form, name='plantilla_dossier_editar'),

    # Firma Digital (ZapSign)
    path('firma/', views_firma.firma_panel, name='firma_panel'),
    path('firma/nuevo/', views_firma.firma_crear, name='firma_crear'),
    path('firma/<int:pk>/enviar/', views_firma.firma_enviar, name='firma_enviar'),
    path('firma/<int:pk>/sincronizar/', views_firma.firma_sincronizar, name='firma_sincronizar'),
    path('firma/<int:pk>/cancelar/', views_firma.firma_cancelar, name='firma_cancelar'),
    path('firma/sincronizar-todos/', views_firma.firma_sincronizar_todos, name='firma_sincronizar_todos'),

    # ── Flujo de Cese — equivalente digital de la macro Excel ─────────────────
    path('cese/', views_cese.pdf_cese_panel,    name='pdf_cese_panel'),
    path('cese/upload/', views_cese.pdf_cese_upload,  name='pdf_cese_upload'),
    path('cese/procesar/', views_cese.pdf_cese_procesar, name='pdf_cese_procesar'),
    path('cese/confirmar/', views_cese.pdf_cese_confirmar, name='pdf_cese_confirmar'),
]
