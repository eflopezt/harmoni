# Manual de Usuario — Harmoni ERP

**Sistema de gestión de RR.HH. y planillas (Perú · D.Leg. 728 / 727)**
Versión del manual: 2026-05-29 · Capturas reales sobre datos de demostración.

---

## Cómo usar este manual

- Cada sección corresponde a un grupo del **menú lateral** de Harmoni.
- Las capturas muestran la pantalla real; debajo se explica **qué hace** y los
  **pasos** para operarla.
- Atajo clave en toda la plataforma: **`Ctrl + K`** abre el buscador global
  (empleados, papeletas, documentos, acciones).
- El selector de **empresa** (arriba a la izquierda) cambia entre RUCs o muestra
  la **vista consolidada** de todo el grupo.

## Contenido

1. [Inicio](#1-inicio)
2. [Personal](#2-personal)
3. [Asistencia / Tareo](#3-asistencia--tareo)
4. [Nóminas — incluye el proceso de planilla paso a paso](#4-nóminas)
5. [Vacaciones y Permisos](#5-vacaciones-y-permisos)
6. [Préstamos y Viáticos](#6-préstamos-y-viáticos)
7. [Documentos / Legajo Digital](#7-documentos--legajo-digital)
8. [Reclutamiento](#8-reclutamiento)
9. [Onboarding y Offboarding](#9-onboarding-y-offboarding)
10. [Evaluaciones de Desempeño](#10-evaluaciones-de-desempeño)
11. [Capacitaciones](#11-capacitaciones)
12. [Disciplinaria](#12-disciplinaria)
13. [Encuestas y Clima](#13-encuestas-y-clima)
14. [Comunicaciones](#14-comunicaciones)
15. [Estructura Salarial](#15-estructura-salarial)
16. [Analytics y Dashboard Ejecutivo](#16-analytics-y-dashboard-ejecutivo)
17. [Portal del Trabajador](#17-portal-del-trabajador)

---

## 1. Inicio

Al iniciar sesión llegas al **Inicio**: resumen del día, accesos rápidos
(Dashboard Ejecutivo, Reporte BI, Nuevo Empleado) y las alertas de nóminas.

![Inicio](img/00_inicio/01_dashboard.png)

La barra superior tiene el **buscador global** (`Ctrl + K`), las notificaciones
(campana) y el menú de usuario/empresa.

---

## 2. Personal

### Lista de empleados
Menú **Personal → Empleados**. Listado con búsqueda, filtros por área/estado y
exportación. Clic en una fila abre la ficha del trabajador.

![Lista de personal](img/01_personal/01_lista.png)

### Ficha del empleado
Datos personales, laborales, contratos, asistencia y documentos del colaborador,
con accesos a editar, ver contratos y descargar boletas.

![Ficha de empleado](img/01_personal/02_detalle.png)

### Contratar Express
Alta rápida de un trabajador con los datos mínimos para incluirlo en planilla.

![Contratar Express](img/01_personal/03_contratar_express.png)

### Contratos
Gestión de contratos por trabajador (tipo, vigencia, renovaciones, vencimientos).

![Contratos](img/01_personal/04_contratos.png)

### Organigrama
Estructura jerárquica de la organización por áreas y reportes.

![Organigrama](img/01_personal/05_organigrama.png)

### Roster Matricial
Programación de turnos por trabajador y día (cuadrícula editable).

![Roster Matricial](img/01_personal/06_roster.png)

### Reportes RR.HH.
Reportes consolidados de personal (altas, ceses, distribución).

![Reportes RRHH](img/01_personal/07_reportes.png)

---

## 3. Asistencia / Tareo

### Dashboard de asistencia
Resumen del ciclo: horas trabajadas, faltas, horas extra y tasa de asistencia.

![Dashboard asistencia](img/02_asistencia/01_dashboard.png)

### KPIs
Indicadores de asistencia, puntualidad y ausentismo con gráficos.

![KPIs asistencia](img/02_asistencia/02_kpis.png)

### Asistencia Matricial
Matriz por trabajador × día con el estado (asistió, falta, vacaciones, permiso,
feriado), totales por día y leyenda de colores.

![Matriz de asistencia](img/02_asistencia/03_matricial.png)

### Papeletas
Registro y gestión de papeletas (permisos, comisiones, salidas) que afectan el
tareo.

![Papeletas](img/02_asistencia/04_papeletas.png)

### Banco de Horas
Acumulado y compensación de horas por trabajador.

![Banco de horas](img/02_asistencia/05_banco_horas.png)

### Briefing del Día
Resumen pre-turno (gastronomía): quién entra, novedades y pendientes del día.

![Briefing del día](img/02_asistencia/06_briefing.png)

### Exportaciones e Importaciones
Exportar el tareo a Excel/PDF e importar la asistencia (desde el biométrico).

![Exportaciones](img/02_asistencia/07_exportaciones.png)
![Importaciones](img/02_asistencia/08_importaciones.png)

---

## 4. Nóminas

El flujo de planilla es: **crear período → generar → revisar → aprobar → emitir
boletas → exportar a SUNAT**.

### Paso 1 — Períodos
Menú **Nóminas → Períodos**: períodos existentes, KPIs del último y procesos
especiales (Gratificación, CTS, Utilidades).

![Períodos](img/03_nominas/01_periodos.png)

### Paso 2 — Nuevo período
**➕ Nuevo período**: elige tipo (Planilla Regular, Gratificación, CTS,
Utilidades, Liquidación), mes/año y confirma las fechas (se autocompletan según
el ciclo configurado, p. ej. 22 → 21).

![Nuevo período](img/03_nominas/02_nuevo_periodo.png)

### Paso 3 — Generar y revisar la planilla
En el detalle (estado **Borrador**) pulsa **Generar planilla**: calcula ingresos,
descuentos (AFP/ONP, 5ta), neto y costo empresa de todos los activos. La barra de
acciones ofrece Exportar CSV, Boletas ZIP, **SUNAT** (PLAME, T-Registro), Reporte
Ejecutivo, **Pago a bancos**, Comparativo y Notificar.

![Detalle de período](img/03_nominas/03_detalle.png)

### Paso 4 — Boleta del trabajador
Clic en un trabajador para ver su boleta detallada (conceptos, base, descuentos),
descargar el PDF o editar conceptos manuales antes de aprobar.

![Boleta](img/03_nominas/04_boleta.png)

### Paso 5 — Aprobar y emitir boletas
Tras **Aprobar** (cierra el período y notifica a los trabajadores), el panel de
**Emisión de Boletas** muestra el tracking de recepción y permite descargar
todas, notificar pendientes o exportar.

![Emisión de boletas](img/03_nominas/05_emision_boletas.png)

### Workflow del Mes
Vista guiada del cierre mensual con los pasos y su estado.

![Workflow del mes](img/03_nominas/06_workflow_mes.png)

### Harmoni IA — Nóminas
Asistente que explica conceptos de la boleta y responde dudas de cálculo.

![Agente IA](img/03_nominas/07_agente_ia.png)

### Conceptos
Catálogo de conceptos remunerativos y descuentos configurables.

![Conceptos](img/03_nominas/08_conceptos.png)

### Calculadoras
Simuladores: sueldo, **CTS**, gratificación, **liquidación**, neto↔bruto y
recomendador AFP.

![Calculadora](img/03_nominas/09_calculadora.png)
![Calculadora CTS](img/03_nominas/10_calc_cts.png)
![Calculadora Liquidación](img/03_nominas/11_calc_liquidacion.png)

### IR 5ta Categoría
Cálculo y proyección del impuesto a la renta de 5ta categoría.

![IR 5ta](img/03_nominas/12_ir5ta.png)

### Flujo de Caja y Comparativos
Proyección de egresos de planilla y comparativos mes a mes.

![Flujo de caja](img/03_nominas/13_flujo_caja.png)
![Comparativo mensual](img/03_nominas/14_comparativo.png)

---

## 5. Vacaciones y Permisos

### Panel de vacaciones
Saldos, solicitudes y calendario de ausencias.

![Vacaciones](img/04_vacaciones/01_panel.png)

### Nueva solicitud
**Nueva Solicitud** → trabajador, fechas de inicio y fin, motivo. El sistema
calcula los días y valida el derecho (D.Leg. 713: tras 1 año de servicio).

![Nueva solicitud](img/04_vacaciones/02_nueva.png)

### Permisos / Licencias
Gestión de permisos y licencias por tipo, con su plazo y sustento.

![Permisos](img/04_vacaciones/03_permisos.png)

### Saldos
Saldos vacacionales por trabajador y período (ganados, gozados, pendientes).

![Saldos](img/04_vacaciones/04_saldos.png)

---

## 6. Préstamos y Viáticos

### Préstamos
Préstamos y adelantos (CTS, gratificación, sueldo, vacaciones).

![Préstamos](img/05_prestamos/01_panel.png)

### Nuevo préstamo
Trabajador, tipo, monto y nº de cuotas. Al aprobar se genera el **cronograma**
(montos y fechas mensuales) que se descuenta automáticamente en planilla.

![Nuevo préstamo](img/05_prestamos/02_nuevo.png)

### Viáticos
Asignación y rendición de viáticos por trabajador y período.

![Viáticos](img/05_prestamos/03_viaticos.png)

---

## 7. Documentos / Legajo Digital

### Legajo
Documentos del trabajador organizados por categoría y tipo.

![Legajo](img/06_documentos/01_legajo.png)

### Faltantes
Documentos pendientes por trabajador (control de completitud del legajo).

![Faltantes](img/06_documentos/02_faltantes.png)

### Constancias
Generador de constancias (trabajo, remuneraciones) en PDF a partir de plantillas.

![Constancias](img/06_documentos/03_constancias.png)

### Firma Digital
Solicitud y seguimiento de firmas de documentos.

![Firma digital](img/06_documentos/04_firma.png)

### Cese / Liquidación de documentos
Documentación del proceso de cese (BLIQ).

![Cese](img/06_documentos/05_cese.png)

---

## 8. Reclutamiento

### Vacantes
Listado de vacantes y su estado.

![Vacantes](img/07_reclutamiento/01_vacantes.png)

### Pipeline (Kanban)
Tablero de candidatos por etapa (Postulado → Entrevista → Oferta → Contratado).
Al **contratar** se crea el empleado en Personal y se inicia su Onboarding.

![Pipeline](img/07_reclutamiento/02_pipeline.png)

### Funnel
Conversión entre etapas del proceso de selección.

![Funnel](img/07_reclutamiento/03_funnel.png)

### Banco de Talento
Candidatos guardados para futuras vacantes.

![Banco de talento](img/07_reclutamiento/04_banco.png)

### CV Express
Carga y parseo rápido de un CV para crear un candidato.

![CV Express](img/07_reclutamiento/05_cv_express.png)

---

## 9. Onboarding y Offboarding

### Dashboard de Onboarding
Procesos de incorporación en curso y su avance.

![Dashboard onboarding](img/08_onboarding/01_dashboard.png)

### Onboarding
Checklist de pasos por nuevo trabajador (cuentas, equipos, inducción).

![Onboarding](img/08_onboarding/02_onboarding.png)

### Offboarding
Proceso de salida (devolución de activos, accesos, finiquito).

![Offboarding](img/08_onboarding/03_offboarding.png)

---

## 10. Evaluaciones de Desempeño

### Dashboard
Estado de los ciclos de evaluación y resultados.

![Dashboard evaluaciones](img/09_evaluaciones/01_dashboard.png)

### 9-Box Grid
Matriz desempeño × potencial para clasificar talento.

![9-Box](img/09_evaluaciones/02_ninebox.png)

### Comparativa de competencias
Radar comparando puntajes por competencia entre áreas o ciclos.

![Comparativa](img/09_evaluaciones/03_comparativa.png)

### OKRs
Objetivos y resultados clave por trabajador/área.

![OKRs](img/09_evaluaciones/04_okrs.png)

---

## 11. Capacitaciones

### Capacitaciones
Programa de capacitaciones, asistentes y certificados.

![Capacitaciones](img/10_capacitaciones/01_panel.png)

### BPM / HACCP (gastronomía)
Seguimiento de certificaciones sanitarias por trabajador y local.

![BPM/HACCP](img/10_capacitaciones/02_gastro.png)

---

## 12. Disciplinaria

### Dashboard
Estado de los procesos disciplinarios.

![Dashboard disciplinaria](img/11_disciplinaria/01_dashboard.png)

### Medidas
Listado de medidas disciplinarias.

![Medidas](img/11_disciplinaria/02_medidas.png)

### Nueva medida
Registrar una medida: trabajador, tipo (verbal/escrita/suspensión/despido),
falta, fecha de hechos y descripción. El flujo continúa con notificar → descargo
→ resolver (el plazo legal de descargo aplica en casos de despido).

![Nueva medida](img/11_disciplinaria/03_nueva.png)

---

## 13. Encuestas y Clima

Encuestas de clima y pulse de la organización.

![Encuestas](img/12_encuestas/01_panel.png)

---

## 14. Comunicaciones

### Notificaciones
Centro de notificaciones internas.

![Notificaciones](img/13_comunicaciones/01_notif.png)

### Comunicados
Comunicados masivos a trabajadores (con plantillas y campañas).

![Comunicados](img/13_comunicaciones/02_comunicados.png)

---

## 15. Estructura Salarial

### Bandas salariales
Bandas por puesto/nivel y posicionamiento de cada trabajador.

![Bandas salariales](img/14_salarios/01_bandas.png)

### Gráfico de bandas
Visualización de equidad salarial (dispersión por banda).

![Gráfico de bandas](img/14_salarios/02_grafico.png)

---

## 16. Analytics y Dashboard Ejecutivo

### Dashboard Ejecutivo
Vista consolidada para gerencia: headcount, costo de planilla, reclutamiento,
operación (BPM/HACCP), rotación y alertas, con filtro por empresa.

![Dashboard Ejecutivo](img/15_analytics/01_ejecutivo.png)

### Analytics
Tableros de people analytics.

![Analytics](img/15_analytics/02_analytics.png)

### Predictivo
Modelos predictivos (p. ej. riesgo de rotación).

![Predictivo](img/15_analytics/03_predictivo.png)

### Pulse del Grupo
Indicadores de clima/operación a nivel multi-empresa.

![Pulse del grupo](img/15_analytics/04_grupo_pulse.png)

---

## 17. Portal del Trabajador

Vista de **autoservicio del colaborador** (URL `/mi-portal/`). Cada trabajador
ingresa con su usuario y solo ve **sus propios datos**. Es una sección distinta
del panel administrativo de los capítulos anteriores.

### Mi Resumen
Pantalla de inicio del trabajador: saludo, encuestas/pulse pendientes y KPIs
personales (días trabajados, saldo de banco de horas, vacaciones disponibles,
HE del mes, último neto, préstamo activo), con accesos rápidos.

![Portal — Mi Resumen](img/17_portal/01_home.png)

### Mi Perfil
Datos personales y laborales del trabajador (solo lectura / edición de contacto).

![Portal — Mi Perfil](img/17_portal/02_perfil.png)

### Mi Asistencia
Marcas, tardanzas, faltas y resumen del ciclo del propio trabajador.

![Portal — Mi Asistencia](img/17_portal/03_asistencia.png)

### Mis Recibos de Sueldo
Boletas de pago del trabajador: ingresos, descuentos y neto, con **descargar
boleta (PDF)**, **confirmar recepción** (firma electrónica, DS 008-2011-TR) y
**explicar mi boleta (IA)**.

![Portal — Mis Recibos](img/17_portal/04_nomina.png)

### Mis Vacaciones
Saldo vacacional y solicitudes del trabajador, con opción de **solicitar**.

![Portal — Mis Vacaciones](img/17_portal/05_vacaciones.png)

### Mis Papeletas
Papeletas del trabajador (crear, ver estado, anular).

![Portal — Mis Papeletas](img/17_portal/06_papeletas.png)

### Mi Roster
Turnos programados del trabajador.

![Portal — Mi Roster](img/17_portal/07_roster.png)

### Mis Documentos
Documentos del legajo del trabajador disponibles para descarga.

![Portal — Mis Documentos](img/17_portal/08_documentos.png)

### Mis Evaluaciones
Resultados de las evaluaciones de desempeño del trabajador.

![Portal — Mis Evaluaciones](img/17_portal/09_evaluaciones.png)

### Mis Capacitaciones
Capacitaciones y certificaciones del trabajador, con su estado.

![Portal — Mis Capacitaciones](img/17_portal/10_capacitaciones.png)

### Mi Historia (Timeline)
Línea de tiempo de hitos del trabajador (ingreso, contratos, evaluaciones, etc.).

![Portal — Mi Historia](img/17_portal/11_timeline.png)

### Directorio
Directorio de colaboradores de la empresa.

![Portal — Directorio](img/17_portal/12_directorio.png)

### Mi Calendario y Banco de Horas
Calendario personal de ausencias/eventos y acumulado del banco de horas.

![Portal — Mi Calendario](img/17_portal/13_calendario.png)
![Portal — Banco de Horas](img/17_portal/14_banco_horas.png)

---

> **Regenerar este manual.** Las capturas administrativas se generan con
> `scripts/capture_manual.py <SESSION_KEY>` y las del portal con
> `scripts/capture_portal.py <SESSION_KEY_DE_TRABAJADOR>` (requieren el dev
> server activo y Playwright con el Chrome del sistema). Útil para refrescar el
> manual tras cambios de interfaz.
