"""
Vistas para el módulo personal.

Este paquete re-exporta todas las vistas para mantener compatibilidad
con las URLs existentes (personal.views.funcion).
"""

from .home import home, logout_view, cmd_search, alertas_dia, hr_ask, RateLimitedLoginView

from .areas import (
    area_list, area_create, area_detail, area_update, area_toggle, area_delete,
    subarea_list, subarea_create, subarea_detail, subarea_update, subarea_toggle, subarea_delete,
    area_export, area_import,
    subarea_export, subarea_import,
)

from .empleados import (
    personal_list, personal_create, personal_update, personal_detail,
    personal_export, personal_import,
    personal_create_express, personal_express_exito,
    personal_drawer_data, personal_inline_edit, personal_cesar_batch,
)

from .control_tower import control_tower

from .roster import (
    roster_list, roster_matricial, roster_create, roster_update,
    roster_export, roster_import, roster_update_cell,
)

from .roster_gastro import (
    roster_gastro_grid, roster_gastro_asignar, roster_gastro_asignar_bulk,
    roster_gastro_pdf, roster_gastro_validar,
)

from .aprobaciones import (
    dashboard_aprobaciones, cambios_pendientes,
    aprobar_cambio, rechazar_cambio,
    enviar_cambios_aprobacion,
    aprobar_lote, rechazar_lote,
)

from .usuarios import (
    usuario_list, usuario_vincular, usuario_crear_y_vincular,
    usuario_desvincular, usuario_sincronizar,
    accesos_gestion, accesos_asignar_perfil,
    accesos_detalle_usuario, accesos_toggle_modulo,
    portal_crear_acceso, portal_reset_credenciales,
    # Gestión completa de usuarios (interfaz ERP)
    gestion_usuario_lista, gestion_usuario_crear, gestion_usuario_editar,
    gestion_usuario_detalle, gestion_usuario_bulk,
    gestion_usuario_permiso_ajax, gestion_usuario_prefill_perfil,
    gestion_usuario_toggle_activo, gestion_usuario_reset_password,
    gestion_usuario_impersonar, gestion_usuario_dejar_impersonar,
)

from .timeline import timeline_empleado

from .contratos import (
    contratos_panel, contratos_lista, contrato_editar, contratos_api_stats,
    contrato_detalle, contrato_crear, contrato_editar_obj,
    contrato_renovar, contrato_renovar_personal, contratos_renovar_masivo, adenda_crear,
    contratos_exportar_excel, contratos_alertas_json,
    contrato_generar_pdf, adenda_generar_pdf, prorroga_generar_pdf,
    contrato_importar_plantilla,
    contrato_analizar_ia, contrato_enviar_email, contratos_envio_masivo,
    plantilla_contrato_lista, plantilla_contrato_crear,
    plantilla_contrato_editar, plantilla_contrato_eliminar,
    plantilla_contrato_importar, plantilla_contrato_detalle,
    plantilla_contrato_ia, plantilla_contrato_aplicar_ia,
)

from .reportes import (
    reportes_panel, reporte_plantilla,
    reporte_asistencia_mensual, reporte_he_detallado,
    reporte_vacaciones, reporte_contratos,
)

from .cese import personal_dar_baja, personal_reactivar

from .cesar import (
    cesar_wizard_paso1, cesar_wizard_preview, cesar_wizard_confirmar,
)

from .import_views import (
    import_upload, import_confirm, import_template_download, import_validate_ajax,
)

from .organigrama import (
    organigrama_view, organigrama_data, organigrama_update_parent,
    organigrama_gestion, organigrama_analizar,
    organigrama_auto_asignar, organigrama_asignar_jefe_area,
    organigrama_bulk_reporta,
)

from .activos import activos_panel, activo_asignar, activo_devolver
