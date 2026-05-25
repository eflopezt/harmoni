# Guía de Presentación — Visual Handoff
**Para: Claude Design (preparar capturas + diapositivas) · Mayo 2026**

> Este documento es para una IA de diseño / un diseñador que prepara las **capturas y el material visual** que respaldan la demo de Harmoni. Cada sección lista la pantalla, la URL, qué capturar, qué resaltar, y la frase gancho que la acompaña en la presentación oral.

---

## 0. Identidad visual — usar siempre

| Elemento | Valor |
|----------|-------|
| **Tipografía UI** | Inter (400 / 500 / 600) |
| **Tipografía numérica** | JetBrains Mono con `font-variant-numeric: tabular-nums` |
| **Color de marca primario** | Teal `#0f766e` |
| **Color secundario** | Slate `#475569` |
| **Fondo neutro** | `#f8fafc` (claro) / `#0b1120` (oscuro) |
| **Borde sutil** | `#e2e8f0` |
| **Radio de tarjetas** | 10 px (8 px para botones, 12 px para drawer) |
| **Sombras** | `0 1px 2px rgba(15,23,42,.06), 0 1px 1px rgba(15,23,42,.04)` |
| **Logo único** | `static/images/brand/png/harmoni-favicon-180.png` (cuadrado 180×180), nunca usar `harmoni-mark-128.png` en contenedor cuadrado — distorsiona. |
| **Estilo general** | "Cockpit V2" — inspirado en Linear / Notion |

---

## 1. Capturas requeridas (en orden de la presentación)

Cada captura debe ser **PNG 1920×1080** (full HD), con el navegador en modo limpio (sin extensiones visibles), zoom 100 %, sin scrollbars custom.

### 1.1 Landing pública
- **URL**: `https://demo.harmoni.pe/`
- **Resaltar**: hero con frase "ERP de RRHH para Perú", CTA "Probar demo", footer con links.
- **Cuidado con**: que no aparezca el dev toolbar de Django (debe estar en producción).
- **Slide**: portada antes de entrar al sistema.
- **Frase gancho**: *"Esto es lo que ve un cliente nuevo. Limpio, claro, peruano."*

### 1.2 Login
- **URL**: `https://demo.harmoni.pe/login/`
- **Resaltar**: logo Harmoni centrado (favicon-180 con border-radius 10 px), formulario simple, link "Recuperar contraseña".
- **Cuidado con**: el logo debe estar cuadrado, no rectangular.
- **Slide**: transición a "Entremos al sistema".

### 1.3 Dashboard "Centro de Comando"
- **URL**: `https://demo.harmoni.pe/dashboard/`
- **Resaltar**:
  - KPIs en vivo (headcount, ausentismo, planilla del mes).
  - Tarjetas de alertas (contratos por vencer, vacaciones acumuladas, papeletas pendientes).
  - Atajos "Lo que hay que hacer hoy".
  - Gráficos compactos de tendencia (últimos 6 meses).
- **Slide**: "El sistema te dice qué hacer".

### 1.4 Módulo Personal — vista lista
- **URL**: `/personal/`
- **Resaltar**:
  - Tabla densa, una línea por persona.
  - Filtros chip arriba (Estado, Grupo, Sede, Área).
  - Tipografía monoespaciada en columnas numéricas (DNI, sueldo).
  - Botón "Nuevo empleado" en topbar.
- **Slide**: "Gestión de 200+ personas en una sola pantalla."

### 1.5 Módulo Personal — drawer abierto
- **Acción**: click sobre una fila de la lista anterior.
- **Resaltar**:
  - Drawer lateral 540 px que **no tapa** la lista (la lista se ve a la izquierda).
  - Las 4 tabs visibles (Datos, Contrato, Asistencia, Histórico).
  - Botón cerrar en la esquina + Esc.
- **Slide**: "Sin perder contexto — la lista sigue ahí."

### 1.6 Módulo Personal — bulk bar activa
- **Acción**: marca 3 checkboxes de la lista.
- **Resaltar**:
  - Barra inferior aparece con: "3 seleccionados — Cambiar estado · Asignar área · Exportar · Cesar masivo".
  - Botón "Deseleccionar todos" a la derecha.
- **Slide**: "Operaciones masivas sin abrir 10 modales."

### 1.7 Módulo Personal — inline edit
- **Acción**: doble-click sobre la columna "Cargo" de una fila.
- **Resaltar**: input aparece dentro de la fila, cursor adentro, Enter confirma.
- **Slide**: "Editas como en Excel, sin Excel."

