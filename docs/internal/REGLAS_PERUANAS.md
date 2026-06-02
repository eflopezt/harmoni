# Reglas Peruanas — Normativa Laboral aplicada en Harmoni ERP

> **Última revisión:** 2026-05-24
> **Alcance:** Régimen laboral privado (D.Leg. 728). Esta guía documenta la base legal exacta y la fórmula que aplica cada módulo de cálculo del ERP. Todo cambio de tasas/parámetros debe reflejarse aquí y en `ConfiguracionSistema`.
> **Conjunto autoritativo:** Cuando la documentación y el código difieran, el código (`nominas/engine.py`, `asistencia/services/he_calculator.py`) es la fuente de verdad operativa — actualizar este archivo en simultáneo.

---

## 1. Resumen ejecutivo (cheat sheet)

### Parámetros vigentes Q2 2026

| Parámetro | Valor 2026 | Base legal | Constante en código |
|-----------|-----------|------------|---------------------|
| **RMV** (Remuneración Mínima Vital) | S/ 1,130.00 | D.S. 006-2024-TR | `nominas/engine.py::RMV_2026` |
| **UIT** | S/ 5,500.00 | D.S. 233-2025-EF | `nominas/engine.py::UIT_2026` |
| **Tope RMA AFP** (prima seguro) | S/ 12,131.49 | SBS, cuatrimestral | `nominas/engine.py::AFP_TOPE_REM_ASEGURABLE` |
| **Asignación familiar** | S/ 113.00 (10% RMV) | Ley 25129 | `nominas/engine.py::ASIG_FAM` |
| **Jornada legal máxima** | 48 h/semana, 8 h/día | D.Leg. 854 + Art. 25 Const. | `he_calculator.py` jornadas configurables |

### Aportes y descuentos (régimen privado)

| Concepto | Tasa | Tope | Quién paga | Base legal |
|----------|------|------|-----------|------------|
| ESSALUD regular | 9.00% | sin tope | empleador | Ley 26790 art. 6 |
| ESSALUD con EPS | 6.75% efectivo | sin tope | empleador | Ley 26790 art. 15 (crédito 25%) |
| ONP (SNP) | 13.00% | sin tope | trabajador | D.L. 19990 |
| AFP aporte obligatorio | 10.00% | sin tope | trabajador | D.L. 25897 |
| AFP comisión por flujo | 1.47% – 1.69% | sin tope | trabajador | Tabla SBS (varía por AFP) |
| AFP prima de seguro | 1.74% | RMA S/ 12,131.49 | trabajador | SBS, uniforme las 4 AFP |
| SCTR Salud | desde 0.53% | sin tope | empleador | Ley 26790 + D.S. 003-98-SA |
| SCTR Pensión | desde 1.23% | sin tope | empleador | Ley 26790 + D.S. 003-98-SA |
| Bonif. extraordinaria grati (ESSALUD) | 9.00% | sin tope | empleador | Ley 30334 (permanente) |
| Bonif. extraordinaria grati (EPS) | 6.75% | sin tope | empleador | Ley 30334 + Ley 26790 |

### Recargos de Horas Extra (sobretiempo)

| Tipo | Recargo | Cuándo | Implementado en |
|------|---------|--------|----------------|
| HE 25% | +25% | 1ra y 2da hora de sobretiempo | `engine.py::calcular_he('HE_25')` |
| HE 35% | +35% | 3ra hora en adelante + nocturno (22:00–06:00) | `engine.py::calcular_he('HE_35')` |
| HE 100% | doble (×2) | Descanso semanal o feriado laborado | `engine.py::calcular_he('HE_100')` |

### Beneficios anuales

