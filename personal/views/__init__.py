"""
Vistas para el módulo personal.

Este paquete re-exporta todas las vistas para mantener compatibilidad
con las URLs existentes (personal.views.funcion).
"""

from .home import home, logout_view

from .areas import (
    area_list, area_create, area_detail, area_update, area_toggle, area_delete,
    subarea_list, subarea_create, subarea_detail, subarea_update, subarea_toggle, subarea_delete,
    area_export, area_import,
    subarea_export, subarea_import,
)

from .empleados import (
    personal_list, personal_create, personal_update, personal_detail,
    personal_export, personal_import,
)

from .roster import (
    roster_list, roster_matricial, roster_create, roster_update,
    roster_export, roster_import, roster_update_cell,
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
)

from .timeline import timeline_empleado

from .contratos import (
    contratos_panel, contratos_lista, contrato_editar, contratos_api_stats,
)

from .reportes import (
    reportes_panel, reporte_plantilla,
    reporte_asistencia_mensual, reporte_he_detallado,
    reporte_vacaciones, reporte_contratos,
)
