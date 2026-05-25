# Propinas en Gastronomía — Best Practices Mundiales 2026

> **Investigación**: 2026-05-25. Para uso interno de Harmoni.
> **Objetivo**: Documentar cómo los grandes payrolls de hospitality manejan propinas
> y identificar qué nos falta en Harmoni vs el estado del arte global.

---

## 1. Sistemas estudiados

| Sistema | Origen | Especialidad |
|--------|--------|--------------|
| **Toast Payroll / Toast Tips Manager** | EE.UU. | POS dominante de restaurantes; pooled tipouts + sync directo + manual entry; 3 ventanas: workday, service period, order |
| **Square for Restaurants / Square Payroll** | EE.UU. | Import de propinas card; declaración de cash tips al clock-out via Team App; pool o pago directo |
| **7shifts** | Canadá/EE.UU. | Especialista en scheduling + tip pooling; integra con Toast, Square, Revel, Qu, GoTab; 3 modos de distribución |
| **TipHaus** | EE.UU. | Calculadora + app empleado + QR tipping ("Cheers") + pay card "HausMoney" + P2P transfers |
| **Kickfin** | EE.UU. | Foco en instant payouts directos al banco; sin app empleado; multi-POS API directa |
| **Tipper** | EE.UU. | App movil empleado; reporting fiscal |
| **Gusto Payroll** | EE.UU. | Ajusta automáticamente min wage si tip credit no cubre; reporte FICA tip credit (Form 8846); soporta service charges como non-tip wages |
| **ADP Workforce Now** | EE.UU./Global | Enterprise; reporting Form 8027 |
| **Tronc systems UK** (IRIS, Buzzacott, Stored) | Reino Unido | Esquema legal "tronc" con troncmaster designado (no puede ser el PAYE admin); ahorro NICs |
| **R&G / Sysrest / Posh** | Latam | POS comunes en restaurantes peruanos; manejan recargo al consumo pero rara vez automatizan distribución legal |

---

## 2. Conceptos clave

### 2.1 Tip Pooling vs Tip Sharing
- **Tip pool**: TODOS los tips colectados en el período van al pozo común y se redistribuyen según fórmula.
- **Tip sharing** (a.k.a. tip-out): cada server mantiene sus tips pero comparte un % con bussers/runners/bartenders/BOH.
- **Diferencia legal (US)**: el pool obliga a registrar el pozo y distribuirlo; tip-out es voluntario o por política casa.

### 2.2 Tip Credit (FLSA §3(m))
- Permite al empleador pagar **$2.13/hr** (min federal) en lugar de **$7.25/hr** si las propinas cubren la diferencia.
- Si el tip credit se invoca, **BOH (cocina) NO puede entrar al pool** (FLSA 2018 amendment).
- **80/20 rule**: si el tipped employee gasta >20% de su tiempo en tareas no productivas de tips (limpiar, prep), el employer pierde el derecho al tip credit por esas horas.
  - **Status 2026**: el DOL rescindió la 80/20 rule el 17-dic-2024 tras la sentencia del 5th Circuit; aún aplica en circuitos 1-4 y 6-11 (no en TX/LA/MS).
- **No aplica a Perú**: nuestro RMV (S/ 1,025) es íntegro independiente de propinas.

### 2.3 Service Charge vs Gratuity
- **Gratuity (tip voluntario)**: NO es ingreso de la empresa, pasa íntegro al empleado, no tributa renta empresa, en US no es wages.
- **Service Charge / Recargo al Consumo (US: auto-grat, UK: discretionary svc chg)**: la empresa lo factura, ES ingreso, pasa a wages cuando se distribuye → tributa.
- **IRS Rev. Rul. 2012-18**: criterios para distinguir — voluntad del cliente, monto libre, derecho a designar receptor, no negociado por norma de la empresa.
- **Perú (SUNAT)**: el recargo al consumo (hasta **13%**) NO es ingreso de la empresa NI es remunerativo para el trabajador → no afecta IGV, IR-empresa, AFP/ONP/CTS/Gratificaciones. Es nuestro caso de uso principal.

