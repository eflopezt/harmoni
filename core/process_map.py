"""
Mapa único de procesos conectados de Harmoni.

Mantiene en un solo lugar el recorrido RRHH: ingreso, operación,
nómina, talento, comunicación y dirección.
"""
from __future__ import annotations

import unicodedata
from copy import deepcopy
from typing import Any

from django.urls import NoReverseMatch, reverse

PROCESS_STAGES: tuple[dict[str, Any], ...] = (
    {
        "id": "ingreso",
        "number": "01",
        "label": "Ingreso y salida",
        "icon": "fa-user-plus",
        "primary_route": "control_tower",
        "description": "Candidato, alta, contrato, legajo, onboarding y cese parten del mismo colaborador.",
        "automation": "Alta express evita recargar datos: crea ficha base, acceso, contrato y tareas de bienvenida.",
        "duplicate_guard": "No dupliques fichas: el colaborador creado aquí alimenta contratos, legajo, portal y nómina.",
        "handoff": (
            ("Recibe", "Candidato validado", "Postulación, DNI, puesto y sede llegan al alta.", "fa-inbox", "pipeline_panel"),
            ("Automatiza", "Ficha, contrato y legajo", "Alta express crea datos base, documentos y accesos.", "fa-gears", "personal_create_express"),
            ("Deja listo", "Colaborador reutilizable", "La misma ficha alimenta asistencia, portal y nómina.", "fa-share-nodes", "asistencia_dashboard"),
        ),
        "match_prefixes": (
            "/personal/",
            "/empleados/",
            "/reclutamiento/",
            "/onboarding/",
            "/contratos/",
            "/documentos/",
        ),
        "actions": (
            ("Pipeline", "pipeline_panel", "fa-stream"),
            ("Alta express", "personal_create_express", "fa-bolt"),
            ("Contratos", "contratos_panel", "fa-file-contract"),
            ("Legajo", "documentos_panel", "fa-folder-open"),
        ),
        "peru_focus": (
            ("SUNAT altas", "integraciones_panel", "fa-id-card", "T-Registro desde integraciones."),
            ("Firma digital", "firma_panel", "fa-signature", "Contrato y anexos con trazabilidad."),
            ("SUNAFIL", "documentos_inspeccion_sunafil", "fa-scale-balanced", "Carpeta inspectiva sin búsqueda manual."),
        ),
    },
    {
        "id": "operacion",
        "number": "02",
        "label": "Operación diaria",
        "icon": "fa-fingerprint",
        "primary_route": "asistencia_dashboard",
        "description": "Marcas, roster, permisos, vacaciones y aprobaciones resuelven el día antes de llegar a planilla.",
        "automation": "Las marcas consolidadas salen directo a pre-planilla y reducen ajustes manuales del cierre.",
        "duplicate_guard": "No recargues horas en nómina: primero corrige asistencia, permisos y saldos en este flujo.",
        "handoff": (
            ("Recibe", "Colaborador activo", "Ficha, sede, horario y responsable vienen de ingreso.", "fa-id-badge", "control_tower"),
            ("Automatiza", "Marcas y ausencias", "Biométrico, permisos y vacaciones quedan conciliados.", "fa-gears", "asistencia_importar"),
            ("Deja listo", "Pre-planilla limpia", "Horas extra, faltas y descansos pasan a nómina.", "fa-share-nodes", "pre_planilla"),
        ),
        "match_prefixes": (
            "/asistencia/",
            "/roster/",
            "/calendario/",
            "/vacaciones/",
            "/aprobaciones/",
        ),
        "actions": (
            ("Importar marcas", "asistencia_importar", "fa-file-import"),
            ("Vista unificada", "asistencia_vista", "fa-table"),
            ("Vacaciones", "vacaciones_panel", "fa-calendar-check"),
            ("Exportar planilla", "asistencia_exportar_panel", "fa-file-export"),
        ),
        "peru_focus": (
            ("Biométrico", "integ_biometrico", "fa-fingerprint", "Marcas reales antes del cierre."),
            ("Banco de horas", "asistencia_banco_horas", "fa-clock", "Horas extra y compensaciones ordenadas."),
            ("Calendario legal", "vacaciones_calendario", "fa-calendar-days", "Vacaciones, permisos y descansos visibles."),
        ),
    },
    {
        "id": "nomina",
        "number": "03",
        "label": "Cierre de nómina",
        "icon": "fa-file-invoice-dollar",
        "primary_route": "workflow_mes",
        "description": "Pre-planilla, conceptos, período, boletas e integraciones cierran el mes con trazabilidad.",
        "automation": "Workflow mes junta asistencia, conceptos y boletas para evitar cierres paralelos en Excel.",
        "duplicate_guard": "No calcules dos veces: usa pre-planilla y luego exporta SUNAT, banco y contabilidad desde integraciones.",
        "handoff": (
            ("Recibe", "Asistencia conciliada", "Marcas, ausencias y conceptos variables llegan desde operación.", "fa-clipboard-check", "pre_planilla"),
            ("Automatiza", "Cálculo y validaciones Perú", "Planilla, gratificación, CTS, AFP y boletas se calculan una vez.", "fa-gears", "workflow_mes"),
            ("Deja listo", "Pago, PLAME y boleta", "Banco, SUNAT y comunicación salen desde el cierre aprobado.", "fa-share-nodes", "integraciones_panel"),
        ),
        "match_prefixes": (
            "/nominas/",
            "/integraciones/",
            "/cierre/",
            "/documentos/boletas/",
        ),
        "actions": (
            ("Workflow mes", "workflow_mes", "fa-route"),
            ("Pre planilla", "pre_planilla", "fa-clipboard-check"),
            ("Boletas", "nominas_emision_boletas", "fa-receipt"),
            ("Integraciones", "integraciones_panel", "fa-plug"),
        ),
        "peru_focus": (
            ("PLAME preview", "integ_plame_preview", "fa-file-lines", "Validación antes de declarar."),
            ("AFP Net", "integ_afp_net_panel", "fa-building-columns", "Aportes listos para exportar."),
            ("CTS bancos", "cts_bancos_panel", "fa-piggy-bank", "Depósitos preparados desde nómina."),
            ("SCTR", "sctr_panel", "fa-helmet-safety", "Cobertura de riesgo vinculada al personal."),
        ),
    },
    {
        "id": "talento",
        "number": "04",
        "label": "Talento y clima",
        "icon": "fa-chart-line",
        "primary_route": "evaluaciones_dashboard",
        "description": "Evaluaciones, OKR, planes, capacitaciones y encuestas convierten señales en acciones.",
        "automation": "Cada resultado debe terminar en plan, capacitación o acción visible para el colaborador.",
        "duplicate_guard": "No abras reportes aislados: conecta encuesta, evaluación, plan y capacitación en el mismo ciclo.",
        "handoff": (
            ("Recibe", "Señales del ciclo laboral", "Asistencia, desempeño, clima y rotación se leen juntos.", "fa-chart-simple", "analytics_dashboard"),
            ("Automatiza", "Brecha a plan", "Evaluación y encuesta generan PDI o capacitación.", "fa-gears", "evaluaciones_dashboard"),
            ("Deja listo", "Acciones comunicables", "Planes, cursos y feedback quedan listos para seguimiento.", "fa-share-nodes", "planes_panel"),
        ),
        "match_prefixes": (
            "/evaluaciones/",
            "/capacitaciones/",
            "/encuestas/",
        ),
        "actions": (
            ("Evaluaciones", "evaluaciones_dashboard", "fa-star-half-alt"),
            ("OKR", "okr_panel", "fa-bullseye"),
            ("Capacitaciones", "capacitaciones_panel", "fa-graduation-cap"),
            ("Encuestas", "encuestas_panel", "fa-poll"),
        ),
        "peru_focus": (
            ("360", "evaluacion_360_panel", "fa-users-viewfinder", "Feedback y brechas en el mismo ciclo."),
            ("PDI", "planes_panel", "fa-road", "Planes de accion despues de evaluar."),
            ("Capacitación", "capacitaciones_panel", "fa-graduation-cap", "Cursos ligados a competencias."),
        ),
    },
    {
        "id": "comunicacion",
        "number": "05",
        "label": "Comunicación",
        "icon": "fa-bullhorn",
        "primary_route": "com_notificaciones_panel",
        "description": "Notificaciones, comunicados, campañas y documentos laborales cierran el circuito con acuse.",
        "automation": "Una acción pendiente puede convertirse en comunicado, recordatorio o campaña segmentada.",
        "duplicate_guard": "No persigas por fuera: comunica desde aquí y conserva lectura, acuse y destinatarios.",
        "handoff": (
            ("Recibe", "Pendientes y audiencias", "Nómina, talento o RRHH definen a quién avisar.", "fa-users-line", "dashboard_aprobaciones"),
            ("Automatiza", "Mensaje con evidencia", "Comunicado, recordatorio y acuse se guardan juntos.", "fa-gears", "com_notificaciones_panel"),
            ("Deja listo", "Constancia trazable", "Lectura y destinatarios vuelven a legajo y dirección.", "fa-share-nodes", "analytics_dashboard"),
        ),
        "match_prefixes": (
            "/comunicaciones/",
            "/documentos/laborales/",
            "/documentos/archivos-hr/",
        ),
        "actions": (
            ("Notificaciones", "com_notificaciones_panel", "fa-bell"),
            ("Comunicados", "com_comunicados_panel", "fa-bullhorn"),
            ("Campañas", "campanas_panel", "fa-paper-plane"),
            ("WhatsApp", "com_whatsapp_config", "fa-comments"),
        ),
        "peru_focus": (
            ("Docs laborales", "docs_laborales_panel", "fa-file-shield", "Politicas con lectura confirmada."),
            ("Comunicados", "com_comunicados_panel", "fa-bullhorn", "Avisos formales con destinatarios."),
            ("Campañas", "campanas_panel", "fa-paper-plane", "Recordatorios segmentados por área."),
        ),
    },
    {
        "id": "direccion",
        "number": "06",
        "label": "Dirección",
        "icon": "fa-gauge-high",
        "primary_route": "analytics_dashboard",
        "description": "Analytics, alertas, rotación y reportes leen el ciclo completo sin pedir nuevos archivos.",
        "automation": "Las alertas nacen de datos vivos y empujan acciones hacia RRHH, talento o comunicacion.",
        "duplicate_guard": "No armes otro tablero manual: usa analytics para auditar el flujo y vuelve al modulo origen.",
        "handoff": (
            ("Recibe", "Datos vivos de todos los módulos", "Ingreso, asistencia, nómina, talento y comunicación se leen sin Excel.", "fa-database", "analytics_dashboard"),
            ("Automatiza", "Alerta a responsable", "Riesgos, vencimientos y ausentismo abren la acción correcta.", "fa-gears", "analytics_alertas"),
            ("Deja listo", "Mejora en origen", "La decisión vuelve al módulo que corrige el problema.", "fa-share-nodes", "dashboard_aprobaciones"),
        ),
        "match_prefixes": (
            "/analytics/",
            "/reportes/",
            "/sistema/",
        ),
        "actions": (
            ("Analytics", "analytics_dashboard", "fa-chart-pie"),
            ("Alertas", "analytics_alertas", "fa-triangle-exclamation"),
            ("Rotación", "predictor_rotacion_panel", "fa-user-clock"),
            ("Reportes", "reportes_panel", "fa-file-lines"),
        ),
        "peru_focus": (
            ("Alertas RRHH", "analytics_alertas", "fa-triangle-exclamation", "Riesgos antes de cierre o inspección."),
            ("SUNAFIL", "documentos_inspeccion_sunafil", "fa-scale-balanced", "Evidencia lista para fiscalización."),
            ("Reportes", "reportes_panel", "fa-file-lines", "Informes sin rehacer Excel."),
        ),
    },
)