### 1.8 Command Palette ⌘K
- **Acción**: Ctrl + K en cualquier vista.
- **Resaltar**:
  - Overlay sobre el contenido con `backdrop-filter: blur(8px)`.
  - Input con placeholder "Buscar empleados, módulos, acciones…".
  - 3 grupos visibles: Empleados, Módulos, Acciones recientes.
  - Cada resultado con su atajo de teclado a la derecha.
- **Slide**: "Como Notion. Como Linear."

### 1.9 Módulo Asistencia — matriz mensual
- **URL**: `/asistencia/matriz/?mes=5&anio=2026`
- **Resaltar**:
  - Columnas: trabajadores. Filas: días. O viceversa.
  - Colores por estado (presente, falta, permiso, vacaciones, feriado).
  - Sticky header y sticky primera columna (nombre).
- **Slide**: "El mes entero de un golpe de vista."

### 1.10 Módulo Asistencia — dashboard
- **URL**: `/asistencia/dashboard/`
- **Resaltar**: tiles con totales (presentes, faltas, papeletas pendientes), botón "Sync Synkro".
- **Slide**: "Un clic y tu marcador biométrico está sincronizado."

### 1.11 Módulo Nóminas — panel
- **URL**: `/nominas/`
- **Resaltar**: lista de períodos con estado (Borrador, Calculado, Aprobado, Cerrado), KPIs comparativos del mes vs. mes anterior.

### 1.12 Módulo Nóminas — Wizard
- **URL**: `/nominas/wizard/`
- **Resaltar**: 4 pasos progresivos (Período → Registros → Cálculo → Aprobación).
- **Slide**: "12 minutos. No es exageración."

### 1.13 Módulo Nóminas — Boleta electrónica
- **URL**: cualquier `/nominas/boleta-verificacion/<id>/`
- **Resaltar**:
  - Boleta DS 009-2011-TR formato oficial.
  - Conceptos remunerativos, descuentos, neto a pagar.
  - Firma electrónica del trabajador (acuse de recibo).
- **Slide**: "Boleta legal, no PDF improvisado."

### 1.14 Agente IA Harmoni (widget) ⭐ MOMENTO WOW
- **Acción**: abrir widget IA en cualquier vista del ERP.
- **Resaltar**:
  - Conversación: usuario tipea *"el mes pasado olvidé subir S/200 a todos"*.
  - Respuesta de la IA: cita norma (D.S. 003-97-TR), propone reintegro + proporcional, muestra tabla de afectados.
  - Botones: **[Aprobar reintegro]** **[Ver detalle]** **[Descartar]**.
- **Slide**: "El asistente actúa, no solo conversa."

### 1.15 Vacaciones — calendario + solicitud
- **URL**: `/vacaciones/`
- **Resaltar**: calendario con bloques por trabajador, modal de solicitud, workflow de aprobación con timeline.

### 1.16 Portal del empleado ⭐ DIFERENCIADOR
- **URL**: `/portal/` (logueado como trabajador)
- **Resaltar**:
  - Tarjetas: "Mis recibos", "Mi asistencia", "Solicitar vacaciones", "Mis datos".
  - Diseño limpio, mobile-first.
- **Slide**: "El trabajador resuelve solo. RRHH deja de ser el cuello de botella."

### 1.17 Analytics — People Intelligence
- **URL**: `/analytics/`
- **Resaltar**: predicción de rotación, salud por sede, pulse semanal.
- **Slide**: "Esto no lo tiene ningún ERP de RRHH peruano hoy."

### 1.18 Reclutamiento — Pipeline Kanban
- **URL**: `/reclutamiento/pipeline/`
- **Resaltar**: kanban con etapas (Postulado, Screening, Entrevista, Oferta, Contratado), drag-and-drop, contador por columna.
- **Slide**: "Cero Excel para el reclutador."

### 1.19 Audit Log
- **URL**: `/configuracion/audit/`
- **Resaltar**: tabla de eventos (usuario, IP, modelo, acción, diff campo a campo), filtros por fecha y modelo.
- **Slide**: "Si alguien cambia algo, queda registro."

### 1.20 Mobile preview — sidebar off-canvas
- **Resolución**: 375×812 (iPhone)
- **Resaltar**: sidebar abierto sobre el contenido con backdrop, tap targets ≥ 44 px, drawer responsive.
- **Slide**: "Funciona en el celular de tu jefe."

---

## 2. Estructura de la presentación (slides)