### 2.4 Tip Out (FOH → BOH)
- Práctica clásica US: el mozo retiene 70%, da:
  - **15%** a bussers
  - **10%** a runners
  - **5%** al bar
- Variantes: % sobre tips o % sobre ventas (1-4% típico).
- Hosts suelen recibir 0.5-1% de ventas (3-5% de los tips de servers).

### 2.5 Weighted by hours vs weighted by position/points
- **Por horas**: `share_i = tips_total × (horas_i / Σ horas)` — el más justo si todos hacen lo mismo.
- **Por puntos**: `share_i = tips_total × (puntos_i / Σ puntos)` — refleja jerarquía/skill (server=3, bartender=2.5, busser=1).
- **Híbrido (mejor práctica)**: `share_i = tips_total × (puntos_i × horas_i / Σ (puntos×horas))` — combina equidad temporal y jerárquica.
- 7shifts soporta los 3 modos; Toast los 2 primeros + percentage.

### 2.6 Mandatory vs Voluntary tip pool
- **Mandatory pool**: política escrita firmada por empleado al onboarding; obligatorio por turno; mejor para auditoría.
- **Voluntary**: cada server decide si contribuye al pozo; raro en operación moderna.

### 2.7 Cash vs Card Tips
- **Cash**: declarado por el empleado (Form 4070A US) → riesgo de under-reporting → IRS allocated tips si <8% de ventas (Form 8027).
- **Card**: capturado automáticamente por POS → trazable, sin disputas → más fácil para distribución posterior.
- **Mejor práctica**: registrar ambos separados en el pool → reporting tributario claro → trabajador ve qué % vino de qué fuente.

### 2.8 Form 8027 (US)
- Anual; large food establishments (>10 empleados/día); reporta tips totales declarados + ventas; si tips reportados <8% ventas → IRS asigna la diferencia a empleados.
- **Equivalente Perú**: no existe formulario propio; el recargo al consumo se reporta indirectamente vía libro de planillas.

### 2.9 Tronc Master (UK)
- Persona designada (puede ser tercero o empleado) que controla la distribución del tronc.
- **NO puede ser el admin de PAYE** (separación obligatoria).
- Beneficio: distribución del tronc no devenga NICs (~13.8% empleador, ~12% empleado) → ahorro material.
- **Employment (Allocation of Tips) Act 2023** (vigente 1-oct-2024): 100% de tips obligatorio al empleado, política escrita obligatoria, registros 3 años.

### 2.10 Distributive fairness algorithms
- **Per-hour rate**: `rate = pool / Σ horas`. Justo para roles homogéneos.
- **Weighted points**: cada rol tiene puntos; `pool × (pts_i × horas_i) / Σ (pts × horas)`.
- **Sales-weighted**: `0.7 × (ventas_i/Σventas) + 0.3 × (horas_i/Σhoras)` (modelo combinado; raro pero existe).
- **Equal split**: `pool / N`. Solo para shifts con un único rol o muy homogéneos.
- **Outlier detection**: si la dist. de un trabajador es <50% del promedio de su cargo, flag para revisión manual.

### 2.11 Auto-gratuity
- Cargo automático 18-20% para parties de 6-8 personas o más.
- US (IRS Rev. Rul. 2012-18): es **service charge**, NO tip → wages cuando se distribuye, sin tip credit, sin Form 8027.
- Triple disclosure obligatorio: menú + entrada + factura final.

---

## 3. Mejores prácticas operativas

### Cash vs Card (separación contable)
- POS captura card automáticamente.
- Cash declarado al clock-out por cada empleado (Square Team App, Toast Tips Manager).
- Pool agrega ambos pero los rastrea por separado en el reporte.

### Anti-disputas
- **Documentación previa**: política firmada en onboarding y reconfirmada en cada cambio.
- **Cálculo determinístico**: misma entrada → misma salida; fórmula publicada.
- **Visibilidad**: empleado ve su distribución en app móvil cada turno/semana.
- **Apelación con timeline**: la mayoría de softwares dan 48-72 hrs para apelar antes del payout final.