| Beneficio | Cuándo | Cuánto | Base legal |
|-----------|--------|--------|------------|
| Gratificación julio | hasta 15-jul | 1 sueldo computable + 9%/6.75% bonif | Ley 27735 + Ley 30334 |
| Gratificación diciembre | hasta 15-dic | 1 sueldo computable + 9%/6.75% bonif | Ley 27735 + Ley 30334 |
| CTS mayo | hasta 15-may | semestre nov-abr | D.Leg. 650 |
| CTS noviembre | hasta 15-nov | semestre may-oct | D.Leg. 650 |
| Vacaciones | 30 días/año | 1 sueldo del mes | D.Leg. 713 |

---

## 2. Remuneración Mínima Vital (RMV) y jornada legal

### 2.1 RMV S/ 1,130 — D.S. 006-2024-TR

- Vigente desde **1 de enero 2025**.
- Es el piso de toda remuneración mensual en régimen privado a jornada completa.
- Sirve de base para: asignación familiar (10% RMV), bono nocturno (RMV nocturna ≥ RMV +35%), tope SCTR mínimo, y régimen de microempresa. (La inembargabilidad NO usa la RMV: son 5 URP = 5 × 10% UIT.)
- En código: `nominas/engine.py::RMV_2026` (fallback) y `ConfiguracionSistema.rmv_valor` (override por admin).

### 2.2 Jornada de trabajo 48h/semana — D.Leg. 854 + Art. 25 Constitución

- **Máximo 8 horas diarias** o **48 horas semanales** — lo que sea favorable al trabajador.
- Distribuible en jornadas atípicas siempre que el promedio del ciclo respete las 48 horas.
- Refrigerio: **mínimo 45 minutos**, no computa dentro de la jornada (Ley 27671 art. 7).
- Descanso semanal obligatorio: **24 horas continuas**, preferentemente domingo (D.Leg. 713 art. 1).
- Trabajo nocturno (22:00–06:00): la remuneración no puede ser inferior a **RMV + 35%** (RMV nocturna).
- Implementación: `asistencia/services/he_calculator.py::obtener_jornada_diaria` — jornadas LOCAL (8.5h L-V, 5.5h sáb) y FORÁNEO (11h L-S, 4h dom), configurables en `ConfiguracionSistema`.

---

## 3. Horas Extra / Sobretiempo

### 3.1 Base legal

- **Ley 27671** + **D.S. 008-2002-TR** + **D.S. 004-2006-TR** (régimen general).
- **D.Leg. 713 art. 3, 4, 9** (descanso semanal y feriado laborados).
- **D.Leg. 854** (jornada de 48h máxima).

### 3.2 Recargos

| Recargo | Cuándo aplica |
|---------|---------------|
| **+25%** | Primeras 2 horas de sobretiempo en día laborable |
| **+35%** | A partir de la 3ra hora y en jornada nocturna (22:00–06:00) |
| **+100%** (doble) | Trabajo en descanso semanal o feriado, sin descanso sustitutorio |

### 3.3 Fórmula y ejemplo

```
valor_hora        = sueldo_mensual / 30 / 8
monto_HE_25       = horas_25 × valor_hora × 1.25
monto_HE_35       = horas_35 × valor_hora × 1.35
monto_HE_100      = horas_100 × valor_hora × 2.00
```

**Ejemplo:** sueldo S/ 3,000, 2h al 25%, 1h al 35%, 4h al 100% en feriado.

- valor_hora = 3000/30/8 = **S/ 12.50**
- HE 25%: 2 × 12.50 × 1.25 = **S/ 31.25**
- HE 35%: 1 × 12.50 × 1.35 = **S/ 16.88**
- HE 100%: 4 × 12.50 × 2.00 = **S/ 100.00**

### 3.4 Notas críticas

- HE son **voluntarias** (acuerdo trabajador-empleador); el empleador no puede exigirlas salvo emergencia.
- Si hay **papeleta de compensación aprobada** (D.Leg. 713 art. 6), el feriado/domingo laborado se compensa con día libre y NO genera HE 100%.
- **Tope auditoría:** 4 h/día × 15 días = 60 h/mes (no bloqueante; `engine.py::TOPE_HE_MES`).
- HE son **REMUNERATIVAS**: afectan grati, CTS, vacaciones y aportes AFP/ONP/ESSALUD/IR 5ta.