PROCESS_SEARCH_SHORTCUTS: tuple[dict[str, Any], ...] = (
    {
        "terms": ("alta", "ingreso", "contratar", "contrato", "legajo", "candidato", "onboarding", "t-registro"),
        "items": (
            ("Contratar express", "personal_create_express", "fa-bolt", "Crea ficha, contrato, legajo y acceso en un solo flujo."),
            ("Pipeline de candidatos", "pipeline_panel", "fa-stream", "Convierte una postulación en alta sin volver a escribir datos."),
            ("Contratos", "contratos_panel", "fa-file-contract", "Genera y firma documentos laborales desde la ficha única."),
            ("Legajo", "documentos_panel", "fa-folder-open", "Centraliza evidencias laborales para auditoría y SUNAFIL."),
        ),
    },
    {
        "terms": ("asistencia", "marca", "marcas", "tareo", "hora", "horas", "permiso", "vacacion", "biometrico"),
        "items": (
            ("Importar marcas", "asistencia_importar", "fa-file-import", "Carga biométrico y corrige datos antes de planilla."),
            ("Vista unificada de asistencia", "asistencia_vista", "fa-table", "Revisa faltas, tardanzas, permisos y descansos juntos."),
            ("Vacaciones", "vacaciones_panel", "fa-calendar-check", "Aprobaciones y saldos conectados con asistencia."),
            ("Exportar a pre-planilla", "asistencia_exportar_panel", "fa-file-export", "Deja horas y ausencias listas para nómina."),
        ),
    },
    {
        "terms": ("planilla", "nomina", "nómina", "pago", "boleta", "boletas", "plame", "afp", "cts", "cierre", "sunat"),
        "items": (
            ("Workflow mes", "workflow_mes", "fa-route", "Cierra asistencia, conceptos, boletas, banco y PLAME sin Excel paralelo."),
            ("Pre-planilla", "pre_planilla", "fa-clipboard-check", "Valida novedades antes de calcular nómina."),
            ("Boletas", "nominas_emision_boletas", "fa-receipt", "Emite y comunica boletas con trazabilidad."),
            ("SUNAT y bancos", "integraciones_panel", "fa-plug", "Exporta PLAME, AFP Net, CTS y archivos de pago."),
        ),
    },
    {
        "terms": ("talento", "evaluacion", "evaluación", "okr", "clima", "encuesta", "capacitacion", "capacitación", "pdi"),
        "items": (
            ("Evaluaciones", "evaluaciones_dashboard", "fa-star-half-alt", "Convierte desempeño en planes y acciones."),
            ("PDI", "planes_panel", "fa-road", "Da seguimiento a brechas y compromisos."),
            ("Capacitaciones", "capacitaciones_panel", "fa-graduation-cap", "Asigna cursos desde brechas reales."),
            ("Encuestas", "encuestas_panel", "fa-poll", "Conecta clima con acciones visibles."),
        ),
    },
    {
        "terms": ("comunicacion", "comunicación", "comunicado", "notificacion", "notificación", "campana", "campaña", "whatsapp"),
        "items": (
            ("Notificaciones", "com_notificaciones_panel", "fa-bell", "Envía recordatorios y conserva lectura."),
            ("Comunicados", "com_comunicados_panel", "fa-bullhorn", "Comunicación formal con destinatarios y acuse."),
            ("Campañas", "campanas_panel", "fa-paper-plane", "Segmenta mensajes por área, sede o grupo."),
            ("WhatsApp", "com_whatsapp_config", "fa-comments", "Configura mensajes para operación diaria."),
        ),
    },
    {
        "terms": ("analytics", "reporte", "reportes", "alerta", "alertas", "rotacion", "rotación", "direccion", "dirección", "sunafil"),
        "items": (
            ("Analytics", "analytics_dashboard", "fa-chart-pie", "Lee el ciclo completo sin pedir otro archivo."),
            ("Alertas RRHH", "analytics_alertas", "fa-triangle-exclamation", "Convierte riesgos en tareas accionables."),
            ("Rotación", "predictor_rotacion_panel", "fa-user-clock", "Detecta riesgo de salida y vuelve al origen."),
            ("Reportes", "reportes_panel", "fa-file-lines", "Prepara informes sin rehacer Excel."),
        ),
    },
)


