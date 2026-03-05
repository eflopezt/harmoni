# Harmoni ERP — Progress Tracker
Última actualización: 2026-03-03

---

## Fase 0: Fundación [COMPLETADA]
### Block 0.0a: Limpieza profunda [COMPLETADO]
- [x] Eliminar backups, scripts dev, docs excesivos, templates backup, commands one-time

### Block 0.0b: Renombrar tareo/ → asistencia/ [COMPLETADO]
- [x] Directorio, templates, apps.py, INSTALLED_APPS, URLs, imports, template paths, URL names
- [x] label='tareo' para compatibilidad BD — Django check: OK

### Block 0.1: App core/ [COMPLETADO]
- [x] constants.py (leyes Peru), mixins.py (roles), templatetags/harmoni_tags.py

### Block 0.2: Corregir HE 100% [COMPLETADO]
- [x] processor.py: HE 100% = feriados + domingos/DSO trabajado (D.Leg. 713)

### Block 0.3: progress.md [COMPLETADO]

### Block 0.4: Split personal/views.py [COMPLETADO]
- [x] 7 archivos: home, areas, empleados, roster, aprobaciones, usuarios + __init__

### Block 0.5: Split asistencia/views.py [COMPLETADO]
- [x] 10 archivos: _common, dashboard, staff, rco, banco, importaciones, exportaciones, configuracion, kpis + __init__

### Block 0.6: UI ERP Profesional [COMPLETADO]
- [x] personal/context_processors.py — es_responsable, cambios_pendientes, areas_responsable, harmoni_version (globales)
- [x] config/settings/base.py — context processor registrado
- [x] static/css/harmoni.css — design system completo (~2050 líneas)
- [x] templates/base.html — sidebar ERP oscuro fijo, topbar, user dropdown con avatar, mobile overlay
- [x] templates/registration/login.html — branding Harmoni, toggle contraseña, show/hide password
- [x] templates/home.html — KPI cards, acciones rápidas, info sistema, bienvenida con fecha
- [x] templates/registration/password_change.html + password_change_done.html
- [x] personal/urls.py — rutas /cuenta/cambiar-password/

### Block 0.7: Identidad de Marca [COMPLETADO]
- [x] Paleta corporativa Teal: sidebar #0d2b27, primary #0f766e, accent #5eead4
- [x] Logo: El Hexágono Vivo — H cuyos 4 extremos coinciden con 4 vértices del hexágono
- [x] harmoni.css — todas las variables :root y colores hardcoded migrados a Teal
- [x] base.html — logo SVG hexágono en sidebar (26x26, blanco+mint sobre teal)
- [x] login.html — logo SVG hexágono en auth card (42x42, blanco+mint sobre teal)
- [x] Narrativa del nombre: trabaja en armonía con su entorno, le falta una letra — siempre hay algo más que podemos hacer

---

## Fase 1: Portal de Autoservicio [COMPLETADA]
### Block 1.1: App portal/ + vistas read-only [COMPLETADO]
- [x] portal/apps.py, urls.py, views.py
- [x] Vistas: portal_home, mi_perfil, mi_asistencia, mi_banco_horas, mi_roster
- [x] Filtro por mes/año en asistencia y roster
- [x] Manejo gracioso si usuario no está vinculado a Personal
- [x] Registrado en INSTALLED_APPS + config/urls.py (/mi-portal/)
- [x] django.contrib.humanize agregado a INSTALLED_APPS
### Block 1.2: Templates portal + sidebar [COMPLETADO]
- [x] templates/portal/: portal_home, mi_perfil, mi_asistencia, mi_banco_horas, mi_roster
- [x] base.html: sección "Mi Portal" en sidebar (visible a todos los usuarios autenticados)

## Fase 2: Vista Unificada + KPI Dashboard [EN PROGRESO]
### Block 2.1: Vista unificada STAFF + RCO [COMPLETADO]
- [x] asistencia/views/vista_unificada.py — tabs TODOS/STAFF/RCO, search, KPI cards, tfoot totales
- [x] templates/asistencia/vista_unificada.html — tabla unificada con columna Grupo condicional
- [x] asistencia/urls.py — path('vista/', ..., name='asistencia_vista')
- [x] base.html — link "Vista Unificada" en sidebar Asistencia

### Block 2.2: KPI Dashboard rediseñado [COMPLETADO]
- [x] Paleta Teal aplicada: stat-cards, paneles STAFF/RCO, iconos, borders
- [x] 3 gráficas Chart.js: donut distribución días, línea tendencia diaria, barras HE (25%/35%/100%)
- [x] Top ausentes en tabla dash-card (no list-group)
- [x] Fix JS: floatformat con locale usaba coma decimal → usar stringformat:"f" para valores JS
- [x] Estructura migrada a dash-card/stat-card system

### Block 2.3: Sistema de alertas [DIFERIDO a Fase 5]

## Fase 3: Workflow Cierre Mensual [COMPLETADA]
### Block 3.1 + 3.2: App cierre/ + Wizard UI [COMPLETADO]
- [x] cierre/models.py: PeriodoCierre + PasoCierre (7 pasos ordenados)
- [x] cierre/engine.py: motor ejecutores, inicializar_pasos(), ejecutar_paso()
- [x] cierre/views.py + urls.py: lista, wizard, crear, ejecutar_paso AJAX, ejecutar_todos, reabrir
- [x] templates/cierre/lista.html + wizard.html (UI paso a paso, progress bar, AJAX sin recarga)
- [x] base.html: sección OPERACIONES → Cierre Mensual
- [x] Fix: TareoImportacion usa periodo_inicio/fin y tipo; Personal usa grupo_tareo
- [x] JS: badge período actualiza a CERRADO al completar wizard

## Fase 1.3: Organigrama + Directorio [COMPLETADA]
- [x] portal/views.py: vistas organigrama (árbol Área→SubÁrea→Personas) y directorio (búsqueda)
- [x] portal/urls.py: /mi-portal/organigrama/ y /mi-portal/directorio/
- [x] templates/portal/organigrama.html: accordion tree, responsables chips, persona chips con mailto/tel
- [x] templates/portal/directorio.html: card grid 4col, búsqueda por nombre/cargo/correo/DNI, filtro área
- [x] base.html: links Organigrama + Directorio en sección Mi Portal
- [x] Fix: estado='Activo' (capitalizado) en filtros Personal

## Fase 4: Import Inteligente + IA [EN PROGRESO]
### Block 4.1: Inteligencia Contextual IA [COMPLETADO]
- [x] ai_context.py: 10 helpers de recolección (vacaciones, capacitaciones, evaluaciones, encuestas, préstamos, onboarding, disciplinaria, comunicaciones, reclutamiento, salarios)
- [x] build_system_prompt_data: parámetro `modules` para lazy loading — solo carga módulos relevantes
- [x] detect_module_context: detecta módulos por keywords del mensaje del usuario
- [x] System prompt reestructurado: secciones temáticas (PLANTILLA, ASISTENCIA, APROBACIONES, VACACIONES, DESARROLLO, BIENESTAR, FINANCIERO, RECLUTAMIENTO, OPERACIONAL, KPI)
- [x] Fallback sin IA (responder_sin_ia): 12 patrones de keywords → respuestas directas desde BD
- [x] views_ai.py: integración fallback en ai_chat_stream y ai_ask_data — chat funciona sin Ollama
- [x] ai_status: widget siempre visible (fallback como backup), indicador modo datos
- [x] detect_chart_request: 4 tipos nuevos (asistencia_semanal, he_distribucion, vacaciones_estado, capacitaciones_estado)
- [x] generate_chart_data: charts nuevos — bar stacked (asistencia 7d), doughnut (HE, vacaciones, caps)
- [x] harmoni-ai-chat.js: soporte [FALLBACK] marker + badge "Respuesta directa", multi-series bar chart
- [x] ai_chat_widget.html: 8 quick actions (antes 4) — empleados, asistencia, pendientes, contratos, vacaciones, capacitaciones, evaluaciones, gráfico áreas
- [x] build_insights_prompt: datos enriquecidos de todos los módulos para mejor generación de insights
- [x] Django check: 0 issues, todos los imports OK

### Block 4.2: Mejoras IA Ronda 2+3 (2026-03-03) [COMPLETADO]
**Bugs y estabilidad:**
- [x] Fix SSE newlines: _sse_text() escapa \n para transporte SSE, JS restaura en renderMarkdown
- [x] Fix ai_status: usa _is_ollama_reachable() con cache 30s (no test_connection directo)
- [x] Fix fallback genérico: respuesta "no reconozco" en vez de 503 cuando no hay match
- [x] Fix chart de edad: simplificado rangos (era tuples no usados, ahora ints)
- [x] Fix detección chart: reordenar tipo_contrato antes de tipo_personal (keyword 'tipo' demasiado genérica)

**Datos y contexto (42 campos):**
- [x] Datos demográficos: personal_masculino/personal_femenino en contexto base
- [x] Top areas ampliado de 5 a 10
- [x] build_system_prompt: sección GENERO en PLANTILLA, 7 reglas de comportamiento, NAVEGACION HARMONI, LEYES PERU