| # | Slide | Captura | Tiempo |
|---|-------|---------|--------|
| 1 | Portada — "Harmoni · ERP de RRHH para Perú" | Logo grande sobre fondo blanco | 30s |
| 2 | Problema — "Tu equipo gasta 4 horas cerrando planilla" | Foto stock RRHH agotada | 30s |
| 3 | Solución — "Harmoni: 12 minutos, ley peruana, audit log" | Captura 1.1 (landing) | 30s |
| 4 | Demo en vivo — entrada | Capturas 1.2 + 1.3 | 2 min |
| 5 | Personal — drawer, bulk, inline | Capturas 1.4–1.7 | 3 min |
| 6 | Command Palette | Captura 1.8 | 1 min |
| 7 | Asistencia | Capturas 1.9 + 1.10 | 3 min |
| 8 | Nóminas | Capturas 1.11–1.13 | 4 min |
| 9 | Agente IA | Captura 1.14 ⭐ | 3 min |
| 10 | Vacaciones | Captura 1.15 | 1 min |
| 11 | Portal del empleado | Captura 1.16 | 2 min |
| 12 | Analytics | Captura 1.17 | 2 min |
| 13 | Reclutamiento | Captura 1.18 | 1 min |
| 14 | Audit log + compliance | Captura 1.19 | 2 min |
| 15 | Mobile | Captura 1.20 | 1 min |
| 16 | Confiabilidad — tests, backup, Sentry | Tabla de números | 1 min |
| 17 | Cierre + Q&A | Captura del centro de comando | abierto |

---

## 3. Elementos a evitar en las capturas

- ❌ Pop-ups del navegador (notificaciones, "guardar contraseña").
- ❌ Toolbar del Django Debug Toolbar.
- ❌ Datos reales del Consorcio Stiler (proteger PII).
- ❌ URLs de localhost o de IP — usar siempre `demo.harmoni.pe`.
- ❌ Logo mark-128 rectangular — usar siempre favicon-180 cuadrado.
- ❌ Texto fantasma de comentarios `{# #}` multilínea (ya están todos arreglados, pero verificar).
- ❌ Tablas con scroll lateral visible — recortar o screenshot del estado scrolled.

---

## 4. Lo que nos hace superiores — usar como anotaciones en las slides

| Competidor típico | Harmoni |
|-------------------|---------|
| Sistema importado, español neutro | **Hecho en Perú, normativa peruana adentro** |
| Cierre planilla 2–4 horas con Excel paralelo | **12 minutos en wizard** |
| Asistente que conversa | **Agente IA que actúa con tool-use real** |
| Sin portal del empleado | **Portal con auto-servicio** |
| Boleta PDF improvisada | **DS 009-2011-TR conforme con firma electrónica** |
| Sin audit log | **AuditEntry en 5 modelos críticos con diff campo a campo** |
| Sin backup automático | **pg_dump diario 03:30 + retención 30 días** |
| Sin tests | **1,669 tests, 91 % cobertura en motor de planilla** |
| Diseño anticuado tipo SAP | **Cockpit V2 — Linear / Notion-style** |
| Solo desktop | **Mobile UX responsive con drawer off-canvas** |

---

## 5. Demos en vivo — preparación

Antes de la presentación, validar:

- [ ] `demo.harmoni.pe` responde en < 1 s.
- [ ] Login con `demo` / `demo123` funciona.
- [ ] Drawer 540 px abre/cierra sin saltos.
- [ ] ⌘K abre sobre cualquier vista.
- [ ] El widget IA tiene la API key configurada (no caer en "Error de conexión").
- [ ] Sync Synkro tiene mock o fixture (no llamar a producción del cliente).
- [ ] Logo favicon-180 cargado en cabecera y login (no mark-128).
- [ ] Centro de Comando tiene datos del mes actual (no quedar vacío).
- [ ] Algún período de nómina en estado APROBADO para mostrar boleta.
- [ ] Audit log con al menos 10 entradas recientes.

---

## 6. Plan B si algo falla en vivo

| Falla | Plan B |
|-------|--------|
| Demo no responde | Cambiar a Consorcio Stiler (`harmoni.pe`) — mostrar producción real. |
| Widget IA da error | Mostrar captura grabada del flujo de reintegro. |
| Sync Synkro no devuelve | Mostrar logs históricos del último sync exitoso. |
| Sin internet | Tener video pregrabado de 5 min del recorrido completo. |
| Sentry alerta en vivo | "Ven, el sistema de monitoreo es tan estricto que reportan hasta los warnings." |

---

## 7. Para Claude Design — output esperado

Cuando recibas este documento, generar:

1. **20 capturas PNG 1920×1080** en `presentacion/capturas/` (numeradas 01-landing.png … 20-mobile.png).
2. **Slides PPTX o Keynote** con la estructura de la sección 2.
3. **Resumen PDF de 1 página** con los 10 puntos diferenciadores de la sección 4 + tarjeta de bolsillo de números clave.
4. **Versión mobile** del resumen para WhatsApp follow-up.

Mantener consistencia visual con la identidad de la sección 0.