def _safe_reverse(route_name: str) -> str | None:
    try:
        return reverse(route_name)
    except NoReverseMatch:
        return None


def _normalize_search_term(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def _resolved_action(label: str, route_name: str, icon: str) -> dict[str, str] | None:
    url = _safe_reverse(route_name)
    if not url:
        return None
    return {
        "label": label,
        "route_name": route_name,
        "icon": icon,
        "url": url,
    }


def _resolved_peru_focus(
    label: str,
    route_name: str,
    icon: str,
    detail: str,
) -> dict[str, str] | None:
    url = _safe_reverse(route_name)
    if not url:
        return None
    return {
        "label": label,
        "route_name": route_name,
        "icon": icon,
        "detail": detail,
        "url": url,
    }


def _resolved_handoff_item(
    step: str,
    label: str,
    detail: str,
    icon: str,
    route_name: str,
) -> dict[str, str] | None:
    url = _safe_reverse(route_name)
    if not url:
        return None
    return {
        "step": step,
        "label": label,
        "detail": detail,
        "icon": icon,
        "route_name": route_name,
        "url": url,
    }


def get_process_search_shortcuts(q: str) -> list[dict[str, str]]:
    """Devuelve accesos de proceso para búsquedas con intención operativa."""
    normalized_query = _normalize_search_term(q)
    shortcuts: list[dict[str, str]] = []
    seen_routes: set[str] = set()

    for group in PROCESS_SEARCH_SHORTCUTS:
        if not any(_normalize_search_term(term) in normalized_query for term in group["terms"]):
            continue

        for title, route_name, icon, detail in group["items"]:
            if route_name in seen_routes:
                continue
            url = _safe_reverse(route_name)
            if not url:
                continue
            seen_routes.add(route_name)
            shortcuts.append({
                "tipo": "flujo",
                "icono": icon,
                "color": "#0f766e",
                "titulo": title,
                "detalle": detail,
                "url": url,
            })

    return shortcuts


def get_process_stages() -> list[dict[str, Any]]:
    """Devuelve etapas con URLs reales, listas para renderizar."""
    stages: list[dict[str, Any]] = []
    home_url = _safe_reverse("home") or "/"

    for raw_stage in PROCESS_STAGES:
        stage = deepcopy(raw_stage)
        actions = [
            action
            for action_tuple in raw_stage["actions"]
            if (action := _resolved_action(*action_tuple)) is not None
        ]
        stage["actions"] = actions
        stage["peru_focus"] = [
            peru_item
            for peru_tuple in raw_stage.get("peru_focus", ())
            if (peru_item := _resolved_peru_focus(*peru_tuple)) is not None
        ]
        stage["handoff"] = [
            handoff_item
            for handoff_tuple in raw_stage.get("handoff", ())
            if (handoff_item := _resolved_handoff_item(*handoff_tuple)) is not None
        ]
        stage["url"] = _safe_reverse(raw_stage["primary_route"]) or (
            actions[0]["url"] if actions else home_url
        )
        stages.append(stage)

    return stages


def _matching_stage_index(path: str) -> int | None:
    path = path or "/"
    winner: tuple[int, int] | None = None

    for index, stage in enumerate(PROCESS_STAGES):
        for prefix in stage["match_prefixes"]:
            if path.startswith(prefix):
                score = len(prefix)
                if winner is None or score > winner[1]:
                    winner = (index, score)

    return winner[0] if winner else None


def current_stage_for_path(path: str) -> dict[str, Any] | None:
    index = _matching_stage_index(path)
    if index is None:
        return None
    return get_process_stages()[index]


def build_process_bridge(request, *, puede_ver_admin: bool = False) -> dict[str, Any]:
    """Arma el contexto de continuidad que se muestra en páginas admin."""
    path = getattr(request, "path", "/") or "/"
    stages = get_process_stages()
    index = _matching_stage_index(path)

    if not puede_ver_admin or index is None or path.startswith("/mi-portal/"):
        return {
            "show": False,
            "stages": stages,
            "current": None,
            "actions": [],
            "peru_focus": [],
            "handoff": [],
            "next_stage": None,
        }

    marked_stages = []
    for stage_index, stage in enumerate(stages):
        item = deepcopy(stage)
        item["is_current"] = stage_index == index
        marked_stages.append(item)

    current = marked_stages[index]
    next_stage = marked_stages[(index + 1) % len(marked_stages)]

    return {
        "show": True,
        "stages": marked_stages,
        "current": current,
        "actions": current["actions"][:4],
        "peru_focus": current["peru_focus"][:4],
        "handoff": current["handoff"][:3],
        "next_stage": next_stage,
    }
