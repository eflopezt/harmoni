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
        "id": "preparacion",
        "number": "01",
        "label": "Preparar",
        "icon": "fa-building-circle-check",
        "primary_route": "data_quality_center",
        "description": "RUC, empresa, estructura, responsables, usuarios y reglas quedan listos antes de mover personas.",
        "automation": "El saneamiento inicial evita que contratos, boletas, PLAME o reportes nazcan con datos incompletos.",
        "duplicate_guard": "Completa empresa, áreas y permisos una vez: el resto del ciclo reutiliza esa base.",
        "handoff": (
            ("Recibe", "Empresa y RUC objetivo", "Define el alcance: una empresa, varios RUC o vista consolidada.", "fa-building", "empresas_panel"),
            ("Automatiza", "Datos base saneados", "Harmoni valida empresa, legajos, permisos y campos críticos.", "fa-gears", "data_quality_center"),
            ("Deja listo", "Estructura operativa", "Áreas, usuarios y perfiles quedan listos para contratar.", "fa-share-nodes", "personal_create_express"),
        ),
        "match_prefixes": (
            "/calidad-datos/",
            "/empresas/",
            "/integraciones/configuracion/",
            "/areas/",
            "/subareas/",
            "/usuarios/",
            "/gestion-usuarios/",
            "/accesos/",
            "/sistema/permisos-modulos/",
        ),
        "actions": (
            ("Sanear datos", "data_quality_center", "fa-shield-check"),
            ("Empresas", "empresas_panel", "fa-building"),
            ("Áreas", "area_list", "fa-sitemap"),
            ("Usuarios", "gestion_usuario_lista", "fa-user-lock"),
        ),
        "peru_focus": (
            ("RUC y domicilio", "data_quality_center", "fa-id-card", "Datos legales completos para contratos y boletas."),
            ("Multi-RUC", "empresas_panel", "fa-layer-group", "Cada planilla se mantiene separada por empresa."),
            ("Permisos", "accesos_gestion", "fa-user-shield", "Acceso por rol y responsable."),
            ("Fiscalización", "documentos_inspeccion_sunafil", "fa-scale-balanced", "Evidencia preparada desde el inicio."),
        ),
    },
    {
        "id": "atraccion",
        "number": "02",
        "label": "Atraer",
        "icon": "fa-user-magnifying-glass",
        "primary_route": "pipeline_panel",
        "description": "Requisiciones, vacantes, candidatos, entrevistas y ofertas avanzan con trazabilidad.",
        "automation": "Una postulación contratada alimenta el alta sin volver a escribir DNI, puesto, sede o sueldo.",
        "duplicate_guard": "No crees una ficha nueva si viene del pipeline: conviértela para conservar origen y evidencia.",
        "handoff": (
            ("Recibe", "Necesidad aprobada", "La vacante parte de un responsable, motivo, área y prioridad.", "fa-inbox", "vacantes_panel"),
            ("Automatiza", "Pipeline y scoring", "Candidatos, CV, entrevistas y ranking quedan en un solo tablero.", "fa-gears", "pipeline_panel"),
            ("Deja listo", "Candidato contratado", "La oferta pasa a alta express con los datos ya capturados.", "fa-share-nodes", "personal_create_express"),
        ),
        "match_prefixes": (
            "/reclutamiento/",
        ),
        "actions": (
            ("Vacantes", "vacantes_panel", "fa-briefcase"),
            ("Pipeline", "pipeline_panel", "fa-stream"),
            ("CV express", "subir_cv_express", "fa-file-arrow-up"),
            ("Banco talento", "banco_de_talento", "fa-users"),
        ),
        "peru_focus": (
            ("Aprobación", "vacantes_panel", "fa-clipboard-check", "Requisición antes de publicar o contratar."),
            ("Consentimiento", "pipeline_panel", "fa-file-shield", "Datos del postulante con fuente y soporte."),
            ("Entrevistas", "calendario_entrevistas", "fa-calendar-days", "Agenda y resultados ligados a la vacante."),
        ),
    },
    {
        "id": "ingreso",
        "number": "03",
        "label": "Incorporar",
        "icon": "fa-user-plus",
        "primary_route": "control_tower",
        "description": "Alta, ficha, contrato, legajo, firma, accesos y onboarding parten del mismo colaborador.",
        "automation": "Alta express crea ficha base, contrato, legajo, portal y tareas de bienvenida desde una sola captura.",
        "duplicate_guard": "No dupliques fichas: el colaborador creado aquí alimenta asistencia, portal, nómina y reportes.",
        "handoff": (
            ("Recibe", "Candidato o alta directa", "DNI, cargo, sueldo, empresa, sede y fecha de ingreso llegan al alta.", "fa-id-badge", "pipeline_panel"),
            ("Automatiza", "Ficha, contrato y legajo", "Documentos, firma y onboarding nacen enlazados al trabajador.", "fa-gears", "personal_create_express"),
            ("Deja listo", "Colaborador operativo", "La misma ficha alimenta turnos, asistencia, solicitudes y nómina.", "fa-share-nodes", "asistencia_dashboard"),
        ),
        "match_prefixes": (
            "/personal/",
            "/empleados/",
            "/onboarding/",
            "/contratos/",
            "/documentos/",
        ),
        "actions": (
            ("Alta express", "personal_create_express", "fa-bolt"),
            ("Empleados", "personal_list", "fa-users"),
            ("Contratos", "contratos_panel", "fa-file-contract"),
            ("Legajo", "documentos_panel", "fa-folder-open"),
        ),
        "peru_focus": (
            ("T-Registro alta", "integ_treg_altas", "fa-id-card", "Archivo de alta SUNAT desde la ficha."),
            ("Firma digital", "firma_panel", "fa-signature", "Contrato y anexos con trazabilidad."),
            ("SUNAFIL", "documentos_inspeccion_sunafil", "fa-scale-balanced", "Carpeta inspectiva sin búsqueda manual."),
        ),
    },
    {
        "id": "operacion",
        "number": "04",
        "label": "Operar",
        "icon": "fa-fingerprint",
        "primary_route": "asistencia_dashboard",
        "description": "Turnos, marcas, papeletas, vacaciones, préstamos, viáticos y aprobaciones se resuelven antes de pagar.",
        "automation": "Las novedades aprobadas llegan a pre-planilla sin digitación paralela.",
        "duplicate_guard": "No recargues horas o ausencias en nómina: corrige asistencia, permisos y saldos en origen.",
        "handoff": (
            ("Recibe", "Colaborador activo", "Ficha, sede, horario y responsable vienen de incorporación.", "fa-id-badge", "control_tower"),
            ("Automatiza", "Marcas y novedades", "Biométrico, permisos, vacaciones y variables quedan conciliados.", "fa-gears", "asistencia_importar"),
            ("Deja listo", "Pre-planilla limpia", "Horas extra, faltas, descansos y descuentos pasan a nómina.", "fa-share-nodes", "pre_planilla"),
        ),
        "match_prefixes": (
            "/asistencia/",
            "/roster/",
            "/calendario/",
            "/vacaciones/",
            "/aprobaciones/",
            "/prestamos/",
            "/viaticos/",
        ),
        "actions": (
            ("Importar marcas", "asistencia_importar", "fa-file-import"),
            ("Vista unificada", "asistencia_vista", "fa-table"),
            ("Vacaciones", "vacaciones_panel", "fa-calendar-check"),
            ("Aprobaciones", "dashboard_aprobaciones", "fa-list-check"),
        ),
        "peru_focus": (
            ("Biométrico", "integ_biometrico", "fa-fingerprint", "Marcas reales antes del cierre."),
            ("Banco de horas", "asistencia_banco_horas", "fa-clock", "Horas extra y compensaciones ordenadas."),
            ("Calendario legal", "vacaciones_calendario", "fa-calendar-days", "Vacaciones, permisos y descansos visibles."),
        ),
    },
    {
        "id": "nomina",
        "number": "05",
        "label": "Pagar",
        "icon": "fa-file-invoice-dollar",
        "primary_route": "workflow_mes",
        "description": "Pre-planilla, período, cálculo, revisión, aprobación, boletas, bancos, SUNAT y contabilidad cierran el mes.",
        "automation": "Workflow mes reúne asistencia, conceptos, boletas, banco, AFP, PLAME y contabilidad en un solo cierre.",
        "duplicate_guard": "No calcules dos veces: aprueba una planilla y exporta todos los archivos desde ese cierre.",
        "handoff": (
            ("Recibe", "Novedades conciliadas", "Asistencia, préstamos, vacaciones y conceptos variables llegan desde operación.", "fa-clipboard-check", "pre_planilla"),
            ("Automatiza", "Cálculo Perú", "Planilla, gratificación, CTS, AFP, IR 5ta, EsSalud y boletas se calculan una vez.", "fa-gears", "workflow_mes"),
            ("Deja listo", "Pago y declaración", "Banco, PLAME, AFP Net, boletas y contabilidad salen del período aprobado.", "fa-share-nodes", "integraciones_panel"),
        ),
        "match_prefixes": (
            "/nominas/",
            "/integraciones/",
            "/cierre/",
            "/documentos/boletas/",
        ),
        "actions": (
            ("Workflow mes", "workflow_mes", "fa-route"),
            ("Pre-planilla", "pre_planilla", "fa-clipboard-check"),
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
        "number": "06",
        "label": "Desarrollar",
        "icon": "fa-chart-line",
        "primary_route": "evaluaciones_dashboard",
        "description": "Evaluaciones, OKR, planes, capacitaciones, disciplina, equidad y clima convierten señales en acciones.",
        "automation": "Cada resultado debe terminar en plan, capacitación, reconocimiento o alerta visible.",
        "duplicate_guard": "No abras reportes aislados: conecta encuesta, evaluación, plan y capacitación en el mismo ciclo.",
        "handoff": (
            ("Recibe", "Señales laborales", "Asistencia, desempeño, clima, brechas y rotación se leen juntos.", "fa-chart-simple", "analytics_dashboard"),
            ("Automatiza", "Brecha a plan", "Evaluación y encuesta generan PDI, capacitación o acción disciplinaria.", "fa-gears", "evaluaciones_dashboard"),
            ("Deja listo", "Acciones comunicables", "Planes, cursos y feedback quedan listos para seguimiento.", "fa-share-nodes", "planes_panel"),
        ),
        "match_prefixes": (
            "/evaluaciones/",
            "/capacitaciones/",
            "/encuestas/",
            "/salarios/",
            "/disciplinaria/",
        ),
        "actions": (
            ("Evaluaciones", "evaluaciones_dashboard", "fa-star-half-alt"),
            ("OKR", "okr_panel", "fa-bullseye"),
            ("Capacitaciones", "capacitaciones_panel", "fa-graduation-cap"),
            ("Encuestas", "encuestas_panel", "fa-poll"),
        ),
        "peru_focus": (
            ("360", "evaluacion_360_panel", "fa-users-viewfinder", "Feedback y brechas en el mismo ciclo."),
            ("PDI", "planes_panel", "fa-road", "Planes de acción después de evaluar."),
            ("Equidad", "equidad_salarial", "fa-scale-balanced", "Brechas salariales visibles por banda."),
        ),
    },
    {
        "id": "comunicacion",
        "number": "07",
        "label": "Comunicar",
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
            ("Docs laborales", "docs_laborales_panel", "fa-file-shield", "Políticas con lectura confirmada."),
            ("Comunicados", "com_comunicados_panel", "fa-bullhorn", "Avisos formales con destinatarios."),
            ("Campañas", "campanas_panel", "fa-paper-plane", "Recordatorios segmentados por área."),
        ),
    },
    {
        "id": "direccion",
        "number": "08",
        "label": "Dirigir",
        "icon": "fa-gauge-high",
        "primary_route": "analytics_dashboard",
        "description": "Analytics, alertas, rotación, auditoría y reportes leen el ciclo completo sin pedir nuevos archivos.",
        "automation": "Las alertas nacen de datos vivos y empujan acciones hacia RRHH, talento, comunicación o salida.",
        "duplicate_guard": "No armes otro tablero manual: usa analytics para auditar el flujo y volver al módulo origen.",
        "handoff": (
            ("Recibe", "Datos vivos", "Ingreso, asistencia, nómina, talento y comunicación se leen sin Excel paralelo.", "fa-database", "analytics_dashboard"),
            ("Automatiza", "Alerta a responsable", "Riesgos, vencimientos, ausentismo o rotación abren la acción correcta.", "fa-gears", "analytics_alertas"),
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
            ("Ejecutivo", "dashboard_ejecutivo", "fa-chart-line", "KPIs de grupo, empresa y costo laboral."),
            ("Auditoría", "audit_list", "fa-clock-rotate-left", "Cambios rastreables por usuario y fecha."),
            ("SUNAFIL", "documentos_inspeccion_sunafil", "fa-scale-balanced", "Evidencia lista para fiscalización."),
        ),
    },
    {
        "id": "salida",
        "number": "09",
        "label": "Desvincular",
        "icon": "fa-person-walking-arrow-right",
        "primary_route": "offboarding_panel",
        "description": "Cese, offboarding, devolución de activos, liquidación, documentos y baja SUNAT cierran el vínculo laboral.",
        "automation": "El cese genera pendientes, liquidación, documentos y bajas sin romper la historia del trabajador.",
        "duplicate_guard": "No cierres por fuera: registra el cese una vez y usa esa fecha para liquidación, baja y reportes.",
        "handoff": (
            ("Recibe", "Decisión de cese", "Motivo, fecha y responsable definen el cierre laboral.", "fa-inbox", "personal_list"),
            ("Automatiza", "Offboarding y liquidación", "Activos, accesos, vacaciones, CTS y documentos se atan al cese.", "fa-gears", "offboarding_panel"),
            ("Deja listo", "Historia cerrada", "Liquidación, baja T-Registro y constancias quedan auditables.", "fa-share-nodes", "nominas_liquidaciones"),
        ),
        "match_prefixes": (
            "/onboarding/offboarding/",
            "/documentos/cese/",
            "/nominas/liquidaciones/",
            "/nominas/liquidacion/",
        ),
        "actions": (
            ("Offboarding", "offboarding_panel", "fa-clipboard-check"),
            ("Cesar personal", "personal_cesar_batch", "fa-user-minus"),
            ("Liquidaciones", "nominas_liquidaciones", "fa-calculator"),
            ("Baja SUNAT", "integ_treg_bajas", "fa-id-card-clip"),
        ),
        "peru_focus": (
            ("Liquidación", "nominas_liquidaciones", "fa-file-invoice-dollar", "CTS, vacaciones truncas, gratificación y descuentos."),
            ("Baja T-Registro", "integ_treg_bajas", "fa-id-card-clip", "Archivo de baja para SUNAT."),
            ("Documentos cese", "pdf_cese_panel", "fa-folder-open", "Cartas y sustento de salida."),
        ),
    },
)


