# Harmoni × EDO — Anexo Cotización
## Onboarding Express: 2 semanas, no 5

Versión 2026-05-21 · Anexo a Cotización del 2026-05-19

---

## El cambio en el enfoque

Después de revisar la operación de EDO en profundidad, **simplificamos el go-live**.

| Enfoque clásico (lo que ofrece la industria) | Onboarding Express Harmoni |
|---|---|
| Migrar 12 meses de planillas históricas desde Spring | **NO migramos historia** |
| 4-5 semanas de implementación | **1-2 semanas** |
| IT de EDO involucrado en parallel runs | RRHH llena un Excel |
| Validación centavo a centavo de meses pasados | Solo validamos saldos al corte |
| Riesgo de duplicar boletas | Cero — salto en limpio |

**La promesa**: "No te pedimos migrar tu historia. Te pedimos un Excel con los saldos al **31/05/2026** (o fecha de corte que prefieras)."

---

## Cómo funciona el wizard de apertura

Tu equipo de RRHH ejecuta 3 pasos:

1. **Define la fecha de corte** (default 31/05/2026 — último cierre Spring)
2. **Descarga la plantilla Excel** — viene pre-llenada con todos los trabajadores activos
3. **Sube el Excel completado** con: provisión CTS, provisión gratificación, provisión vacaciones, días vac. pendientes, IR 5ta acumulado del año, saldo préstamos vigentes

Validamos, mostramos preview, confirmas. **Listo: Harmoni arranca a procesar desde junio 2026 en adelante.**

Spring sigue corriendo:
- Contabilidad
- Logística  
- Facturación

**Harmoni asume RRHH end-to-end** y le manda a Spring 3 cosas estandarizadas:
- Asiento contable mensual de planilla (Excel Universal / Concar / Siscont)
- Maestro actualizado de empleados (para Logística)
- Costos por centro de costo (para reportes de rentabilidad)

---

## Plan revisado de implementación

| Semana | Trabajo | Quién |
|--------|---------|-------|
| **S1** | Setup empresa, locales, puestos. Conceptos remunerativos custom de EDO (propinas pool, bono nocturno, etc.) | Harmoni + RRHH EDO |
| **S1** | Configurar plan de cuentas para asiento contable (mapear a las cuentas que usa Spring) | Harmoni + contador EDO |
| **S2** | Equipo RRHH EDO llena la plantilla de apertura (saldos al 31/05/2026) | RRHH EDO |
| **S2** | Capacitación al equipo de RRHH (2 sesiones de 90 min) | Harmoni |
| **S2** | Doble corrida paralela: planilla mayo en Spring vs Harmoni. Validar coincidencia. | Harmoni + contador EDO |
| **Jun** | **Go-live**. Harmoni emite la planilla oficial de junio 2026. Exporta asiento a Spring. | Equipo EDO |

---

## Lo que esto baja en la cotización

Al simplificar el go-live:

- ❌ Removemos **horas de migración histórica** (que en una propuesta clásica son ~40-60 horas profesionales)
- ❌ Removemos **horas de parallel run histórico** de 12 meses
- ✅ Mantenemos la promesa de funcionalidad completa
- ✅ **Time-to-value se acelera** — EDO opera en Harmoni el mes siguiente al contrato

**Esto se traduce en una reducción de aproximadamente 20-30% del costo de implementación**, manteniendo intacto el valor del producto.

---

## Lo que Harmoni le manda a Spring (resumen para el contador de EDO)

```
                ┌──────────────────────────────┐
                │           SPRING             │
                │  • Contabilidad              │
                │  • Logística                 │
                │  • Facturación               │
                │  • Inventario                │
                └─────────────▲────────────────┘
                              │
                              │ Cada mes / on-demand
                              │
            ┌─────────────────┴──────────────────┐
            │                                    │
            │  ① Asiento contable mensual        │
            │     (formato CONCAR / Siscont /    │
            │      Excel Universal estándar)     │
            │                                    │
            │  ② Maestro empleados activos       │
            │     (DNI, local, estado)           │
            │                                    │
            │  ③ Costos por centro de costo      │
            │     (rentabilidad por local)       │
            │                                    │
            └─────────────────▲──────────────────┘
                              │
                ┌─────────────┴────────────────┐
                │          HARMONI             │
                │  RRHH end-to-end:            │
                │  • Contratación              │
                │  • Onboarding                │
                │  • Turnos rotativos          │
                │  • Asistencia                │
                │  • Planilla + boletas        │
                │  • Liquidación al cese       │
                │  • PLAME / T-Reg / AFPnet    │
                │  • Briefing del Día          │
                │  • Pulse del Grupo (24 RUCs) │
                └──────────────────────────────┘
```

El contador de EDO sigue trabajando con Spring sin cambios. Solo importa el asiento mensual que Harmoni le entrega cada cierre.

---

## Features destacadas para Grupo Gastronómico Premium

Harmoni ahora incluye features específicas para grupos como EDO:

### 🎯 Pulse del Grupo
Dashboard ejecutivo con las 24 empresas/locales como tarjetas. Cada local muestra: headcount, asistencia hoy, planilla del mes, alertas. Código verde/amarillo/rojo según salud operativa. **La pantalla que el dueño abre cada mañana.**

### 📋 Briefing del Día
Pre-shift handover estilo brigade kitchen (Escoffier). El jefe de local publica antes del servicio: covers esperados, VIPs/alergias, especiales del chef, items 86'd (sin stock), dress code, notas operativas. La brigada lo ve en su portal con notificación push. **Trail auditable para una operación premium.**

### 📊 Comparativo Mensual
Vista evolutiva últimos 3/6/9/12 meses: trabajadores, neto pagado, costo empresa, AFP/ONP. Gráfico Chart.js + tabla con deltas porcentuales + export CSV. Para gerencia y planeación.

### 💼 Saldos de Apertura (Onboarding Express)
Wizard de 3 pasos con plantilla Excel. Reemplaza la migración histórica completa.

### 🔌 Outputs Universales
Excel Universal + CONCAR + Siscont + SAP + SIRE SUNAT + Provisiones separadas. Funciona con CUALQUIER ERP receptor — no nos casamos con un proveedor específico de contabilidad.

---

## Garantías del Onboarding Express

- **Parallel run validado**: corremos planilla mayo en Spring y en Harmoni. Si no coinciden centavo a centavo, no hacemos go-live.
- **Backup del primer mes**: la primera planilla de Harmoni en producción tiene revisión adicional de nuestro equipo sin costo.
- **Soporte primer mes intensivo**: respuesta < 4 horas hábiles durante los primeros 30 días de operación.
- **Rollback plan**: si por cualquier razón hay que volver a Spring antes de los 60 días, Harmoni le entrega toda la data en formato estándar para re-cargar en Spring. No data lock-in.

---

## Próximos pasos sugeridos

1. **Validar con Isabel** el ángulo "Onboarding Express" antes del próximo meeting
2. **Conseguir muestra del asiento contable** que Spring importa (1 archivo de cualquier mes) — esto nos permite afinar el conector específico
3. **Definir fecha de corte preferida** — 31/05/2026 o 31/12/2025 (recomendamos la primera)
4. **Agendar demo en vivo del Wizard de Apertura** + Pulse del Grupo + Briefing del Día

---

**Contacto**: Edwin López — Gerente de Operaciones Harmoni
*eflopezt@gmail.com · www.harmoni.pe*

*Cotización viva. Sujeta a revisión final tras llamada de validación con EDO.*