### Auditoría / trazabilidad
- **Log inmutable** de cambios en config del pool (modos, puntos por cargo).
- **Manager approval** queda registrado con timestamp y usuario.
- **Reconciliation cadence**: semanal POS vs payroll vs payouts; mensual spot-check; anual antes de W-2.
- **Retención de records**: US 3 años (FLSA); UK 3 años (post-2024 Act); Perú 5 años (libro de planillas).

### Integración con payroll
- Card tips → POS → payroll engine → boleta (taxable wages en US, no en Perú).
- Cash tips → declarados → reconciliados con POS → boleta (separado en US para reporting; informativo en Perú).
- Service charges → siempre wages en US; no remunerativo en Perú.

### Frecuencia de pago
- **Diaria** (Kickfin instant payout, TipHaus HausMoney): retención + lealtad, popular en US.
- **Semanal**: estándar US/UK.
- **Quincenal / mensual**: típico Latam, asociado a planilla normal.
- **Mejor práctica**: igualar la frecuencia de la planilla principal o más rápido (employee retention).

### Reporting al trabajador
- **App móvil** con histórico (TipHaus, Tipper, Toast Now).
- **Boleta/recibo separado** con desglose (cash declarado / card pool / tip-out recibido / tip-out dado).
- **Firma de aceptación** del payout (en papel para auditoría manual o digital).

---

## 4. Comparativa Harmoni actual vs estado del arte

| Capability | Toast | 7shifts | TipHaus | Gusto | Tronc UK | **Harmoni hoy** | Gap |
|---|---|---|---|---|---|---|---|
| Pool por puntos (cargo) | ✓ | ✓ | ✓ | — | ✓ | ✓ | — |
| Pool dividido parejo (per hour) | ✓ | ✓ | ✓ | — | ✓ | parcial (no por horas) | **× faltaba** |
| Pool **híbrido** (puntos × horas) | ✓ | ✓ | ✓ | — | ✓ | — | **× falta** |
| Cash vs Card tracking separado | ✓ | ✓ | ✓ | ✓ | ✓ | — | **× falta** |
| Tip-out FOH → BOH (% automático) | ✓ | ✓ | ✓ | — | ✓ | — | **× falta** |
| Retención casa (rotura/gastos) | parcial | ✓ | — | — | ✓ | ✓ | — |
| Inclusión/exclusión por rol | ✓ | ✓ | ✓ | — | ✓ | ✓ (cocina/admin) | — |
| Service charge vs tip distinction | ✓ | parcial | ✓ | ✓ | ✓ | — (todo se trata igual) | × útil futuro |
| Auto-gratuity (>N personas) | ✓ | — | parcial | — | — | — | × no-MVP |
| Reporte PDF firmable por trabajador | parcial | — | — | — | ✓ | — | **× falta** |
| Detección de anomalías / outliers | parcial | — | ✓ | — | — | — | **× falta** |
| Histórico app empleado | ✓ | ✓ | ✓ | — | ✓ | parcial (admin only) | × parcial |
| Audit log de cambios config | ✓ | ✓ | ✓ | ✓ | ✓ | — | × futuro |
| Idempotencia distribución | ? | ? | ? | ? | ? | **✓** | ventaja Harmoni |
| Atomicidad transaccional | ✓ | ✓ | ✓ | ✓ | ✓ | **✓** | ventaja Harmoni |
| Multi-tenant por empresa | ✓ | ✓ | ✓ | ✓ | ✓ | **✓** | ventaja Harmoni |

### Top 10 insights

