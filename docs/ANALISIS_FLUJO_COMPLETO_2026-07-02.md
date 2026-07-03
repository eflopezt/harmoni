# Harmoni — Análisis del flujo completo de trabajo
**Fecha:** 2026-07-02 · **Alcance:** requisición → reclutamiento → onboarding → operación (asistencia, roster, vacaciones, nómina) → offboarding · 27 apps, ~823 URLs, 171 items de menú

---

## 1. El flujo end-to-end (como está hoy)

### Fase 1 — Requisición de personal
`Reclutamiento > Vacantes` · `reclutamiento/views_requisicion.py`

1. Jefe de área/RRHH crea `Vacante` (estado BORRADOR) con justificación.
2. "Solicitar aprobación" → POR_APROBAR.
3. Aprobador aprueba o rechaza. **Al aprobar, el estado vuelve a BORRADOR** (solo queda `aprobada_por` + `fecha_aprobacion` como rastro).
4. Publicación multi-canal: portal propio, Computrabajo, Bumeran, LinkedIn, Telegram, WhatsApp (`integraciones/LogPublicacionVacante`).
5. PUBLICADA → EN_PROCESO → CUBIERTA (manual) / CANCELADA.

La aprobación es **aditiva, no bloqueante**: una vacante puede publicarse sin aprobar.

### Fase 2 — Reclutamiento
`reclutamiento/` (46 URLs, ~31 pantallas)

- Entradas de candidatos: portal público, alta manual, **CV Express** (parser PyMuPDF/pdfplumber/docx + LLM opcional + score 0-100), bulk import XLSX.
- Pipeline kanban por `EtapaPipeline` configurable, con tags, bulk actions, banco de talento (rescate de descartados), comparador, entrevistas con resultado y calificación.
- `contratar_candidato`: transacción atómica que crea `Personal` (estado Activo), vincula la postulación (CONTRATADA), mueve a etapa "contratado" **solo si existe en el seed**, y auto-crea `ProcesoOnboarding`.

### Fase 3 — Onboarding
`onboarding/` (24 URLs)

- `PlantillaOnboarding` por grupo (STAFF/RCO) y área; pasos con tipo (tarea/documento/capacitación/notificación/aprobación), responsable (RRHH/JEFE/TI/TRABAJADOR) y plazo en días desde el ingreso.
- `ProcesoOnboarding` con % de avance, pasos vencidos en rojo, notificación al jefe al 100%.
- Checklist Gastronomía 30/60/90 paralelo (BPM/HACCP, evaluaciones).
- El empleado ve su proceso en el Portal (`/mi-portal/mi-onboarding`).

### Fase 4 — Operación diaria
- **Roster** (`personal/`, 25 URLs): matriz persona×día con códigos T/TR/DL/DLA/VAC/F/DM; días libres ganados por régimen (ej. 21×7 → factor 3); workflow de aprobación de cambios; grid drag-drop para gastronomía.
- **Asistencia** (`asistencia/`, 110 URLs): importación biométrico/Synkro → `RegistroTareo` diario → papeletas (override) → cálculo HE 25/35/100 → Banco de Horas (STAFF) o pago vía S10 (RCO). Cruce contra SUNAT/S10 y contra Roster (`CruceTareoRoster`).
- **Vacaciones** (`vacaciones/`, 26 URLs): `SaldoVacacional` 30 días/año (DL 713), solicitudes con lock anti-race, venta de vacaciones (máx 15), 12 tipos de permiso legales.
- **Dinero**: préstamos con cronograma francés **integrados automáticamente al engine de nómina**; descuentos de planilla (embargos, pensión, daños) **manuales**; viáticos con rendición y conciliación **aislados de nómina**.
- **Satélites**: evaluaciones (360°, 9-box, OKRs), capacitaciones (LMS + certificados), disciplinaria (DS 003-97-TR, cartas PDF), encuestas (eNPS, pulse), comunicaciones (motor central de notificaciones multi-canal), analytics (KPIs, attrition, IA).

### Fase 5 — Nómina mensual (ciclo 21 → 20)
`nominas/` (114 URLs) + `cierre/` (11 URLs)

1. Día 21: cierre de asistencia (revisar SS, justificaciones, banco de horas).
2. Crear `PeriodoNomina` → engine calcula con **snapshot legal congelado** (RMV, UIT, tasas AFP) — excelente para auditoría.
3. Consolida automáticamente: tareo (HE, faltas), cuotas de préstamo del mes, conceptos manuales (Excel→JSON).
4. Detección de anomalías → revisión → APROBADO.
5. Cierre formal: wizard de 7 pasos validadores (importaciones, DNI, SS, banco, **S10 = stub sin implementar**, reporte, bloqueo).
6. Emisión de boletas (portal + acuse DS 009-2011-TR + verificador QR), PLAME, T-Registro, archivo banco.