### 3.5 Referencia en código

- `asistencia/services/he_calculator.py::calcular_he_componentes` — función pura núcleo.
- `asistencia/services/he_calculator.py::calcular_he_para_registro` — wrapper UI calendario.
- `nominas/engine.py::valor_hora`, `calcular_he` — cálculo monetario para boleta.

---

## 4. Descanso semanal trabajado (DSL) y feriado laborado (FL)

### 4.1 Base legal

- **D.Leg. 713 art. 3 y 4**: descanso semanal obligatorio de 24 horas.
- **D.Leg. 713 art. 9**: feriados no laborables — si se trabajan sin descanso sustitutorio, se pagan con recargo del 100%.

### 4.2 Reglas

- **Día normal trabajado en descanso semanal (DSL)** → pago doble (sueldo del día + 100% recargo).
- **Feriado laborado (FL)** → triple efectivo (sueldo del día regular + sueldo del día como feriado + 100% recargo), salvo descanso sustitutorio en los próximos 7 días.
- En Harmoni el código de tareo `DSL` y `FL` fuerzan que TODAS las horas se contabilicen al 100% (`he_calculator.py` líneas 184-199).
- Si hay **papeleta de compensación APROBADA** se procesa como día normal (tiene `tiene_papeleta_comp=True` en el cálculo).

### 4.3 Referencia en código

- `asistencia/services/he_calculator.py::CODIGOS_SIN_HE` — `DSL`, `FL` se tratan especialmente.
- Códigos de tareo `DL` (descanso laborable), `DLA` (descanso laborado anticipado): se pagan sin HE.

---

## 5. Permisos y licencias (LCG / LF / LP / LSG)

### 5.1 Códigos de tareo

| Código | Descripción | Pagado | Base legal |
|--------|-------------|--------|-----------|
| `LCG` | Licencia con goce | sí (remunerativo) | Convenio o D.Leg. 728 art. 56 |
| `LSG` | Licencia sin goce | no | Acuerdo entre partes |
| `LF`  | Licencia por fallecimiento (luto) | sí (3-5 días) | Convenio colectivo / costumbre |
| `LP`  | Licencia por paternidad | sí (10 días naturales) | Ley 29409 + Ley 30807 |
| `FA`  | Falta injustificada | no | Descuento sueldo + posible falta grave |
| `TR`  | Tardanza | parcial | Descuento proporcional |
| `CDT` | Compensación día trabajado | sí | D.Leg. 713 art. 6 |

### 5.2 Notas

- **Licencia por paternidad:** Ley 29409 (ampliada por Ley 30807 a 10 días calendario contados desde el nacimiento o desde alta hospitalaria del recién nacido).
- **Licencia por maternidad:** Ley 26644 + Ley 30367 → 98 días (49 pre + 49 post; ver §10).
- Implementación: ninguno de estos códigos genera HE (están en `CODIGOS_SIN_HE`).

---

## 6. Gratificación legal de julio y diciembre

### 6.1 Base legal

- **Ley 27735** (régimen general) + **D.S. 005-2002-TR** (reglamento).
- **Ley 29351** + **Ley 30334**: bonificación extraordinaria por inafectación de aportes a la grati (permanente).

### 6.2 Fórmula

```
gratificación = (sueldo_base + asig_familiar + promedio_remuneraciones_regulares) × meses_trabajados / 6
bonif_extraordinaria = gratificación × 9%          ← si está en ESSALUD regular
bonif_extraordinaria = gratificación × 6.75%       ← si está afiliado a EPS
total_a_pagar_julio = gratificación + bonif_extraordinaria
```

### 6.3 Inafectaciones (Ley 29351)