1. **Equidad temporal es estándar mundial**: ningún payroll moderno reparte solo por cargo sin considerar horas. Harmoni se quedó corto en esto.
2. **Separación cash/card es obligatoria fiscalmente** en US (Form 8027) y mejor práctica universal para auditoría.
3. **Tip-out FOH→BOH es la práctica más extendida** en US (70/15/10/5); Harmoni hoy lo simula manualmente cambiando puntos de cocina.
4. **Service charge vs gratuity tiene tratamientos legales OPUESTOS** (US wages vs Perú no-remunerativo). Confundirlos genera contingencias.
5. **Reporte PDF firmado por trabajador es la herramienta de auditoría #1** para defensa ante SUNAFIL/DOL/HMRC.
6. **Detección de anomalías reduce disputas un 60%** según TipHaus (server con dist << promedio de su cargo → manager revisa).
7. **Frecuencia diaria de payout es ventaja competitiva** (Kickfin escaló por esto). Mensual ya no es estándar.
8. **El troncmaster UK es un patrón replicable**: separación de quien controla la distribución vs quien administra la planilla → más confianza del staff.
9. **Multi-tenant atomicidad + idempotencia**: Harmoni tiene ventaja arquitectural sobre Toast (single-tenant rígido).
10. **Política firmada al onboarding** + reconfirmación en cambios → primer pilar legal. Harmoni puede aprovechar el portal trabajador existente.

---

## 5. Recomendaciones priorizadas para Harmoni

### Implementadas en esta iteración (2026-05-25)

1. **Modo `POOL_PUNTOS_HORAS`** — Distribución híbrida: `puntos × horas` (estado del arte).
2. **`POOL_HORAS`** — Reparto puro por horas trabajadas (per-hour rate, modo más justo para equipos homogéneos).
3. **Separación `monto_cash` y `monto_card`** en `PoolPropinas` para reporting tributario claro.
4. **Tip-out automático FOH → BOH** vía `porcentaje_tipout_bot` en config.
5. **Reporte PDF "Acta de Distribución"** con desglose por trabajador, sección de firma y QR de verificación.
6. **Detección de anomalías** — flag `anomalia=True` en `DistribucionPropinas` cuando monto < 50% del promedio del cargo.

### Para iteraciones futuras

- **Audit log de cambios** en `ConfiguracionPropinas` (quién cambió qué puntos cuándo).
- **Portal trabajador**: histórico de propinas recibidas, comparativo vs equipo.
- **Política firmable** en onboarding del trabajador (similar al consentimiento de boleta electrónica).
- **Service charge ≠ tip**: campo separado en `PoolPropinas` para `monto_service_charge` (cuando aplique al cliente).
- **Pagos diarios** vía batch transfers (BCP/BBVA APIs) si el cliente lo requiere.
- **App móvil del trabajador** con visualización en vivo del pool del turno.

---

## 6. Fuentes