### Fase 6 — Offboarding y cese
- **Dos flujos paralelos**: `dar-baja` rápido (POST directo) y wizard de 3 pasos con preview de liquidación. Ambos disparan el mismo signal.
- Signal `_handle_cese`: notifica admins, genera constancia PDF, email al empleado, auto-crea `ProcesoOffboarding` y `LiquidacionLaboral` (BORRADOR).
- Liquidación: vacaciones/gratificación/CTS truncas, indemnización, descuentos → BORRADOR → CALCULADA → APROBADA → FIRMADA → PAGADA → CERRADA.
- Documentos de cese (`documentos/cese/`): upload masivo de PDFs (baja SUNAT, boleta S10) con match automático por DNI.
- Baja T-Registro individual desde `integraciones`.

---

## 2. Problemas detectados (priorizados)

### 🔴 Críticos (integridad de datos / dinero)

**P1. "Días libres" sin fuente única de verdad.** Viven en 4 modelos que no se sincronizan: `Roster` (DL/DLA), `RegistroPapeleta` (BAJADAS/VAC), `SaldoVacacional` (gozados/pendientes) y `Personal.dias_libres_corte_2025`. Aprobar una `SolicitudVacacion` NO crea papeleta ni actualiza el Roster; crear una papeleta VAC NO descuenta saldo. **Riesgo real de doble goce/doble descuento.**

**P2. Descuentos de planilla manuales.** `CuotaPrestamo` entra sola al engine (idempotente, bien hecho), pero `DescuentoPlanilla`/`AplicacionDescuento` requiere que el admin cree la aplicación cada mes y cargue `otros_descuentos` a mano. Un embargo judicial olvidado = incumplimiento legal.

**P3. Motivos de cese triplicados.** `Personal` (13 opciones), `ProcesoOffboarding` (5), `LiquidacionLaboral` (8), con mapeos manuales entre ellos. Inconsistencia garantizada a futuro.

**P4. Offboarding no valida activos.** `ActivoAsignado` existe (con estados ASIGNADO/DEVUELTO) pero nada impide cerrar el offboarding ni pagar la liquidación con laptop/EPP sin devolver.

### 🟡 Importantes (flujo confuso / trabajo duplicado)

**P5. Aprobación de requisición vuelve a BORRADOR.** No existe estado "APROBADA"; la única evidencia es `aprobada_por != null`, y se puede publicar sin aprobar. Además existe un motor de workflows genérico (`workflows/InstanciaFlujo`, con escalamiento y auditoría) que NO se usa aquí.

**P6. Dos flujos de cese en paralelo** (dar-baja rápido vs wizard con preview). El rápido se salta el preview de liquidación.

**P7. Onboarding y offboarding no se conocen.** Cesar a alguien en período de prueba no cancela su onboarding en curso.

**P8. Cruce Tareo-Roster y faltas automáticas son comandos manuales** (`generar_faltas_auto`, cruce bajo demanda). Si el admin lo olvida, los reportes quedan incompletos.

**P9. Compensación de feriados hardcodeada** (`aplicar_feriados_semana_santa_2026`): cada feriado especial requiere código nuevo, aunque el modelo `CompensacionFeriado` ya existe para parametrizarlo.

**P10. Pantallas/URLs legacy vivas junto a las nuevas:** `liquidaciones_panel` (viejo) vs `LiquidacionLaboral` (nuevo), `conceptos_panel` viejo vs `conceptos/configurar/`, "Dashboard Legacy" de reclutamiento visible en el menú, endpoint `mover etapa` duplicado (2 implementaciones).

**P11. Paso GENERAR_CARGA_S10 del cierre es un stub** — el wizard dice 7 pasos pero uno no hace nada.

**P12. IR 5ta con dos métodos** (legacy + SUNAT) seleccionables por booleano; tasas AFP/SCTR hardcodeadas en engine con override en ConfiguracionSistema — dos fuentes de verdad.

### 🔵 UX / "muchas ventanas"

**P13. Sobrecarga de navegación:** 171 items de menú en 21 secciones (~823 URLs). Nóminas sola tiene ~27 items de menú incluyendo 6 calculadoras como items separados.

**P14. Cuatro calendarios distintos** para responder "¿quién está disponible el día X?": `/calendario/` (unificado), `/vacaciones/calendario/` (+variante anual), `/asistencia/calendario/` (grid tareo), `/personal/roster/matricial/` (grid turnos).

**P15. Dashboards solapados en reclutamiento:** Mi Día, Dashboard, Dashboard Legacy, Stats Reclutadores, Funnel — 5 pantallas de KPIs del mismo dominio.