- La gratificación NO está afecta a aportes AFP/ONP ni a IR 5ta (Art. 18 TUO LIR).
- ESSALUD 9% sigue afectando, pero ese monto se entrega al trabajador como **bonificación extraordinaria** (no se descuenta).
- Si el trabajador tiene EPS, la bonif. baja a 6.75% (porque el aporte ESSALUD efectivo del empleador es 6.75%, no 9%).

### 6.4 Ejemplo

Trabajador con sueldo S/ 3,000, asig fam S/ 113, 6 meses completos, sin EPS:

- Grati = (3000 + 113) × 6/6 = **S/ 3,113.00**
- Bonif extra = 3113 × 9% = **S/ 280.17**
- **Total a pagar:** S/ 3,393.17

### 6.5 Referencia en código

- `nominas/engine.py::calcular_gratificacion`
- `nominas/engine.py::BONIF_EXTRAORDINARIA_TASA` (9%) y `BONIF_EXTRAORDINARIA_TASA_EPS` (6.75%)

---

## 7. CTS — Compensación por Tiempo de Servicios

### 7.1 Base legal

- **D.Leg. 650** (TUO) + **D.S. 004-97-TR** (reglamento).
- **Ley 27006** y modificatorias sobre depósitos semestrales.

### 7.2 Fórmula

```
remuneración_computable = sueldo + asig_familiar + 1/6 × última_grati
depósito_semestral      = rem_computable × meses_completos / 12
                        + rem_computable × días_sueltos / 360
```

Dos depósitos al año:
- **Hasta 15-may** (semestre noviembre–abril).
- **Hasta 15-nov** (semestre mayo–octubre).

### 7.3 Características

- Es **intangible** salvo retiro voluntario hasta el 100% del excedente sobre 4 sueldos (ley vigente prorrogada).
- El empleador **NO descuenta CTS** del trabajador — se deposita directamente en el banco que el trabajador elige.
- Acumula desde el primer día. Trabajadores con < 1 mes no generan CTS.

### 7.4 Referencia en código

- `nominas/engine.py::calcular_prov_gratif` (helper común con grati)
- Cálculo CTS detallado: rutinas dentro de `calcular_registro` (provisión mensual `prov-cts`).

---

## 8. Vacaciones anuales

### 8.1 Base legal

- **D.Leg. 713** + **D.S. 012-92-TR**.

### 8.2 Reglas

- **30 días calendario** de descanso después de 1 año completo de servicios + récord vacacional.
- **Récord vacacional**:
  - Jornada 6 días/semana: 260 días efectivos en el año.
  - Jornada 5 días/semana: 210 días efectivos.
- **Remuneración vacacional** = sueldo del mes en que se goza (no se duplica, salvo trabajadores que no las tomaron en plazo legal).
- **Vacaciones truncas al cese**: proporcional `30/360 × días_trabajados`.
- **Triple sueldo** si no se goza dentro del año siguiente al de adquisición (D.Leg. 713 art. 23): 1 sueldo vacacional + 1 sueldo por no haber descansado + 1 indemnización.

### 8.3 Aumento retroactivo afecta vacaciones

Si se aplica un aumento retroactivo (ver §15) y el trabajador ya gozó vacaciones con sueldo anterior, corresponde **reintegro vacacional** por la diferencia (D.Leg. 713 art. 16).

---

## 9. Subsidio por Incapacidad Temporal (descanso médico)

### 9.1 Base legal

- **Ley 26790** (Ley de Modernización de la Seguridad Social en Salud).
- Reglamento + circulares ESSALUD.

### 9.2 Reglas

| Días | Quién paga | Naturaleza |
|------|-----------|------------|
| Día 1 – 20 | **Empleador** | Remuneración íntegra — **REMUNERATIVO** (afecta aportes) |
| Día 21 – 340 (11m10d) | **ESSALUD** | Subsidio — **NO REMUNERATIVO** |
| > 340 días | No pagable | Tope legal alcanzado |

### 9.3 Cálculo

```
valor_diario = promedio_remuneraciones_últimos_12_meses / 360
             ≈ sueldo_mensual / 30                          (simplificación práctica)
subsidio_essalud = valor_diario × días_subsidio_essalud
```