PROCESS_SEARCH_SHORTCUTS: tuple[dict[str, Any], ...] = (
    {
        "terms": (
            "configuracion", "configuración", "empresa", "ruc", "permiso",
            "permisos", "usuario", "usuarios", "area", "área", "estructura",
            "sanear", "calidad", "datos",
        ),
        "items": (
            ("Sanear datos", "data_quality_center", "fa-shield-check", "Completa empresa, legajos y campos críticos antes de operar."),
            ("Empresas", "empresas_panel", "fa-building", "Administra RUCs, sedes y vista consolidada."),
            ("Áreas", "area_list", "fa-sitemap", "Ordena áreas, subáreas y responsables."),
            ("Usuarios y accesos", "gestion_usuario_lista", "fa-user-lock", "Vincula personas, perfiles y permisos."),
        ),
    },
    {
        "terms": ("reclutamiento", "candidato", "candidatos", "vacante", "vacantes", "cv", "entrevista", "pipeline", "postulacion", "postulación"),
        "items": (
            ("Vacantes", "vacantes_panel", "fa-briefcase", "Crea requisiciones y publica puestos aprobados."),
            ("Pipeline de candidatos", "pipeline_panel", "fa-stream", "Mueve candidatos por etapas sin perder trazabilidad."),
            ("CV express", "subir_cv_express", "fa-file-arrow-up", "Carga un CV y crea el candidato más rápido."),
            ("Banco de talento", "banco_de_talento", "fa-users", "Reutiliza candidatos para futuras vacantes."),
        ),
    },
    {
        "terms": ("alta", "ingreso", "incorporar", "contratar", "contrato", "legajo", "onboarding", "t-registro"),
        "items": (
            ("Contratar express", "personal_create_express", "fa-bolt", "Crea ficha, contrato, legajo y acceso en un solo flujo."),
            ("Empleados", "personal_list", "fa-users", "Ficha única que alimenta todo el ciclo laboral."),
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
        "terms": ("talento", "desarrollo", "evaluacion", "evaluación", "okr", "clima", "encuesta", "capacitacion", "capacitación", "pdi", "disciplina", "equidad"),
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
    {
        "terms": ("cese", "cesar", "salida", "desvincular", "offboarding", "liquidacion", "liquidación", "baja", "no adeudo"),
        "items": (
            ("Offboarding", "offboarding_panel", "fa-clipboard-check", "Cierra tareas, activos y accesos del trabajador."),
            ("Cesar personal", "personal_cesar_batch", "fa-user-minus", "Registra fecha y motivo una sola vez."),
            ("Liquidaciones", "nominas_liquidaciones", "fa-calculator", "Calcula beneficios y documentos de cierre."),
            ("Baja SUNAT", "integ_treg_bajas", "fa-id-card-clip", "Prepara la baja para T-Registro."),
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