- [How to Handle Tip Pooling Payroll Compliance for Restaurants in 2026 — Netchex](https://netchex.com/blog/how-to-handle-tip-pooling-payroll-compliance-for-restaurants-in-2026/)
- [Toast Payroll: Manage and Integrate Tips](https://support.toasttab.com/en/article/Toast-Payroll-Tip-Processing)
- [Get Started With Toast Tips Manager](https://central.toasttab.com/s/article/Getting-Started-with-Toast-Tips-Manager-How-to-Pool-Share-Tips)
- [Tip Pooling for Toast POS — 7shifts](https://kb.7shifts.com/hc/en-us/articles/13166056874771-Tip-Pooling-for-Toast-POS)
- [7shifts 101: Tip Pooling](https://kb.7shifts.com/hc/en-us/articles/4417505157779-7shifts-101-Tip-Pooling)
- [Tip Pooling Calculator — 7shifts](https://www.7shifts.com/resources/templates/tip-pooling-calculator/)
- [Restaurant Tip Outs Guide — 7shifts](https://www.7shifts.com/blog/restaurant-tipping-out-guide/)
- [DOL Fact Sheet #15: Tipped Employees (FLSA)](https://www.dol.gov/agencies/whd/fact-sheets/15-tipped-employees-flsa)
- [DOL Tip Regulations Under FLSA](https://www.dol.gov/agencies/whd/flsa/tips)
- [2026 Restaurant Tip Credit Guide — Uncle Kam](https://unclekam.com/tax-strategy-blog/2026-restaurant-tip-credit-complete-guide-to-flsa-rules-legal-compliance-and-tipping-culture-impact/)
- [Fifth Circuit Strikes Down DOL Tip Credit Rule — Jackson Lewis](https://www.jacksonlewis.com/insights/fifth-circuit-strikes-down-dol-tip-credit-rule-what-it-means-employers)
- [Restaurant Tronc & Tips Guide 2026 — Stored](https://www.joinstored.com/blogs/restaurant-tronc-and-tips)
- [What Is Tronc? — Supy](https://supy.io/blog/what-is-tronc-the-clear-guide-to-tronc-meaning-tip-distribution-service-charge-in-uk-hospitality)
- [New UK Tipping Law: Employment (Allocation of Tips) Act 2023](https://klglaw.co.uk/new-uk-tipping-law-what-the-employment-allocation-of-tips-act-2023-means-for-restaurants-and-staff/)
- [Tronc Payments for Hospitality Employees — IRIS](https://www.iris.co.uk/products/tronc-payroll/)
- [Square Payroll Tip Importing](https://squareup.com/help/us/en/article/6480-square-payroll-tip-importing)
- [How to Process Payroll for Tipped Employees — Square](https://squareup.com/us/en/the-bottom-line/operating-your-business/how-to-process-payroll-for-tipped-employees)
- [Tipped Employees 101: Cash vs Credit Card Tips — Valor Payroll](https://valorpayrollsolutions.com/blog/tipped-employees-101-how-to-properly-report-and-tax-cash-vs-credit-card-tips-as-an-employer/)
- [IRS Form 8027: Annual Tip Income Report — Fincent](https://fincent.com/irs-tax-forms/form-8027)
- [IRS Tip Recordkeeping and Reporting](https://www.irs.gov/businesses/small-businesses-self-employed/tip-recordkeeping-and-reporting)
- [Tipping Out — Homebase](https://www.joinhomebase.com/blog/tipping-out)
- [Restaurant Tip-Out Chart 2026 — Gratuity Solutions](https://gratuitysolutions.com/blog/restaurant-tip-out-chart)
- [Understanding Tip Out — Toast](https://pos.toasttab.com/blog/on-the-line/tip-out)
- [Kickfin vs TipHaus comparison](https://kickfin.com/blog/kickfin-vs-tiphaus/)
- [TipHaus vs Kickfin 2026](https://www.tiphaus.com/blog/tiphaus-vs-kickfin/)
- [FICA and FLSA tip credits — Gusto](https://support.gusto.com/article/112472520100000/FICA-and-FLSA-tip-credits)
- [Tip wages, distributed service charges, tip credits — Gusto](https://gusto.rightanswers.com/portal/app/portlets/results/viewsolution.jsp?solutionid=112472520100000)
- [Restaurant Payroll Services — Gusto](https://gusto.com/product/solutions/industry/restaurant)
- [Understanding Tax on Gratuity vs Service Charge — Paychex](https://www.paychex.com/articles/payroll-taxes/tips-and-service-charges)
- [Automatic Gratuity: Is It Legal — WebstaurantStore](https://www.webstaurantstore.com/blog/4328/automatic-gratuity-law.html)
- [Automatic Gratuity, Explained — 7shifts](https://www.7shifts.com/blog/restaurant-auto-gratuity/)
- [What Automatic Gratuity Means — Toast](https://pos.toasttab.com/blog/on-the-line/automatic-gratuity)
- [2026 Tip Compliance Checklist — Restaurant365](https://www.restaurant365.com/blog/2026-tip-compliance-checklist-avoid-costly-fines-and-payroll-errors/)
- [SUNAT: recargo al consumo y propinas — Gestión](https://gestion.pe/economia/sunat-preciso-recargo-consumo-propinas-consideran-ingresos-restaurantes-hospedajes-63347-noticia/)
- [Recargo al consumo: propina obligatoria — LP Derecho](https://lpderecho.pe/recargo-consumo-propina-camuflada-obligatoria-restaurantes-hoteles/)
- [Tip Pooling vs Tip Sharing — 7shifts](https://www.7shifts.com/blog/tip-pooling-vs-tip-sharing/)
- [How to Split Tips by Hours — OysterLink](https://oysterlink.com/spotlight/how-to-split-tips-by-hours-formula/)