### 9.4 Trámite

- Médico de ESSALUD emite **Certificado de Incapacidad Temporal del Trabajo (CITT)**.
- Empleador adelanta los primeros 20 días.
- Para días 21+: empleador presenta CITT + Formulario 8001 a ESSALUD y solicita reembolso.

### 9.5 Referencia en código

- `nominas/engine.py::calcular_subsidio_incapacidad`

---

## 10. Subsidio por Maternidad

### 10.1 Base legal

- **Ley 26790** + **Ley 30367** (ampliación a 98 días).
- **D.U. 005-2011** (regulación complementaria).

### 10.2 Reglas

- **98 días** de descanso: 49 pre-natales + 49 post-natales.
- **Parto múltiple o discapacidad del recién nacido:** +30 días adicionales.
- Pagado por **ESSALUD** — NO remunerativo.
- Requisito de calificación: **3 meses consecutivos o 4 alternados** de aportes en los 6 meses previos (Ley 26790 art. 12).
- Empleador adelanta el subsidio y solicita reembolso a ESSALUD.

### 10.3 Fórmula

```
valor_diario  = sueldo_mensual / 30                          (simplificación)
subsidio_total = valor_diario × 98
```

### 10.4 Referencia en código

- `nominas/engine.py::calcular_subsidio_maternidad`

---

## 11. SCTR — Seguro Complementario de Trabajo de Riesgo

### 11.1 Base legal

- **Ley 26790** art. 19.
- **D.S. 003-98-SA** (Reglamento — define actividades de riesgo y prestaciones).
- **Resoluciones SBS** para primas mínimas.

### 11.2 Quién está obligado

Empleadores cuya actividad principal o accesoria figure en el **Anexo 5 del D.S. 009-97-SA** como **actividad de alto riesgo**: minería, construcción civil, manufactura pesada, transporte de carga, agroindustria, pesca, energía, etc.

### 11.3 Estructura

| Cobertura | Quién emite | Tasa referencial mínima |
|-----------|------------|------------------------|
| **SCTR Salud** | ESSALUD o EPS | desde 0.53% |
| **SCTR Pensión** | ONP o aseguradora privada | desde 1.23% |

La tasa exacta la fija la aseguradora según el **nivel de riesgo** del puesto (clasificación CIIU + historial siniestral).

### 11.4 Características

- Es **íntegramente costo del empleador** (no descuenta al trabajador).
- Obligatorio incluso para trabajadores administrativos si están expuestos al riesgo (visitas a obra, planta, etc.).
- Cobertura: invalidez/sobrevivencia + atención médica por accidente de trabajo o enfermedad profesional.
- No reemplaza a ESSALUD ni a AFP/ONP regulares — es **adicional**.

### 11.5 Referencia en código

- Aún no calculado automáticamente — registro manual vía `otros_descuentos`/`otros_ingresos` o como concepto custom en `ConceptoRemunerativo`. Pendiente para futuro release.

---

## 12. AFP — Sistema Privado de Pensiones

### 12.1 Base legal

- **D.L. 25897** (Ley del SPP).
- **Resoluciones SBS** trimestrales (tasas de comisión y prima de seguro).

### 12.2 Estructura del descuento al trabajador

| Componente | Tasa | Tope | Notas |
|-----------|------|------|-------|
| **Aporte obligatorio** | 10.00% | sin tope | Va a la CIC (Cuenta Individual de Capitalización) |
| **Comisión por flujo** | 1.47% – 1.69% | sin tope | Varía por AFP (Habitat más baja, Profuturo más alta) |
| **Prima de seguro** | 1.74% | **RMA S/ 12,131.49** | Uniforme las 4 AFP. Tope publicado por SBS |

### 12.3 Tasas Q2 2026 (vigentes abr–jul 2026)