**Charts nuevos (13 tipos totales):**
- [x] tipo_contrato: doughnut por tipo de contrato
- [x] genero: doughnut M/F/Otro con colores cyan/púrpura/gris
- [x] edad: bar chart con 5 rangos etarios + colores por barra
- [x] regimen_pension: doughnut AFP/ONP
- [x] JS: per-bar colors para bar charts (colores individuales por barra)
- [x] JS: leyenda automática para bar charts con múltiples colores
- [x] JS: ícono dinámico en título (fa-chart-pie, fa-chart-bar, fa-chart-line)

**Fallback enriquecido (20+ patrones):**
- [x] Resumen general: cruza 12+ módulos (plantilla, asistencia, pendientes, contratos, vacaciones, desarrollo, préstamos, reclutamiento, onboarding, disciplinaria, eNPS, KPIs)
- [x] Empleados: incluye datos demográficos (148M/56F) y contratos por vencer
- [x] Patrones nuevos: saludos, resumen, KPIs, áreas, notificaciones, clima/eNPS, HE, ayuda

**Fallback en todos los endpoints:**
- [x] ai_insights: _build_static_insights() con reglas basadas en datos
- [x] ai_analyze_chart: _static_chart_analysis() sin Ollama
- [x] ai_ask_data: siempre responde (nunca 503)

**Performance (4 niveles de cache):**
- [x] Context cache: 15s TTL en build_system_prompt_data
- [x] Connectivity cache: 30s TTL en _is_ollama_reachable
- [x] Service singleton: 60s TTL en get_service()
- [x] Model resolution cache: 5min TTL global en _resolver_modelo

**Widget v2 completo:**
- [x] harmoni-ai-chat.js: v2 rewrite (~730 líneas)
- [x] scrollToBottom: double requestAnimationFrame
- [x] Suggestion chips: SUGGESTION_MAP con 12 contextos + _default
- [x] Typing indicator: "Pensando..." / "Consultando datos..." según modo
- [x] Markdown mejorado: h3/h4, listas numeradas, inline code, HR, escaped newlines
- [x] History: persiste isFallback, restaura badges en renderHistory
- [x] Ctrl+Shift+H: keyboard shortcut para toggle chat
- [x] Toggle quick actions: botón lightbulb en header
- [x] Exportar conversación: descarga .md con Markdown formateado + toast notification
- [x] 12 quick actions: Resumen, Empleados, Asistencia, Pendientes, Contratos, Vacaciones, Capacitaciones, Evaluaciones, Por Área, Género, Por Edad, Ayuda
- [x] harmoni-ai.css: toast notification, fallback badge, status indicators, suggestion chips

**Insights prompt mejorado:**
- [x] Estructura por secciones: PLANTILLA, ASISTENCIA HOY, OPERACIONES, KPIs, módulos temáticos
- [x] Formato obligatorio: emojis + negrita, 4 insights exactos, acciones con responsable
- [x] Datos: tasa presencia calculada, género, vacaciones acumuladas, PDI, incrementos

### Block 4.3: Maximize + Dashboard + Excel Export (2026-03-03) [COMPLETADO]
**Modo Maximizar (Fullscreen):**
- [x] HTML: botón #aiChatMaximize (reemplaza minimize duplicado)
- [x] CSS: .maximized fullscreen (inset:0, 100vw×100vh) — como un módulo más del sistema
- [x] CSS: backdrop overlay, dashboard grid 2x2, download button teal gradient
- [x] JS: toggleMaximize(), restoreFromMaximize(), rerenderVisibleCharts()
- [x] JS: ESC key cierra maximize, backdrop click también
- [x] JS: Chart.getChart(canvas).resize() con delay 350ms para transición CSS

**Dashboard Ejecutivo (multi-chart):**
- [x] detect_dashboard_request(): keywords "dashboard gerencia", "dashboard ejecutivo", etc.
- [x] generate_dashboard_data(): genera 4 charts (áreas, headcount, género, tipo_personal)
- [x] SSE: [MAXIMIZE] marker → auto-maximize + [CHART]×N en grid container
- [x] JS: dashboardGrid container con clase ai-dashboard-grid
- [x] CSS: flex-wrap grid 2x2 (calc(50% - 12px)), responsive stack en mobile
- [x] renderHistory(): soporta array de chartData para persistencia multi-chart

