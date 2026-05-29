# Manual visual — Harmoni ERP

> Guía paso a paso con capturas reales de la plataforma. Complementa al
> [MANUAL_USUARIO.md](../../MANUAL_USUARIO.md) (referencia detallada en texto).
> Capturas generadas el 2026-05-29 sobre datos de demostración.

## Contenido
1. [Acceso y Dashboard](#1-acceso-y-dashboard)
2. [Proceso de Planilla (paso a paso)](#2-proceso-de-planilla-paso-a-paso)
3. [Asistencia / Tareo](#3-asistencia--tareo)
4. [Personal](#4-personal)
5. [Vacaciones y Permisos](#5-vacaciones-y-permisos)
6. [Préstamos y Adelantos](#6-préstamos-y-adelantos)
7. [Reclutamiento](#7-reclutamiento)
8. [Disciplinaria](#8-disciplinaria)
9. [Evaluaciones de Desempeño](#9-evaluaciones-de-desempeño)
10. [Dashboard Ejecutivo](#10-dashboard-ejecutivo)

---

## 1. Acceso y Dashboard

Al iniciar sesión llegas al **Inicio**, con el resumen del día, accesos rápidos
(Dashboard Ejecutivo, Reporte BI, Nuevo Empleado) y las alertas de nóminas.

![Dashboard](img/01_dashboard.png)

La barra superior incluye el buscador global (**Ctrl + K**), notificaciones y el
menú de empresa (arriba a la izquierda) para cambiar entre RUCs o ver consolidado.

---

## 2. Proceso de Planilla (paso a paso)

El flujo completo es: **crear período → generar → revisar → aprobar → emitir boletas → exportar a SUNAT**.

### Paso 1 — Abrir el módulo Nóminas
Menú lateral → **Nóminas → Períodos**. Verás los períodos existentes, KPIs del
último período y los procesos especiales (Gratificación, CTS, Utilidades).

![Panel de Nóminas](img/02_nominas_panel.png)

### Paso 2 — Crear un período nuevo
Botón **➕ Nuevo período**. Elige el tipo (Planilla Regular, Gratificación, CTS,
Utilidades o Liquidación), el mes/año y confirma las fechas — se autocompletan
según el ciclo configurado (ej. 22 del mes anterior → 21 del mes actual).

![Nuevo período](img/03_nomina_nuevo.png)

### Paso 3 — Generar la planilla
En el detalle del período (estado **Borrador**) pulsa **Generar planilla**. El
sistema calcula a todos los trabajadores activos: ingresos, descuentos (AFP/ONP,
5ta categoría), neto y costo empresa. El período pasa a mostrar sus KPIs.

![Detalle de período con acciones](img/04_nomina_detalle.png)

Desde aquí dispones de toda la barra de acciones:
- **Exportar CSV** / **Reporte Ejecutivo (PDF)**
- **Boletas ZIP** — todas las boletas en PDF
- **SUNAT** — PLAME (PDT 601) y T-Registro
- **Pago a bancos** — archivos por banco (BCP, BBVA, Scotiabank, Interbank, BN)
- **Comparativo** y **Notificar** boletas

### Paso 4 — Revisar una boleta individual
Haz clic en un trabajador de la tabla para ver su **boleta de pago** detallada
(conceptos, base de cálculo, descuentos). Desde aquí puedes descargar el PDF
individual o editar conceptos manuales antes de aprobar.

![Boleta del trabajador](img/05_nomina_registro.png)

### Paso 5 — Aprobar el período
Cuando los montos están correctos, **Aprobar** cierra el período (bloquea edición)
y notifica a cada trabajador que su boleta está disponible (DS 009-2011-TR).

### Paso 6 — Emitir y entregar boletas
Menú → **Nóminas → Emisión de Boletas**. Aquí ves el tracking de recepción
(visualizadas / descargadas / sin ver) y puedes descargar todas, notificar
pendientes, exportar CSV o el reporte ejecutivo.

![Emisión de boletas](img/06_emision_boletas.png)

---

## 3. Asistencia / Tareo

El módulo de **Asistencia** muestra el resumen del ciclo (horas, faltas, HE) y da
acceso a papeletas, KPIs y exportaciones.

![Asistencia](img/07_asistencia.png)

La **matriz de asistencia** muestra por trabajador y día el estado (asistió,
falta, vacaciones, permiso, feriado), con totales por día y leyenda de colores.

![Matriz de asistencia](img/08_asistencia_matriz.png)

---

## 4. Personal

Listado de colaboradores con búsqueda, filtros por área/estado y exportación.

![Lista de personal](img/09_personal_lista.png)

Al abrir un trabajador ves su ficha completa: datos personales, laborales,
contratos, asistencia, documentos y acciones (editar, contratos, boletas).

![Detalle de empleado](img/10_personal_detalle.png)

---

## 5. Vacaciones y Permisos

Panel con saldos, solicitudes y calendario de ausencias.

![Vacaciones](img/11_vacaciones.png)

Para registrar una solicitud: **Nueva Solicitud** → elige al trabajador, fechas
de inicio y fin, y el motivo. El sistema calcula los días y valida el derecho
(D.Leg. 713: se genera tras 1 año de servicio).

![Nueva solicitud de vacaciones](img/12_vacaciones_nueva.png)

---

## 6. Préstamos y Adelantos

Panel de préstamos y adelantos (CTS, gratificación, sueldo, vacaciones).

![Préstamos](img/13_prestamos.png)

**Nuevo Préstamo** → trabajador, tipo, monto y número de cuotas. Tras la
aprobación se genera el **cronograma de cuotas** (montos y fechas mensuales) que
se descuenta automáticamente en planilla.

![Nuevo préstamo](img/14_prestamos_nuevo.png)

---

## 7. Reclutamiento

**Pipeline** tipo Kanban: arrastra candidatos entre etapas (Postulado →
Entrevista → Oferta → Contratado). Al **contratar** se crea el empleado en
Personal y se inicia su proceso de Onboarding automáticamente.

![Pipeline de reclutamiento](img/15_reclutamiento_pipe.png)

---

## 8. Disciplinaria

Gestión del proceso disciplinario: registrar medida → notificar (inicia el plazo
legal de descargo en casos de despido) → registrar descargo → resolver.

![Disciplinaria](img/17_disciplinaria.png)

---

## 9. Evaluaciones de Desempeño

Ciclos de evaluación, competencias y comparativas (incluye evaluación 360°).

![Evaluaciones](img/18_evaluaciones.png)

---

## 10. Dashboard Ejecutivo

Vista consolidada para gerencia: headcount, costo de planilla, rotación,
asistencia y alertas, con filtros por empresa.

![Dashboard Ejecutivo](img/16_dashboard_ejec.png)

---

> **Nota.** Las capturas se regeneran con `scripts/capture_manual.py` (requiere el
> dev server activo y una sesión válida). Útil para refrescar el manual tras
> cambios de UI.