| AFP | Comisión flujo | Prima seguro |
|-----|---------------|--------------|
| Habitat | 1.47% | 1.74% |
| Integra | 1.55% | 1.74% |
| Prima | 1.60% | 1.74% |
| Profuturo | 1.69% | 1.74% |

Fuente: Resolución SBS publicada cuatrimestralmente. Override en `ConfiguracionSistema.afp_tasas_override`.

### 12.4 Régimen mixto vs. flujo

- **Comisión por flujo** (descrita arriba): se cobra sobre la remuneración del mes. Es lo único vigente para nuevos afiliados desde 2013.
- **Comisión mixta**: combinación de tasa de flujo (decreciente) + tasa sobre saldo. Solo aplica para afiliados que ya estaban antes de la reforma 2013 y se quedaron en mixta. La SBS hizo migración compulsiva en 2014; hoy hay muy pocos casos.

### 12.5 Referencia en código

- `nominas/engine.py::AFP_TASAS`, `AFP_APORTE`, `AFP_TOPE_REM_ASEGURABLE`
- `nominas/engine.py::_get_tasas_afp`, `_get_tope_rma`

---

## 13. ONP — Sistema Nacional de Pensiones

### 13.1 Base legal

- **D.L. 19990** (Ley del SNP).
- Modificatorias posteriores (Ley 28991, Ley 29951).

### 13.2 Tasa

- **13.00% único** sobre la remuneración bruta, **sin tope** (desde 2013; previamente había topes).

### 13.3 Características

- Pagado por el trabajador, descontado de la planilla, declarado por el empleador en PLAME.
- **Mínimo 20 años** de aportes para acceder a pensión de jubilación general.
- Trabajador puede cambiarse de ONP a AFP en cualquier momento, pero NO al revés (salvo casos de la Ley 28991).

### 13.4 Referencia en código

- `nominas/engine.py::ONP_TASA = Decimal('13.00')`

---

## 14. IR 5ta Categoría

### 14.1 Base legal

- **TUO Ley del Impuesto a la Renta** art. 53 (escala) y 75 (retención).
- **R.S. 010-2006/SUNAT** (procedimiento de retención mensual).

### 14.2 Escala progresiva 2026 (sobre lo que excede 7 UIT)

| Tramo (UIT) | Tramo (S/) | Tasa |
|-------------|-----------|------|
| Hasta 5 UIT | hasta 27,500 | 8% |
| 5 a 20 UIT | 27,501 – 110,000 | 14% |
| 20 a 35 UIT | 110,001 – 192,500 | 17% |
| 35 a 45 UIT | 192,501 – 247,500 | 20% |
| Más de 45 UIT | > 247,500 | 30% |

- **UIT 2026:** S/ 5,500 (D.S. 233-2025-EF).
- **Deducción 7 UIT anual:** S/ 38,500.

### 14.3 Método de retención (R.S. 010-2006/SUNAT)

1. Proyectar la **remuneración anual** = sueldo × meses restantes (incluido actual) + variables ya percibidas + gratificaciones que falten cobrar.
2. Restar 7 UIT + aporte EPS del trabajador.
3. Aplicar la escala progresiva → **impuesto anual proyectado**.
4. Dividir entre los meses restantes (incluido el actual) → **retención del mes**.

### 14.4 Inafectaciones relevantes

- **Gratificaciones** (Art. 18 TUO LIR): inafectas al IR 5ta.
- **CTS**: inafecta.
- **Subsidios ESSALUD** (incapacidad, maternidad días 21+): inafectos por no ser remunerativos.

### 14.5 Referencia en código

- `nominas/engine.py::IR_5TA_ESCALA`, `IR_5TA_DEDUCCION_UITS`
- `nominas/engine.py::_calcular_ir_5ta_legacy` y `_calcular_ir_5ta_sunat` (toggle por `ConfiguracionSistema.usar_metodo_sunat_ir5ta`).

---

## 15. Reintegros y aumento retroactivo

### 15.1 Base legal