**Reporte Excel (.xlsx):**
- [x] NUEVO: asistencia/services/ai_excel_export.py — ReporteGerenciaExporter (openpyxl)
- [x] Sheet 1 "Resumen KPI": 15+ indicadores (headcount, género, contratos, asistencia, rotación, etc.)
- [x] Sheet 2 "Headcount por Área": tabla área × STAFF/RCO/M/F con totales
- [x] Sheet 3 "Tendencias": últimos 12 KPISnapshots (headcount, rotación, asistencia, HE, altas, bajas)
- [x] Sheet 4 "Alertas Activas": alertas RRHH con severidad coloreada
- [x] Estilo Harmoni: header dark teal (#0D2B27), accent #F0FDFA, zebra rows
- [x] Endpoint: POST /asistencia/ia/exportar/ → HttpResponse .xlsx
- [x] detect_export_request(): keywords "exportar reporte", "reporte excel", etc.
- [x] SSE: [DOWNLOAD:type] marker → botón styled en chat
- [x] JS: window.aiDownloadReport() — POST fetch → blob → download

**Quick Actions (14 totales):**
- [x] Dashboard (fa-columns), Reporte Excel (fa-file-excel) — nuevos
- [x] Suggestions: dashboard, gerencia, reporte, excel contexts

**Verificado:**
- [x] Django check: 0 issues
- [x] Maximize: fullscreen 100vw×100vh, ESC restore, backdrop
- [x] Dashboard: auto-maximize, 3 charts en grid 2x2 (headcount sin data KPI)
- [x] Excel: 4 sheets generados, endpoint 200 OK, download funcional
- [x] Download button: placeholder AIDLBTN (no underscores para evitar conflicto markdown)

## Fase 5: Módulo Configuración Central [EN PROGRESO]
### Block 5.1: Campos IA + UI rediseñada [COMPLETADO]
- [x] ConfiguracionSistema: ia_provider (OLLAMA|NINGUNO), ia_endpoint, ia_modelo — sin cloud API keys
- [x] Migraciones: 0004 (agregar campos), 0005 (eliminar anthropic_api_key, openai_api_key)
- [x] configuracion_view POST: guarda todos los campos (incluyendo reloj_col_tipo_trab, reloj_col_area, IA Ollama)
- [x] templates/asistencia/configuracion.html: rediseño completo — 6 tabs, paleta Teal, dash-card, Font Awesome
- [x] Tab IA: solo Ollama — panel dinámico JS (oculta modelo/endpoint cuando "Sin IA")
- [x] Django check: 0 issues

### Block 5.2: Feriados CRUD [COMPLETADO]
- [x] 4 endpoints: feriado_crear, feriado_editar, feriado_eliminar, feriados_cargar_peru
- [x] Modal Bootstrap add/edit con validación JS
- [x] Tabla con botones editar/eliminar por fila (actualización DOM sin recarga)
- [x] "Cargar Perú": 12 feriados nacionales hardcoded (D.Leg. 713) — selección de año 2024-2028
- [x] parametros_view pasa anio_actual + anios_feriados al contexto
- [x] Verificado: 12 feriados 2026 cargados correctamente, modal funciona

### Block 5.3: Módulos adicionales [COMPLETADO]
- [x] Homologaciones CRUD — toolbar + modal + agregar/editar/eliminar AJAX
- [x] Regímenes de turno CRUD — tabla + modal 10 campos + crear/editar/eliminar AJAX, validación eliminar con horarios asociados
- [x] Horarios CRUD — tabla + modal 7 campos + crear/editar/eliminar AJAX, selector régimen dinámico, soporte turno nocturno
- [x] Preferencias por usuario — PreferenciaUsuario model (core), vistas GET/POST + API AJAX, template con Interface/Notificaciones/Cuenta, auto-save switches

### Block 5.4: Papeletas de Compensación [COMPLETADO]
- [x] Modelo PapeletaCompensacion (migración 0006): personal, tipo, fechas, estado, aprobado_por
- [x] processor.py: carga papeletas activas (APROBADA/EJECUTADA) en __init__; _calcular_horas recibe `tiene_papeleta_comp` — si True, feriado/DSO se trata como día normal (HE 25/35 en vez de 100%)
- [x] Vistas: papeletas_view (lista+filtros), papeleta_crear, papeleta_editar, papeleta_eliminar
- [x] Template dedicado: /asistencia/papeletas/ — tabla con filtros, modal CRUD, info legal
- [x] Sidebar: link "Papeletas Comp." bajo Banco de Horas

### Block 5.5: Control de Horas Extra [COMPLETADO]
- [x] ConfiguracionSistema: `he_requiere_solicitud` (bool) — migración 0007
- [x] Modelo SolicitudHE: personal, fecha, horas_estimadas, tipo (PAGABLE/COMPENSABLE), motivo, estado, aprobado_por — migración 0007
- [x] processor.py: si `he_requiere_solicitud=True` y no hay SolicitudHE aprobada → `he_bloqueado=True` → HE = 0
- [x] Admin: vistas CRUD + lista con filtros + aprobación (asistencia/views/solicitudes_he.py)
- [x] Template admin: /asistencia/solicitudes-he/ — tabla + modal + indicador control activo/inactivo
- [x] Portal trabajador: mis_solicitudes_he, solicitud_he_crear, solicitud_he_anular
- [x] Template portal: /mi-portal/solicitudes-he/ — tabla + modal + filtros año/mes + indicador control HE
- [x] Sidebar: link "Solicitudes HE" en MI PORTAL
- [x] Base legal: DL 728 + DS 007-2002-TR — HE son voluntarias, empleador puede establecer flujo de autorización

### Block 5.6: Justificaciones de No-Marcaje [COMPLETADO]
- [x] Modelo JustificacionNoMarcaje: personal, fecha, tipo (8 opciones), motivo, estado, revisado_por — migración 0008
- [x] Admin: vistas lista + revisar (aprobar/rechazar con comentario) + eliminar
- [x] Template admin: /asistencia/justificaciones/ — tabla con filtros + aprobación inline
- [x] Portal: mis_justificaciones, justificacion_crear (get_or_create), justificacion_anular
- [x] Template portal: /mi-portal/justificaciones/ — tabla + modal + filtros año/mes
- [x] Sidebar: link "Mis Justificaciones" en MI PORTAL + "Justificaciones" en ASISTENCIA

### Block 5.7: Rediseño Sistema de Papeletas [COMPLETADO]
**Decisión arquitectural**: Papeletas unificadas — importadas O creadas en sistema, un solo modelo
- [x] RegistroPapeleta extendido: origen (IMPORTACION/SISTEMA/PORTAL), estado (APROBADA/PENDIENTE/RECHAZADA/EJECUTADA/ANULADA), creado_por, aprobado_por, fecha_aprobacion, observaciones, fecha_referencia
- [x] importacion FK → nullable, 17 tipos de permiso (VAC, LSG, LCG, DM, CHE, DL, DLA, etc.)
- [x] processor.py: usa RegistroPapeleta unificado para compensaciones (CPF/CDT con estado APROBADA/EJECUTADA)
- [x] Admin papeletas: CRUD completo + aprobar/rechazar + filtros (año, tipo, estado, origen, trabajador) + color-coded pills
- [x] Protección: papeletas importadas no se pueden eliminar, solo las creadas manualmente
- [x] Portal trabajador: "Mis Papeletas" — solicitar VAC, LSG, LCG, CHE, DM, etc. + anular propias
- [x] Sidebar: "Mis Papeletas" en MI PORTAL, "Papeletas" en ASISTENCIA (renombrado de "Papeletas Comp.")
- [x] Migración 0009_unificar_papeletas aplicada (637 registros existentes conservados)
- [x] Reporte post-cierre "Rezagos": faltas/anomalías/papeletas/HE entre día (corte+1) y fin de mes
- [x] Botón "Rezagos Post-Cierre" visible en wizard cuando período está CERRADO

## Fase 6: Portal del Trabajador Ampliado [EN PROGRESO]
### Block 6.1: Justificación de no-marcaje [COMPLETADO en 5.6]

### Block 6.2: Boletas de Pago Digital [COMPLETADO]
**Base legal (DS 009-2011-TR + DS 003-2013-TR)**
- [x] Modelo BoletaPago: personal, periodo, tipo (MENSUAL/GRATIFICACION/CTS/LIQUIDACION/UTILIDADES), archivo PDF upload, resumen (bruta/descuentos/neto), constancia lectura (IP+timestamp+confirmación)
- [x] Admin panel: upload PDF, publicar individual/masivo, anular, filtros
- [x] Portal: "Mis Boletas" — lista por año, descarga, confirmar recepción (DS 009-2011-TR)
- [x] Diseño upload-only: boletas vienen de software externo, Harmoni gestiona distribución

### Block 6.3: Documentación Digital (Memos y Comunicados) [COMPLETADO]
- [x] Modelo: DocumentoLaboral (7 tipos: REGLAMENTO/POLITICA/COMUNICADO/MEMO/CARTA/SST/OTRO)
- [x] Modelo: EntregaDocumento — constancia individual por destinatario (visto + confirmado + IP)
- [x] Admin: crear, publicar (genera entregas automáticas), archivar, detalle con tasa confirmación
- [x] Portal trabajador: "Mis Documentos Laborales" — pendientes de confirmar, historial
- [x] doc_laboral_ver: marca como visto al abrir; doc_laboral_confirmar: constancia legal
- [x] Base legal: DS 003-97-TR Art. 35, Ley 29783 Art. 35, DL 728
- [x] Sidebar: admin → "Docs. Laborales" + portal → "Mis Documentos Laborales"

## Fase INFRA: Fundación Técnica Crítica [EN PROGRESO]
**⚠️ PRIORIDAD MÁXIMA — Si no se planea ahora, refactorizar después cuesta 10x**

### Block INFRA.1: Multi-empresa / Multi-sede [PENDIENTE]
**Por qué ahora**: Si `Personal` no tiene `empresa_id` desde el inicio, migrar después rompe TODA la data
- [ ] Modelo: Empresa (ruc, razon_social, nombre_comercial, logo, direccion, representante_legal)
- [ ] Modelo: Sede (empresa FK, nombre, direccion, ciudad, es_principal)
- [ ] FK `empresa` en: Personal, Area, ConfiguracionSistema, TareoImportacion, PeriodoCierre
- [ ] FK `sede` en: Personal, Area (opcional — no toda empresa tiene multi-sede)
- [ ] Middleware: `EmpresaMiddleware` — detecta empresa activa del usuario logueado
- [ ] Context processor: `empresa_actual`, `sede_actual` disponibles en todo template
- [ ] Superadmin puede ver todas las empresas; usuario normal solo ve la suya
- [ ] ConfiguracionSistema se vuelve **por empresa** (cada empresa tiene su config)
- [ ] Login: si usuario pertenece a >1 empresa, selector post-login
- [ ] Migración de data existente: crear empresa default, asignar a todos los registros actuales

### Block INFRA.2: Audit Trail [COMPLETADO]
- [x] Modelo AuditLog (core/models.py): content_type FK, object_id, accion (CREATE/UPDATE/DELETE), descripcion, cambios JSONField, usuario, ip_address, timestamp
- [x] core/audit.py: log_create(), log_update(), log_delete() — usados en todas las vistas críticas
- [x] Thread-local storage: AuditMiddleware captura request actual para vistas sin request explícito
- [x] Serialización segura de valores (datetimes, Decimals, FKs)
- [x] Aplicado en: personal, documentos, asistencia, papeletas, banco horas, disciplinaria

### Block INFRA.3: Permisos Granulares [PENDIENTE]
**Por qué ahora**: El sistema de roles básico no escala. Necesitamos permisos por objeto, no solo por rol
- [ ] Modelo: PerfilPermiso (usuario, tipo: ROL/AREA/SEDE/EMPRESA, scope)
- [ ] Permisos por objeto: "Jefe Área X solo ve empleados de Área X"
- [ ] Permisos por sede: "HR Lima no ve HR Arequipa"
- [ ] Permisos por módulo: "Contador solo ve Nómina y Reportes"
- [ ] Decorador: `@permiso_requerido('modulo.accion')` — reemplaza `@login_required` básico
- [ ] Mixin vista: `PermisoMixin` — filtra querysets automáticamente según permisos del usuario
- [ ] UI: panel de permisos en admin de usuarios (checkboxes por módulo + scope)
- [ ] Migración: roles actuales (is_staff, es_responsable) se mapean a nuevos permisos

### Block INFRA.4: Workflow Engine Genérico [PENDIENTE]
**Por qué ahora**: Onboarding, offboarding, vacaciones, permisos, HE — todos son workflows. Uno genérico = N módulos gratis
- [ ] Modelo: PlantillaWorkflow (nombre, modulo, pasos JSON, activa)
- [ ] Modelo: InstanciaWorkflow (plantilla FK, objeto_relacionado: GenericFK, estado, iniciado_por, fecha_inicio)
- [ ] Modelo: PasoWorkflow (instancia FK, orden, titulo, tipo: APROBACION/TAREA/AUTOMATICO/NOTIFICACION, responsable, estado, fecha_completado)
- [ ] Motor: al completar un paso, evalúa condiciones y avanza al siguiente (o bifurca)
- [ ] Tipos de paso: aprobación (requiere acción humana), tarea (checklist), automático (ejecuta función), notificación (envía email)
- [ ] API interna: `WorkflowService.iniciar(plantilla, objeto)`, `.completar_paso(paso, usuario)`, `.cancelar(instancia)`
- [ ] Configurable desde UI: HR puede crear/editar plantillas de workflow sin código
- [ ] Integración: onboarding, offboarding, solicitud vacaciones, solicitud HE — todos consumen este engine

### Block INFRA.5: API REST [COMPLETADO]
**Por qué ahora**: App móvil, reloj biométrico, contabilidad externa, integraciones — todo necesita API
- [x] Django REST Framework ya instalado y configurado (SessionAuth + filtros)
- [x] Autenticación: JWT (SimpleJWT) — access 8h, refresh 7d, rotate + blacklist
- [x] Central API Router: `/api/v1/` con 12 módulos (core/api_urls.py)
- [x] **171 endpoints** across 12 modules: personal, asistencia, vacaciones, prestamos, documentos, capacitaciones, evaluaciones, encuestas, salarios, reclutamiento, comunicaciones, analytics
- [x] Serializers para todos los módulos: api_serializers.py + api_views.py + api_urls.py en cada app
- [x] ViewSets ReadOnly para datos sensibles, ModelViewSet para creación donde aplica
- [x] Versionado: `/api/v1/` (backward compat `/api/` mantenido)
- [x] Documentación automática: drf-spectacular — Swagger UI en `/api/v1/docs/`, ReDoc en `/api/v1/redoc/`
- [x] Health endpoint: `/api/v1/health/` (sin auth)
- [x] JWT Token endpoints: `/api/v1/token/`, `/api/v1/token/refresh/`
- [x] OpenAPI schema: `/api/v1/schema/`
- [x] Tags Swagger por módulo (11 tags configurados)
- [ ] Throttling y rate limiting (futuro)
- [ ] Webhooks salientes (futuro)

---

## Fase 7: Onboarding & Offboarding [COMPLETADA]
### Block 7.1: Workflow de Onboarding [COMPLETADO]
- [x] 4 modelos: PlantillaOnboarding, PasoPlantilla, ProcesoOnboarding, PasoOnboarding
- [x] PlantillaOnboarding: aplica_grupo (STAFF/RCO/TODOS), aplica_areas M2M, pasos configurables
- [x] PasoPlantilla: tipo (TAREA/DOCUMENTO/CAPACITACION/NOTIFICACION/APROBACION), responsable_tipo (RRHH/JEFE/TI/TRABAJADOR), dias_plazo
- [x] ProcesoOnboarding: estado EN_CURSO→COMPLETADO/CANCELADO, auto-genera PasoOnboarding desde plantilla
- [x] Checklist digital con completar/omitir pasos AJAX, % avance, fecha_limite auto-calc
- [x] Portal: "Mi Onboarding" — empleado ve su checklist y progreso
- [x] Admin: panel con stats, filtros, crear proceso, detalle con checklist interactivo
- [x] Plantillas CRUD: gestión de plantillas con agregar/eliminar pasos AJAX
- [x] Seed: "Onboarding General" (8 pasos) + "Offboarding General" (6 pasos)

### Block 7.2: Workflow de Offboarding [COMPLETADO]
- [x] 4 modelos: PlantillaOffboarding, PasoPlantillaOff, ProcesoOffboarding, PasoOffboarding
- [x] motivo_cese: RENUNCIA/DESPIDO/MUTUO_ACUERDO/FIN_CONTRATO/JUBILACION
- [x] Panel, crear, detalle con misma mecánica que onboarding
- [ ] Emails automáticos (requiere Fase 8: Motor Comunicaciones)
- [ ] Cálculo liquidación automática (requiere Fase 20: Nóminas)

### Block 7.3: Periodo de Prueba & Contratos [COMPLETADO]
- [x] Personal.TIPO_CONTRATO_CHOICES (13 modalidades D.Leg. 728) — migración 0013
- [x] Campos: tipo_contrato, fecha_inicio/fin_contrato, renovacion_automatica, observaciones_contrato
- [x] Properties: periodo_prueba_meses (3/6/12), fecha_fin_periodo_prueba, en_periodo_prueba, dias_para_vencimiento_contrato
- [x] Panel contratos: KPIs vencidos/próximos/en prueba, tabs 3 vistas, lista paginada con filtros
- [x] personal_detail.html: sección Contrato Laboral con badge período de prueba
- [x] forms.py: PersonalForm incluye campos de contrato con DateInput widgets
- [x] AlertaRRHH: nueva categoría CONTRATOS en analytics/models.py
- [x] analytics/services.py: generar_alertas() — contratos vencidos/por vencer/período de prueba
- [x] management command alertas_diarias: --dry-run, --solo-contratos, --solo-vacaciones (idempotente)

## Fase 8: Comunicaciones Inteligentes [COMPLETADA]
### Block 8.1: Motor de Notificaciones [COMPLETADO]
- [x] 6 modelos: PlantillaNotificacion, Notificacion, ComunicadoMasivo, ConfirmacionLectura, PreferenciaNotificacion, ConfiguracionSMTP
- [x] Motor centralizado: NotificacionService (services.py) — enviar, enviar_desde_plantilla, enviar_masivo, marcar_leida
- [x] PlantillaNotificacion: Django template syntax para asunto/cuerpo, módulo (RRHH/ASISTENCIA/ONBOARDING/etc.), tipo (EMAIL/IN_APP/AMBOS)
- [x] ConfiguracionSMTP: singleton, test_connection(), firma_html
- [x] Admin: dashboard stats (hoy/semana/mes/fallidas), CRUD plantillas con preview, config SMTP con test AJAX
- [x] Seed: 8 plantillas default (bienvenida, evaluación, encuesta, vacaciones aprobadas/rechazadas, disciplinaria, préstamo, comunicado)

### Block 8.2: Comunicaciones del Ciclo de Vida [PARCIAL]
- [x] Plantillas creadas para onboarding, evaluaciones, encuestas, vacaciones, disciplinaria, préstamos
- [ ] Disparadores automáticos (cumpleaños, aniversario, periodo prueba) — requiere cron/celery

### Block 8.3: Comunicados Masivos [COMPLETADO]
- [x] ComunicadoMasivo: destinatarios_tipo (TODOS/AREA/GRUPO/INDIVIDUAL), M2M áreas y personal
- [x] ConfirmacionLectura: tracking lectura por destinatario, tasa_lectura property
- [x] PreferenciaNotificacion: frecuencia (INMEDIATO/DIARIO/SEMANAL), horario silencio
- [x] Portal: "Mis Notificaciones" inbox + "Mis Comunicados" con confirmación lectura
- [x] Admin: crear comunicado, enviar masivo, detalle con progress bar confirmaciones

## Fase 9: Reclutamiento & Selección [COMPLETADA]
### Block 9.1: Gestión de Vacantes y Postulaciones [COMPLETADO]
- [x] 5 modelos: Vacante, EtapaPipeline, Postulacion, NotaPostulacion, EntrevistaPrograma
- [x] Vacante: prioridad, tipo_contrato, salario_min/max, educacion_minima, publica flag
- [x] EtapaPipeline: configurable con orden/color, seed 8 etapas default
- [x] Pipeline kanban: vista por vacante con postulaciones como cards, mover etapa AJAX
- [x] Postulacion: fuente (PORTAL/LINKEDIN/REFERIDO/HEADHUNTER), CV upload, estado tracking
- [x] Entrevistas: programar, tipo/modalidad/enlace_virtual, registrar resultado AJAX
- [x] Pipeline cross-vacante: vista general todas las vacantes activas
- [x] Portal público de empleo: standalone HTML (sin base.html), branding Harmoni, cards responsivas
- [x] Portal postular: formulario público con CV upload
- [x] Admin: 16 vistas, 8 templates, config etapas CRUD
- [ ] Parsing CV con Ollama (futuro)
- [ ] Al contratar → disparar onboarding automático (futuro integración)

## Fase 10: Vacaciones y Permisos [COMPLETADA]
**Base legal**: DL 713 (30 días/año calendario), DS 012-92-TR (reglamento)
### Block 10.1: Gestión de Vacaciones [COMPLETADO]
- [x] Modelo SaldoVacacional: personal, periodo, dias_derecho=30, gozados, vendidos, pendientes, recalcular()
- [x] Modelo SolicitudVacacion: personal, saldo FK, fechas, dias_calendario auto-calc, estado workflow, aprobar/rechazar
- [x] Modelo VentaVacaciones: máx 15 días (DL 713 Art. 19), monto, auto-actualiza saldo
- [x] Admin panel: solicitudes con filtros, aprobar/rechazar AJAX, generar saldos masivos
- [x] Portal: "Mis Vacaciones" con saldos, progress bars, solicitar, anular

### Block 10.2: Permisos y Licencias [COMPLETADO]
- [x] Modelo TipoPermiso: 12 tipos Perú (paternidad, maternidad, fallecimiento, matrimonio, etc.)
- [x] Modelo SolicitudPermiso: personal, tipo FK, fechas, sustento FileField, estado workflow
- [x] Admin panel: permisos con filtros por tipo/estado, aprobar/rechazar AJAX
- [x] Portal: "Mis Permisos" — solicitar con sustento, anular, tipos disponibles
- [x] Config: CRUD tipos de permiso (modal AJAX)
- [x] Seed: 12 tipos Perú con base legal (Ley 29409, Ley 26644, DL 713, etc.)

## Fase 11: Legajo Digital del Trabajador [COMPLETADA]
**Reemplaza la carpeta física — todo documento del trabajador vive en el sistema**
### Block 11.1: Gestión Documental [COMPLETADO]
- [x] Modelo CategoriaDocumento: nombre, icono FontAwesome, orden, activa
- [x] Modelo TipoDocumento: nombre, categoría FK, obligatorio, vence, dias_alerta, aplica_staff/rco
- [x] Modelo DocumentoTrabajador: personal, tipo, archivo FileField, nombre, fecha_emision, fecha_vencimiento, estado (VIGENTE/VENCIDO/POR_VENCER/ANULADO), version, subido_por
- [x] Auto-cálculo estado: save() evalúa fecha_vencimiento vs hoy → VENCIDO/POR_VENCER/VIGENTE
- [x] Versionado: upload incrementa version automáticamente
- [x] Admin panel: KPIs vencidos/por vencer, tabla personal con contadores, alertas, subir docs AJAX
- [x] Legajo por trabajador: docs agrupados por categoría, documentos faltantes obligatorios
- [x] Reporte "Documentos Faltantes": matriz personal × obligatorios → cuáles faltan (filtro STAFF/RCO)
- [x] Tipos CRUD: modal AJAX agregar/editar/desactivar con campos vence/obligatorio/aplica_*
- [x] Seed: 7 categorías + 32 tipos predefinidos Perú (command seed_documentos)
- [x] Sidebar admin: "Documentos" → "Legajo", "Tipos", "Constancias", "Faltantes", "Boletas", "Docs. Laborales"
- [x] Constancias: PlantillaConstancia con Django template syntax, generación PDF (services.py), preview AJAX

## Fase 12: Evaluaciones de Desempeño [COMPLETADA]
### Block 12.1: Evaluaciones [COMPLETADO]
- [x] 9 modelos: Competencia, PlantillaEvaluacion, PlantillaCompetencia, CicloEvaluacion, Evaluacion, RespuestaEvaluacion, ResultadoConsolidado, PlanDesarrollo, AccionDesarrollo
- [x] CicloEvaluacion: tipos 90/180/360/OKR/PRUEBA, estados BORRADOR→ABIERTO→EN_EVALUACION→CALIBRACION→CERRADO
- [x] 360°: evaluaciones AUTO + JEFE auto-generadas, soporte PAR/SUBORDINADO/CLIENTE
- [x] Calibración: puntaje_calibrado en ResultadoConsolidado
- [x] **9-Box Grid**: performance × potencial (3x3), visualización matricial color-coded
- [x] PDI: PlanDesarrollo + AccionDesarrollo (tipo CAPACITACION/PROYECTO/MENTORIA), % avance
- [x] Portal: "Mis Evaluaciones" — ver asignadas, completar con slider por competencia
- [x] Seed: 16 competencias (6 Core, 4 Liderazgo, 4 Técnica, 2 Interpersonal)
- [x] Admin: 16 vistas, 10 templates, 19 URL patterns

### Block 12.2: OKRs y KPIs por Puesto [COMPLETADO — 2026-03-02]
- [x] Modelo ObjetivoClave: nivel (EMPRESA/AREA/INDIVIDUAL), cascada self-FK, período (TRIMESTRAL/SEMESTRAL/ANUAL), anio/trimestre, status, peso, vinculación ciclo evaluación
- [x] Modelo ResultadoClave (KR): descripción, unidad (7 tipos: %/Número/S//Sí-No/Puntos/Días/Horas/Personalizado), valor_inicial/meta/actual, completado_binario (SI_NO), responsable, fecha_limite
- [x] Modelo CheckInOKR: historial de actualizaciones de progreso con fecha+valor+comentario+registrado_por
- [x] Properties: avance_promedio (obj), porcentaje_avance (kr), periodo_display, color_status, color_avance
- [x] views_okr.py: panel, crear, editar, detalle, cambiar_status, eliminar, kr_crear, kr_actualizar, kr_eliminar, checkin_registrar, mis_okrs
- [x] Templates: okr_panel.html, okr_form.html, okr_detalle.html (con modales AJAX para KRs y check-ins), mis_okrs.html
- [x] API REST: ObjetivoClaveViewSet, ResultadoClaveViewSet, CheckInOKRViewSet en /api/v1/evaluaciones/
- [x] Sidebar: "OKRs" en sección Evaluaciones (admin) + "Mis OKRs" en Mi Portal
- [x] Migración 0002 aplicada. Django check: 0 issues.

## Fase 13: Capacitaciones / LMS Ligero [COMPLETADA]
### Block 13.1: Gestión de Capacitaciones [COMPLETADO]
- [x] Modelo CategoriaCapacitacion: nombre, código, icono, color, orden
- [x] Modelo Capacitacion: título, tipo (INTERNA/EXTERNA/ELEARNING/INDUCCION/SSOMA), instructor, horas, costo, M2M participantes through AsistenciaCapacitacion, estado, obligatoria
- [x] Modelo AsistenciaCapacitacion: through model con estado, nota, aprobado, certificado
- [x] Modelo RequerimientoCapacitacion: aplica_todos/staff/rco, áreas M2M, frecuencia, vigencia, obligatorio
- [x] Modelo CertificacionTrabajador: personal, requerimiento, vencimiento, auto-estado (VIGENTE/POR_VENCER/VENCIDA)
- [x] Admin panel: capacitaciones con stats (horas, costo, inscritos), filtros, crear/detalle
- [x] Detalle: gestión participantes AJAX, registro asistencia/nota, completar
- [x] Requerimientos panel: lista de requerimientos obligatorios con frecuencia/vigencia
- [x] Incumplimientos panel: matriz personal × requerimiento, quién falta capacitarse
- [x] Portal: "Mis Capacitaciones" — historial, horas totales, certificaciones vigentes

## Fase 14: Préstamos y Adelantos [COMPLETADA]
### Block 14.1: Gestión de Préstamos [COMPLETADO]
- [x] 3 modelos: TipoPrestamo, Prestamo, CuotaPrestamo
- [x] TipoPrestamo: max_cuotas, tasa_interes_mensual, monto_maximo, requiere_aprobacion
- [x] Prestamo: estados BORRADOR→PENDIENTE→APROBADO→EN_CURSO→PAGADO/CANCELADO, auto-genera cuotas con residuo en última
- [x] CuotaPrestamo: registrar_pago parcial/total, auto-cierre préstamo al completar todas
- [x] Admin: panel con stats, crear, detalle con cuotas, aprobar, cancelar, pagar cuota AJAX
- [x] Portal: "Mis Préstamos" — historial personal
- [x] Seed: seed_tipos_prestamo
- [x] Límites: monto_maximo + max_cuotas por tipo
- [ ] Descuento automático en nómina (requiere Fase 20: Nóminas)

## Fase 15: Estructura Salarial [COMPLETADA]
### Block 15.1: Bandas y Compensaciones [COMPLETADO]
- [x] 4 modelos: BandaSalarial, HistorialSalarial, SimulacionIncremento, DetalleSimulacion
- [x] BandaSalarial: cargo+nivel, min/medio/max, moneda PEN/USD, amplitud, compa_ratio(), posicion_en_banda()
- [x] HistorialSalarial: motivo INGRESO/INCREMENTO/PROMOCION/AJUSTE/REVALORACION, porcentaje auto-calc
- [x] SimulacionIncremento: tipo PORCENTAJE/MONTO_FIJO, estado BORRADOR→APROBADA→APLICADA, presupuesto_total
- [x] DetalleSimulacion: toggle aprobado individual, porcentaje_incremento property
- [x] Simulador masivo: genera propuestas por % o monto fijo, filtro por área, dentro_presupuesto check
- [x] Aplicar incrementos: transacción atómica (crea HistorialSalarial + actualiza Personal.sueldo_base)
- [x] Admin: 13 vistas, 6 templates, 13 URL patterns
- [x] Portal: "Mi Historial Salarial" via portal/urls.py
- [x] ConfiguracionSistema: mod_salarios flag + sidebar integrado
- [ ] Equidad salarial: alertas disparidad por género en mismo cargo/banda (futuro)

## Fase 16: Amonestaciones y Medidas Disciplinarias [COMPLETADA]
### Block 16.1: Proceso Disciplinario [COMPLETADO]
- [x] Modelo TipoFalta: 15 tipos DS 003-97-TR (LEVE/GRAVE/MUY_GRAVE), base legal
- [x] Modelo MedidaDisciplinaria: personal, tipo_medida (VERBAL/ESCRITA/SUSPENSION/DESPIDO), tipo_falta FK, fecha_hechos, descripción, testigos, evidencias, carta preaviso, fecha_limite_descargo (6 días hábiles auto-calc), resolución, días_suspensión, fecha_cese, estado workflow (BORRADOR→NOTIFICADA→EN_DESCARGO→DESCARGO_RECIBIDO→RESUELTA)
- [x] Modelo Descargo: medida FK, texto, adjuntos, estado (PRESENTADO/EN_REVISION/ACEPTADO/RECHAZADO), presentado_a_tiempo property
- [x] Admin panel: medidas con stats, filtros, plazo descargo tracking
- [x] Detalle: notificar AJAX, registrar descargo, evaluar, resolver, historial previo, alerta escalamiento (3+ escritas en 12 meses)
- [x] Config: CRUD tipos de falta (modal AJAX)
- [x] Historial: vista por trabajador con resumen verbales/escritas/suspensiones
- [x] Seed: 15 tipos falta DS 003-97-TR Art. 25
- [x] Base legal: DS 003-97-TR art. 24-28, art. 31, Ley 27942, Ley 29783

## Fase 17: Encuestas y Clima Laboral [COMPLETADA]
### Block 17.1: Motor de Encuestas [COMPLETADO]
- [x] 4 modelos: Encuesta, PreguntaEncuesta, RespuestaEncuesta, ResultadoEncuesta
- [x] Encuesta: tipos CLIMA/PULSO/SATISFACCION/ENPS/SALIDA/ONBOARDING/CUSTOM, estados BORRADOR→PROGRAMADA→ACTIVA→CERRADA→ARCHIVADA
- [x] PreguntaEncuesta: tipos ESCALA_5/ESCALA_10/OPCION/SI_NO/TEXTO/MATRIZ, opciones JSONField, categorías dimensión
- [x] Anonimato real: FK personal nullable, guarda area_anonima/grupo_anonimo como metadata, captura IP
- [x] eNPS: cálculo automático (promotores - detractores / total * 100)
- [x] Resultados: puntajes por dimensión (categoría pregunta), distribución por pregunta
- [x] Portal: "Mis Encuestas" — pendientes y completadas, formulario dinámico por tipo pregunta
- [x] Admin: 11 vistas, 6 templates, 10 URL patterns
- [x] ConfiguracionSistema: mod_encuestas flag

## Fase 18: Integraciones Perú [PARCIAL]
### Block 18.1 Lite: Exportaciones SUNAT/AFP/Bancos [COMPLETADO — 2026-03-02]
- [x] App `integraciones/` — LogExportacion model (13 tipos, ESTADO choices), migración 0001
- [x] exportadores.py — 6 funciones: generar_t_registro_altas/bajas, generar_planilla_excel, generar_afp_net, generar_pago_banco, generar_essalud
- [x] views.py — panel + 6 vistas exportación + preview AJAX (JsonResponse con totals/aportes)
- [x] urls.py — 9 patrones URL bajo /integraciones/
- [x] Panel: KPIs (activos/AFP/ONP/banco), 6 cards exportación con Preview AJAX, historial tabla
- [x] JavaScript: período selector actualiza links dinámicamente, filtros AFP/banco
- [x] Sidebar: sección "Integraciones" → "Exportaciones SUNAT" (solo superuser)
- [x] Formatos: T-Registro pipe-delimitado SUNAT, AFP Net pipe-delimitado, planilla CSV/Excel, banco CSV Telecrédito, ESSALUD CSV
- [ ] **PLAME**: PDT PLAME (requiere cálculo nómina completa — Fase 20)
- [ ] **SCTR**: control de pólizas y vencimientos
- [ ] **Reloj biométrico**: ver Block 18.2

### Block 18.2: Reloj Biométrico
- [ ] Importación automática desde reloj (ya parcialmente implementado en asistencia)
- [ ] Soporte multi-marca: ZKTeco, Anviz, Suprema (formato configurable)
- [ ] API para recibir marcaciones en tiempo real (webhook del reloj)
- [ ] Reconciliación: marcación reloj vs marcación sistema → alertas discrepancias

## Fase 19: Calendario Laboral Compartido [COMPLETADA]
### Block 19.1: Calendario Visual [COMPLETADO]
- [x] 1 modelo: EventoCalendario (custom events, otros se leen dinámicamente)
- [x] Merge dinámico de 6 fuentes: vacaciones, permisos, feriados, cumpleaños, roster, eventos custom
- [x] Color-coded: vacaciones=#3b82f6, permisos=#f59e0b, feriados=#ef4444, cumpleaños=#22c55e, turnos=#8b5cf6
- [x] Calendario puro CSS Grid + vanilla JS (sin librería externa)
- [x] Navegación mes (prev/next/hoy), pills de eventos, detalle por día click
- [x] Filtros: chips por tipo (toggle on/off), dropdown por área
- [x] Export iCal (.ics) con VEVENT entries
- [x] Eventos custom: crear/eliminar AJAX
- [x] Portal: "Mi Calendario" — solo eventos personales del empleado
- [x] Sidebar: admin "Calendario Laboral" + portal "Mi Calendario"

## Fase 20: Nóminas [COMPLETADA — 2026-03-02]
**Base legal**: DL 728, DS 001-97-TR, Ley 27735 (gratificaciones), DL 650 (CTS)
### Block 20.1: Motor Cálculo Perú [COMPLETADO]
- [x] 4 modelos: ConceptoRemunerativo, PeriodoNomina, RegistroNomina, LineaNomina
- [x] engine.py: AFP (4 AFPs: Habitat/Integra/Prima/Profuturo, tasas 2026), ONP 13%, EsSalud 9%, IR 5ta escala progresiva (7 UIT deducción), HE 25/35/100%, asig. familiar 10% RMV
- [x] Provisiones: gratificación (1/6) + CTS (1/12), costo total empresa
- [x] generar_periodo(): bulk generation + recálculo idempotente
- [x] Seed: 24 conceptos remunerativos (7 ingresos + 4 no remun. + 2 provisiones + 8 descuentos + 3 aportes empleador)
- [x] 12 vistas: panel, crear período, detalle, generar, aprobar, exportar CSV (BOM UTF-8), registro detalle, editar, conceptos CRUD, mis recibos
- [x] Exportar CSV compatible Excel con todos los conceptos dinámicos
- [x] 7 templates: panel, periodo_form, periodo_detalle, registro_detalle, registro_editar, conceptos, mis_recibos
- [x] Sidebar: sección "Nóminas" (admin) + "Mis Recibos" (portal)
- [x] Migración 0001_initial aplicada. Django check: 0 issues.
- [x] Gratificaciones julio/diciembre con bonificación extraordinaria 9% (período GRATIFICACION) — engine completo
- [x] CTS mayo/noviembre (período CTS) — engine completo
- [ ] Liquidación al cese
- [ ] Integración contable

### Block 20.2: Plan de Plantilla + Flujo de Caja Avanzado [COMPLETADO — 2026-03-05]
- [x] Modelo PlanPlantilla: nombre, tipo (OBRA/EMPRESA), período proyección, estado BORRADOR→APROBADO→VIGENTE→CERRADO, notas, creado_por
- [x] Modelo LineaPlan: plan FK, cargo, tipo_trabajador (STAFF/RCO), n_personas, sueldo_base, cond_trabajo, alimentacion, viaticos, mes_inicio, mes_fin
- [x] Engine proyectar_desde_plan(plan, n_meses): proyecta cashflow desde líneas del plan (sin depender de Personal real)
- [x] flujo_caja_engine.py: modo PLAN (?plan=PK) vs REAL (sin param), n_meses = max(1, min(n_meses, 60))
- [x] viaticos_mensual incluido en engine (REAL y PLAN) y en chart_viaticos
- [x] 6 vistas Plan: planes_panel, plan_crear, plan_editar, plan_detalle, plan_aprobar, plan_cerrar
- [x] flujo_caja_panel: parámetro ?plan=PK activa modo PLAN con toggle REAL/PLAN en UI
- [x] Templates: planes_panel.html, plan_detalle.html con lineas AJAX, flujo_caja.html con selector período + toggle PLAN/REAL
- [x] Fix: fa-chart-gantt (FA PRO) → fa-chart-bar (FA 6.5.1 Free)

## Fase 21: Analytics & People Intelligence [COMPLETADA]
### Block 21.1: Dashboard Ejecutivo y KPIs [COMPLETADO]
- [x] 2 modelos: KPISnapshot, AlertaRRHH
- [x] KPISnapshot: snapshot mensual con headcount, rotación, asistencia, HE, vacaciones, capacitación, costos
- [x] AlertaRRHH: título, descripción, categoría (7 tipos), severidad (INFO/WARN/CRITICAL), estado workflow
- [x] Services: calcular_headcount, calcular_rotacion, calcular_asistencia, calcular_vacaciones, calcular_capacitacion, generar_snapshot, generar_alertas
- [x] Dashboard ejecutivo: 6 KPI cards, 4 gráficas Chart.js (distribución área, tendencia headcount, rotación mensual, HE), alertas
- [x] Headcount detallado: pirámide por área STAFF/RCO, distribución antigüedad (doughnut), barras horizontales
- [x] Snapshots: tabla histórica 24 meses, generar mes actual con 1 click
- [x] Alertas: lista filtrable (activas/resueltas/todas), resolver con notas, generar automáticas
- [x] API JSON: /analytics/api/kpi/ y /analytics/api/tendencias/ para gráficos AJAX
- [x] Management command: `generar_kpi --anio 2026 --mes 3 --alertas`
- [x] API REST: 2 ViewSets (KPISnapshot, AlertaRRHH) integrados en /api/v1/analytics/
- [x] Sidebar: sección Analytics con 4 links (Dashboard, Headcount, Snapshots, Alertas)
- [ ] Predicción de rotación con ML/Ollama (futuro)
- [ ] Succession planning (futuro)
- [ ] People analytics avanzado (futuro)

---

## Pendientes activos (al 2026-03-05)

### Plan de Plantilla — Block 20.3 (próxima sesión)
- [ ] **Pestaña Presupuesto en plan_detalle**: tab adicional con resumen financiero por mes (costo total, por cargo, por área)
- [ ] **Edición inline de líneas**: editar área, fecha inicio/fin, cargo directamente desde plan_detalle sin modal separado
- [ ] **Import Excel para LineaPlan**: subir plantilla Excel con columnas cargo/tipo/n_personas/sueldo/cond_trabajo/alimentacion/viaticos/mes_inicio/mes_fin
- [ ] **Export Excel del plan**: descargar el plan completo como Excel (todas las líneas + proyección cashflow mes a mes)
- [ ] **Plantilla Excel descargable**: botón "Descargar plantilla" para rellenar e importar

### INFRA
- [ ] **INFRA.1 Multi-empresa** — ALTA PRIORIDAD. Si Personal no tiene empresa_id pronto, migrar después rompe toda la data
- [ ] **INFRA.3 Permisos Granulares** — Modelo PermisoModulo creado (lite), pero no por objeto/área/sede
- [ ] **INFRA.4 Workflow Engine Genérico** — pendiente (onboarding/vacaciones/HE actualmente tienen workflow hardcodeado)

### Módulos
- [ ] **Nóminas**: Liquidación al cese, integración contable
- [ ] **Reloj biométrico** (Block 18.2): importación automática ZKTeco, webhook marcaciones tiempo real
- [ ] **PLAME/PDT** — requiere nómina completa (ya implementada), pendiente generar PDT
- [ ] **Disparadores automáticos comunicaciones** — cumpleaños, aniversarios, período de prueba (requiere cron/celery)
- [ ] **Prueba del sistema en producción** — push a Render + migración PostgreSQL

---

## Estructura actual del proyecto
```
D:\Harmoni\
├── core/                    ✅ constants, mixins, templatetags, audit
├── personal/                ✅ views/ split en 7 módulos
├── evaluaciones/            ✅ NUEVO — 360°, 9-Box, PDI, competencias
├── encuestas/               ✅ NUEVO — clima laboral, eNPS, pulsos
├── salarios/                ✅ NUEVO — bandas, historial, simulaciones
├── onboarding/              ✅ NUEVO — onboarding + offboarding, plantillas
├── calendario/              ✅ NUEVO — calendario visual, iCal export
├── reclutamiento/           ✅ NUEVO — vacantes, pipeline kanban, portal empleo
├── comunicaciones/          ✅ NUEVO — motor notificaciones, comunicados masivos, SMTP
├── analytics/               ✅ NUEVO — dashboard ejecutivo, KPIs, alertas, tendencias
├── asistencia/              ✅ views/ split en 10 módulos (label='tareo')
├── portal/                  ✅ autoservicio trabajador
├── cierre/                  ✅ wizard 7 pasos
├── documentos/              ✅ legajo + constancias + boletas de pago
├── prestamos/               ✅ préstamos y adelantos
├── viaticos/                ✅ viáticos CDT
├── vacaciones/              ✅ NUEVO — vacaciones, permisos, saldos
├── capacitaciones/          ✅ NUEVO — LMS ligero, certificaciones
├── disciplinaria/           ✅ NUEVO — proceso disciplinario legal
├── config/                  ✅ settings, urls
├── templates/               ✅ 50+ templates
├── static/css/harmoni.css   ✅ design system
└── brand/                   ✅ identidad visual
```

## Notas de sesión
- 2026-03-01: Fase 0 completa. Limpieza (~40 archivos), rename tareo→asistencia, core/ app, HE 100% fix, splits de views. Django check: 0 issues.
- 2026-03-01 (cont.): Block 0.6 — UI ERP profesional completa. Login, dashboard, sidebar oscuro, context processor global, harmoni.css design system, password change.
- 2026-03-01 (cont.): Block 0.7 — Identidad de marca definida. Paleta Teal (#0d2b27/#0f766e/#5eead4). Logo: El Hexágono Vivo (SVG inline). Narrativa "Harmoni — siempre hay algo más que podemos hacer".
- 2026-03-01 (cont.): Fase 1 Portal + Block 2.1 Vista Unificada + Block 2.2 KPI Dashboard con Charts.js teal. Fix crítico: floatformat con locale Spanish usa comma decimal, rompe JS — usar stringformat:"f" para vars JS.
- 2026-03-01 (cont.): Fase 3 Cierre Mensual completa. Fase 1.3 Organigrama + Directorio completa. Fix bugs engine.py: estado='Activo', personal__grupo_tareo='RCO'.
- 2026-03-01 (cont.): Block 5.1 ConfiguracionSistema IA (Ollama only, migraciones 0004+0005). Block 5.2 Feriados CRUD (12 feriados Perú cargados). Block 5.3 Homologaciones CRUD (modal completo con 11 campos). Block 5.4 Papeletas de Compensación COMPLETO (modelo+processor+vista dedicada). Nuevos requisitos capturados: Block 5.5 Control HE, Fase 6 Portal ampliado (justificaciones, boletas digitales DS 009-2011-TR, documentación laboral).
- 2026-03-01 (cont.): Block 5.5 Control HE COMPLETO. Block 5.6 Justificaciones COMPLETO. Block 5.7 Papeletas Unificadas COMPLETO — migración 0009, processor actualizado, admin CRUD+aprobar, portal "Mis Papeletas" (solicitar/anular), reporte post-cierre rezagos (faltas/papeletas/HE fuera del corte planilla).
- 2026-03-02: Block 6.2 Boletas de Pago Digital COMPLETO (upload-only desde software externo, constancia lectura DS 009-2011-TR). Fase 10 Vacaciones y Permisos COMPLETA (5 modelos, 12 tipos Perú seed, admin+portal, aprobar/rechazar AJAX). Fase 13 Capacitaciones COMPLETA (5 modelos, categorías, requerimientos, incumplimientos, certificaciones, portal). Fase 16 Disciplinaria COMPLETA (3 modelos, 15 tipos falta DS 003-97-TR seed, workflow legal completo, descargos, historial). 4 nuevas apps: vacaciones, capacitaciones, disciplinaria + extensión documentos. 22 templates nuevos. Migraciones aplicadas. Django check: 0 issues.
- 2026-03-02 (cont.): Fase 12 Evaluaciones COMPLETA (9 modelos, 360°, 9-Box Grid, PDI, 16 competencias seed, 10 templates). Fase 17 Encuestas COMPLETA (4 modelos, eNPS, dimensiones, anonimato real, 6 templates). Fase 15 Estructura Salarial COMPLETA (4 modelos, bandas compa-ratio, simulador masivo, historial, 6 templates). 3 nuevas apps: evaluaciones, encuestas, salarios. mod_evaluaciones/encuestas/salarios flags. Django check: 0 issues.
- 2026-03-02 (cont.): Fase 7 Onboarding COMPLETA (8 modelos, plantillas+pasos config, checklist AJAX, offboarding con motivo_cese, seed 14 pasos, 10 templates, portal). Fase 14 Préstamos ya existía completa (3 modelos, cuotas, auto-cierre). Fase 19 Calendario COMPLETA (CSS Grid puro, merge 6 fuentes, iCal export, portal, pills+detalle). 2 nuevas apps: onboarding, calendario. Django check: 0 issues.
- 2026-03-02 (cont.): Fase 9 Reclutamiento COMPLETA (5 modelos, pipeline kanban, 8 etapas seed, portal empleo público standalone, entrevistas+notas, 8 templates). Fase 8 Comunicaciones COMPLETA (6 modelos, NotificacionService reusable, ConfiguracionSMTP singleton, ComunicadoMasivo con confirmacion lectura, 8 plantillas seed, 9 templates). 2 nuevas apps: reclutamiento, comunicaciones. Django check: 0 issues.
- 2026-03-02 (cont.): INFRA API REST COMPLETA — 171 endpoints bajo /api/v1/. JWT auth (SimpleJWT), Swagger/ReDoc (drf-spectacular), 12 módulos con api_serializers+api_views+api_urls. Central router en core/api_urls.py. Health + token endpoints. Django check: 0 issues.
- 2026-03-02 (cont.): Fase 21 Analytics COMPLETA — 2 modelos (KPISnapshot, AlertaRRHH), services.py con 6 calculadores, dashboard ejecutivo con 4 gráficas Chart.js, headcount detallado, snapshots mensuales, alertas con workflow, management command generar_kpi. 19 Harmoni apps, 95 modelos. Django check: 0 issues.
- 2026-03-02 (cont.): MEJORAS Áreas/SubÁreas — vista detalle área (KPIs headcount STAFF/RCO, subareas, empleados top 50), toggle activa/inactiva para áreas y subareas, delete con guard (solo si 0 personal), paginación en listas, filtro activas/todas, contadores personal activo (Q filter estado='Activo'), breadcrumb. Nuevas rutas: area_detail, area_toggle, area_delete, subarea_toggle, subarea_delete. subarea_create/update ahora requiere is_superuser + redirige a area_detail. Django check: 0 issues.
- 2026-03-02 (cont.): Block 5.3 Preferencias COMPLETO — PreferenciaUsuario model (core/models.py), migración 0002, vistas GET/POST + API AJAX, template /sistema/preferencias/ con Interface/Notificaciones/Cuenta, AJAX auto-save switches. Management command alertas_diarias COMPLETO (--dry-run, --solo-contratos, --solo-vacaciones). Block 7.3 Contratos COMPLETO (13 modalidades, período de prueba calculado, Panel/Lista/Editar, alertas analytics, personal_detail con badge). Fase 6.3 Docs. Laborales: fix heredoc double-quotes en 5 templates, sidebar links admin+portal. Fase 18 Lite COMPLETA — 6 exportadores (T-Registro altas/bajas, planilla CSV, AFP Net, bancos, ESSALUD), panel con AJAX preview, LogExportacion model, sidebar Integraciones. Área/SubÁrea v2 COMPLETA — campo `codigo` + `jefe_area` FK (migración 0014), area_list v2 con S/R badges headcount + jefe column, area_detail v2 con 6 KPIs + 3 analytics cards (categoría/pensión/contrato), subarea_detail NEW view+template, subarea_list links a detalle, area_form.html manual rendering (fix Python 3.14 crispy context.__copy__ bug). Django check: 0 issues.
- 2026-03-02 (cont.): SESIÓN RECUPERADA TRAS CAÍDA SERVIDOR. Block 12.2 OKRs COMPLETO (3 modelos: ObjetivoClave/ResultadoClave/CheckInOKR, cascada empresa→área→individual, check-ins históricos, 4 templates, views_okr.py, API REST 3 ViewSets, migración 0002, sidebar admin+portal). Seed documentos COMPLETO (command seed_documentos: 7 categorías + 32 tipos predefinidos Perú). Progress.md actualizado: Block 6.3, Fase 11, INFRA.2 marcados como COMPLETADOS. Django check: 0 issues. Total modelos: 98.
- 2026-03-02 (cont.2): Fase 20 Nóminas COMPLETA (4 modelos, engine.py AFP/ONP/EsSalud/IR5ta/gratif/CTS, 24 conceptos seed, 12 vistas, 7 templates, exportar CSV Excel, portal Mis Recibos, sidebar admin+portal). INFRA.3 Permisos Granulares lite COMPLETA (PermisoModulo model, core/permissions.py con decorador requiere_permiso/tiene_permiso/get_permisos_usuario, panel UI matriz módulo×acciones, migración 0003, sidebar Sistema). Notificaciones in-app COMPLETA (views_notif.py: 3 endpoints AJAX json/marcar/marcar-todas, badge counter en header, dropdown últimas 8 notifs, polling 60s, mark-as-read). Home dashboard world-class (6 KPIs, nómina card dark, alertas contratos, quick actions 14 acciones, saludo por hora). Búsqueda global expandida (+vacaciones, +OKRs, +nóminas, 18 resultados). Django check: 0 issues. Total modelos: 99 (PermisoModulo).
- 2026-03-02 (cont.4): Ollama IA COMPLETO — ai_service.py (OllamaService: test_connection/generate/chat/mapear_columnas/resumir_texto/clasificar_falta + get_service/ia_disponible/mapear_columnas_ia), s10_importer.py _mapear_con_ia() reescrito para usar Ollama (era Anthropic API — violaba arquitectura), ia_test_connection view + URL (POST devuelve {ok, modelos, modelo_activo, error}), configuracion.html tab IA rediseñado (Probar conexión AJAX, status card verde/rojo, chips de modelos clickables con info talla, aviso modelo no instalado con ollama pull command). Fase 4 Import Inteligente COMPLETO — importar.html rediseñado como Import Hub (4 cards: Reloj inline+drag&drop, Synkro, SUNAT, S10 con Ollama badge), importar_view actualiza contexto con stats_synkro/stats_sunat/stats_s10/total_staff/total_rco/ia_disponible, importar_s10.html rediseño completo (breadcrumb, Ollama status badge dinámico, historia S10 5 últimas, columnas detectadas con col-chip, otros importadores links). importar_s10_view mejorado: pasa ia_disponible+ia_modelo al template, POST redirecta al mismo formulario (no al dashboard) para mostrar resultado. Viáticos MEJORADO — gasto_revisar AJAX (APROBADO/RECHAZADO/OBSERVADO con motivo requerido, recalcula monto_rendido), gasto_eliminar AJAX (solo PENDIENTE), viatico_anular (estado→CANCELADO), viaticos_exportar CSV (respeta filtros del panel), detalle.html: columna Acciones con botones aprobar/rechazar/observar/eliminar por gasto, botón Anular en sidebar, tfoot colspan ajustado, JS revisarGasto/pedirMotivo/eliminarGasto, panel.html: botón Exportar CSV. Nóminas Gratificaciones+CTS — calcular_gratificacion() (Ley 27735 + Ley 29351 bonif 9%, proporcional 1-6 meses, descuentos AFP/ONP, IR inafecto), calcular_cts() (DL 650, base=sueldo+asig_fam+1/6 gratif, proporcional 1-6 meses, inafecto pensiones+renta), generar_periodo() dispatch por tipo, 3 conceptos seed nuevos (gratificacion, bonif-extraordinaria, cts-semestral). periodo_detalle.html: alert informativo legal para GRATIFICACION/CTS, columna Días→Meses para esos tipos. Django check: 0 issues.
- 2026-03-03: MEJORA IA MASIVA — Block 4.1+4.2. Ver detalle arriba en Block 4.1 y Block 4.2. Resumen: 42 campos contexto, 13 tipos chart (áreas/tipo/antigüedad/rotación/headcount/asistencia_semanal/HE/vacaciones/capacitaciones/tipo_contrato/género/edad/pensión), 20+ patrones fallback, 4 niveles cache, widget v2 con exportar .md, suggestion chips contextuales, 12 quick actions, toast notifications, per-bar colors, leyendas dinámicas, icons dinámicos. Testing visual completo: todos los gráficos y features verificados en browser. Django check: 0 issues.
- 2026-03-05: Plan de Plantilla + Flujo de Caja PLAN/REAL — Block 20.2 COMPLETO (2 modelos: PlanPlantilla+LineaPlan, engine proyectar_desde_plan, modo REAL/PLAN toggle, viaticos en engine, planes_panel+plan_detalle templates, 6 vistas, fix fa-chart-gantt→fa-chart-bar). FIX CRÍTICO Python 3.14 + crispy-forms — personal_form/subarea_form/roster_form reescritos con Bootstrap manual (error: context.__copy__() en Python 3.14 rompe crispy Layout en rendering). personal/forms.py: Layout/FormHelper removidos de PersonalForm/SubAreaForm/RosterForm, Bootstrap clases directamente en widgets. Imports limpiados (Row/Column/Div/Layout removidos). personal_create + personal_update verificados → HTTP 200. Commits: feat(nominas) Plan Plantilla + fix(planes) fa-icon + fix(personal) crispy-forms Python 3.14.
- 2026-03-02 (cont.3): UX Cese empleado COMPLETO — personal_form.html: JS show/hide motivo_cese al cambiar estado, auto-fill fecha_cese con hoy; personal_detail.html: alerta banner rojo para cesados con fecha+motivo; personal_list.html: row table-secondary, nombre tachado, badge rojo, tooltip Bootstrap con motivo+fecha. Identidad Visual COMPLETA — ConfiguracionSistema: 10 nuevos campos (empresa_direccion, empresa_telefono, empresa_email, empresa_web, logo ImageField, membrete_color, membrete_mostrar, firma_nombre, firma_cargo, firma_imagen), propiedades logo_base64/firma_base64 para xhtml2pdf, migración tareo.0012. documentos/services.py: reescritura completa con _build_membrete_html() (tabla para xhtml2pdf), _build_firma_html(), membrete automático en todos los PDFs. configuracion.html: tab "Identidad Visual" con logo upload+preview+delete, datos contacto, color picker membrete con preview live, firma upload+preview. configuracion_view: manejo enctype multipart/form-data + logic upload/delete imágenes. requirements.txt: Pillow + xhtml2pdf. Filtros STAFF/RCO en personal_list COMPLETO — grupo_tareo filter, total_activos/staff/rco counters, badges clickables, columna Grupo, limpiar filtros, paginación preserva params. plantilla_form.html REDISEÑO COMPLETO — layout 2 columnas (col-lg-8 form + col-lg-4 panel variables), 48 var-chips en 4 grupos (Trabajador/Fechas/Empresa/AFP-Banco), inserción al cursor con toast, verbatim blocks para onclick attrs, botón Ejemplo. sidebar base.html: empresa_nombre dinámico desde harmoni_config. seed_constancias NUEVO (5 plantillas: Constancia Trabajo/Ingresos/Certificado Trabajo/Cese/Carta Presentación). Constancias portal COMPLETO — ConstanciaGenerada model (migración documentos.0006), portal views mis_constancias + portal_generar_constancia, historial con ADMIN/PORTAL badge, registro automático en constancia_generar (admin) + portal, sidebar "Mis Constancias", panel admin actualizado con historial 30 últimas + stats por plantilla, personal_detail dropdown "Generar Constancia" con plantillas disponibles, portal_home acciones rápidas + Mis Boletas. Django check: 0 issues.