**P16. Bandejas de aprobación fragmentadas:** `/personal/aprobaciones/` (roster), `/workflows/` (bandeja genérica), vacaciones pendientes, permisos pendientes, papeletas pendientes, préstamos pendientes — cada una en su módulo.

**P17. Módulos experimentales colgando:** `mobile/` (React Native, 2 commits, TODOs) y `wa_marketing/` (2 commits) — decidir si avanzan o se archivan. `provisioning/` está vacío.

---

## 3. Recomendaciones de optimización

### Quick wins (bajo esfuerzo, alto impacto)
1. **Estado `APROBADA` en Vacante** (o bloquear publicar sin `aprobada_por`). 1 migración + 2 vistas.
2. **Auto-integrar `DescuentoPlanilla` al engine** copiando el patrón exacto de `CuotaPrestamo` (filtro descuentos_activos → Sum cuota_mensual → `AplicacionDescuento` auto). Elimina P2.
3. **Validación de activos en offboarding**: al completar el paso "entrega de activos" (o al aprobar liquidación), verificar `ActivoAsignado.filter(estado='ASIGNADO')` y advertir/bloquear.
4. **Un catálogo único de motivos de cese** (constants compartidas importadas por los 3 modelos; los 3 CHOICES apuntan a la misma lista).
5. **Auto-ejecutar `generar_faltas_auto` + cruce Tareo-Roster** como post-proceso de toda importación de asistencia.
6. **Retirar del menú lo legacy**: Dashboard Legacy reclutamiento, liquidaciones viejas, conceptos viejos (redirect 301 a las nuevas).

### Medio plazo (estructura)
7. **Papeleta como fuente única de ausencias**: `SolicitudVacacion.aprobar()` crea `RegistroPapeleta` VAC automáticamente; el Roster y los calendarios leen papeletas aprobadas. Un solo lugar donde "el día X esta persona no trabaja".
8. **Consolidar el cese en un solo flujo**: el wizard (con preview de liquidación) como único camino; "dar de baja" rápido = wizard con defaults pre-llenados.
9. **Vincular onboarding ↔ offboarding**: signal que cancela onboarding EN_CURSO al crear offboarding.
10. **Un solo calendario con capas** (turnos, vacaciones, feriados, asistencia real) y filtros; deprecar los otros 3 como vistas, manteniendo sus datos.
11. **Bandeja de aprobaciones unificada**: extender `/workflows/bandeja/` (ya genérico con GenericFK, escalamiento y auditoría) para que roster, vacaciones, permisos, papeletas y préstamos registren instancias ahí. El motor ya existe; está infrautilizado.
12. **Implementar el paso S10 del cierre** o quitarlo del wizard (hoy da falsa sensación de validación).
13. **Centralizar tasas legales** en ConfiguracionSistema (una sola fuente; engine sin constantes hardcodeadas) y un solo método IR 5ta.
14. **Parametrizar compensaciones de feriado** vía el modelo `CompensacionFeriado` existente (sin comandos por año).

### Navegación / UX
15. **Menú por tarea, no por app**: consolidar las 6 calculadoras de nómina en una sola pantalla con tabs; agrupar reportes; mover configuraciones (etapas, conceptos, tasas, tipos) a una sección única "Configuración" — el menú puede bajar de 171 a ~90 items sin perder funcionalidad.
16. **"Mi Día" como patrón transversal**: ya existe para reclutador y nóminas; replicar para RRHH-operaciones (pendientes de aprobación + vencidos + alertas del día) y hacer que sea la landing por rol.
17. **Decidir el destino de `mobile/` y `wa_marketing/`**: avanzar o archivar; hoy son superficie de mantenimiento sin retorno.
18. **Provisioning**: si se implementa, empezar mínimo: checklist TI con campos estructurados (correo creado sí/no, usuario AD, equipo asignado FK a ActivoAsignado) en vez de integraciones complejas.

---

## 4. Lo que está bien (no tocar)

- **Snapshot legal congelado por período** (`parametros_snapshot`) — auditoría fiscal sólida.
- **Préstamos → nómina automático e idempotente** — el patrón a copiar para descuentos.
- **Contratación transaccional** candidato→Personal→onboarding en un solo POST atómico.
- **CV parser + scoring + banco de talento** — pipeline de reclutamiento muy completo.
- **Cierre mensual como wizard validador** — buen diseño, solo falta completar S10.
- **Motor de workflows genérico** con escalamiento por vencimiento — infrautilizado pero bien diseñado.
- **Liquidación laboral** completa y reutilizando el engine (sin cálculos duplicados).
- **Menú contextual por rol/plan/módulo** — la lógica de visibilidad ya existe; el problema es solo el volumen.

---

*Generado por análisis automatizado de código (5 agentes de exploración sobre los 27 módulos, modelos, URLs, señales y templates del proyecto).*