- **D.S. 003-97-TR** art. 6 (TUO LPCL) + Ley 27735 + D.Leg. 650 art. 9 + D.Leg. 713 art. 16.
- **SUNAT R. 183-2011** (registro en PLAME del período de pago).

### 15.2 Cómo se calcula

1. **Bruto a reintegrar** = monto correcto – monto pagado, por cada período afectado.
2. Recalcular **aportes del trabajador** sobre el bruto:
   - AFP/ONP (~13% según régimen)
   - EPS (si aplica)
   - IR 5ta (proyección anual con el bruto adicional)
3. Recalcular **aportes empleador**: ESSALUD 9% (o 6.75% con EPS), SCTR si aplica.
4. **Neto** = bruto – aportes trabajador.
5. **Costo empresa** = bruto + ESSALUD + SCTR.

### 15.3 Conceptos derivados afectados

- **Gratificación** del semestre (Ley 27735): el sueldo computable cambia.
- **CTS** del semestre (D.Leg. 650 art. 9): depósito sube.
- **Vacaciones** ya gozadas o por gozar (D.Leg. 713 art. 16): remuneración vacacional debe igualar el sueldo a la fecha de goce.

### 15.4 Registro en PLAME

- Se reporta **en la planilla del mes de pago**, no en el mes de origen.
- Código de concepto "reintegro" con campo "período tributario al que corresponde".

### 15.5 Referencia en código

- `nominas/engine_reintegros.py` — motor especializado.
- Entradas RAG: "Reintegro de remuneración" + "Aumento de sueldo retroactivo".

---

## 16. Asignación Familiar

### 16.1 Base legal

- **Ley 25129** (mayo 1989).

### 16.2 Regla

- **Monto:** 10% de la RMV → **S/ 113.00** en 2026.
- **Condición:** trabajador con al menos un **hijo menor de 18 años**, o hasta 24 si cursa estudios superiores.
- **Régimen:** privado (D.Leg. 728).
- Es **REMUNERATIVO**: afecta grati, CTS, vacaciones y todos los aportes.
- Trabajador debe presentar partida de nacimiento del hijo para activarla.

### 16.3 Referencia en código

- `nominas/engine.py::ASIG_FAM = RMV_2026 × 0.10`

---

## 17. Embargo y pensión alimenticia

### 17.1 Base legal

- **Art. 648 del Código Procesal Civil**.

### 17.2 Reglas

**Inembargable:**
- Hasta **5 URP**. La URP (Unidad de Referencia Procesal) = **10% de la UIT**
  (fijada por el Poder Judicial), **NO** la RMV. 2026: UIT 5,500 → URP 550 →
  **5 URP = S/ 2,750**.

**Embargable sobre el exceso:**
- **Deudas civiles**: hasta **1/3** (33.33%) del exceso sobre 5 URP.
- **Pensión alimenticia**: hasta **60%** de la remuneración total — Art. 648 inc. 5 CPC.

### 17.3 Ejemplos

**Embargo civil sueldo S/ 8,000:**
- Inembargable: 2,750 → Exceso: 5,250 → Máximo embargable: 5,250/3 = **S/ 1,750.00**

**Pensión alimenticia 30% sueldo S/ 3,000:**
- Base = sueldo – descuentos legales (AFP/ONP, IR 5ta) = 3000 − 600 = 2400
- Pensión = 2400 × 30% = **S/ 720**

### 17.4 Referencia en código

- `nominas/engine.py::calcular_embargo_civil`
- `nominas/engine.py::calcular_pension_alimenticia`
- `nominas/engine.py::valor_he_banco_no_compensadas` (deuda de HE del banco pagada al cese)

---

## 18. Boleta de pago electrónica

### 18.1 Base legal

- **D.S. 009-2011-TR**.

### 18.2 Datos obligatorios

- Empresa: razón social, RUC, dirección.
- Trabajador: nombres, DNI, cargo, fecha de ingreso, sistema pensionario.
- Período (mes/año).
- Ingresos, descuentos, aportes empleador, neto a pagar.

### 18.3 Acuse de recibo

- Firma digital o física por el trabajador dentro del mes siguiente al pago.
- Locales con < 3 trabajadores: el empleador firma en lugar del trabajador (art. 18-A).
- Conservación: **5 años** (Art. 18 — plazo SUNAT/MTPE).

### 18.4 Referencia en código

- `nominas/pdf.py` — generación PDF de boleta.
- `templates/nominas/boleta_verificacion.html`.

---

## 19. Contratos: D.Leg. 728 vs. D.Leg. 1057 (CAS)

### 19.1 Régimen privado (D.Leg. 728 — TUO D.S. 003-97-TR)

Aplicado por Harmoni por defecto. Características:

- Aplica al sector privado.
- Beneficios completos: grati, CTS, vacaciones, asignación familiar, indemnización por despido arbitrario, AFP/ONP, ESSALUD.
- Modalidades: contrato a plazo indeterminado, plazo fijo (sujeto a modalidad), parcial.

### 19.2 CAS — Contrato Administrativo de Servicios (D.Leg. 1057)

- Régimen especial del sector público.
- Beneficios: vacaciones (30 días), aguinaldos (no equivalentes a grati), CTS desde 2020 (Ley 31131), ESSALUD, AFP/ONP.
- **Harmoni hoy no calcula nóminas CAS** — el ERP está orientado al D.Leg. 728.

### 19.3 Régimen MYPE (Microempresa — Ley 28015 / D.S. 013-2013-PRODUCE)

- Microempresa (< 10 trab., ventas ≤ 150 UIT): grati y CTS reducidas, vacaciones 15 días.
- Pequeña empresa: beneficios reducidos pero más amplios que micro.
- Harmoni soporta marcar régimen en `Empresa.regimen` (futuro release).

---

## 20. Tabla de referencia rápida — funciones del engine

| Concepto | Función / constante | Archivo |
|----------|---------------------|---------|
| Valor hora | `valor_hora(sueldo)` | `nominas/engine.py` |
| HE 25/35/100 monto | `calcular_he(horas, sueldo, tipo)` | `nominas/engine.py` |
| Subsidio incapacidad | `calcular_subsidio_incapacidad(...)` | `nominas/engine.py` |
| Subsidio maternidad | `calcular_subsidio_maternidad(...)` | `nominas/engine.py` |
| Pensión alimenticia | `calcular_pension_alimenticia(...)` | `nominas/engine.py` |
| Embargo civil | `calcular_embargo_civil(...)` | `nominas/engine.py` |
| Bonif. escolaridad | `calcular_bonif_escolaridad(...)` | `nominas/engine.py` |
| IR 5ta legacy | `calcular_ir_5ta_mensual(...)` | `nominas/engine.py` |
| IR 5ta SUNAT | `_calcular_ir_5ta_sunat(...)` | `nominas/engine.py` |
| Provisión grati | `calcular_prov_gratif(sueldo, asig)` | `nominas/engine.py` |
| Gratificación | `calcular_gratificacion(registro)` | `nominas/engine.py` |
| Reintegro | `engine_reintegros.calcular_reintegro_*` | `nominas/engine_reintegros.py` |
| HE componentes (asistencia) | `calcular_he_componentes(...)` | `asistencia/services/he_calculator.py` |
| Jornada del día | `obtener_jornada_diaria(...)` | `asistencia/services/he_calculator.py` |

---

## 21. Mantenimiento de este documento

- Actualizar la **fecha de última revisión** arriba.
- Si cambia una tasa, parámetro o base legal:
  1. Actualizar este archivo.
  2. Actualizar la constante en `nominas/engine.py` y/o el override en `ConfiguracionSistema`.
  3. Si el cambio afecta el RAG del agente IA, actualizar `nominas/agente_ia/rag.py`.
- Cualquier nueva entrada debe llevar **base legal con citación exacta** (Ley/D.Leg./D.S. con número y artículo).
