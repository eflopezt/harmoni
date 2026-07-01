# Regímenes Construcción Civil y Minería — Investigación y Diseño

> Documento de investigación + diseño arquitectónico para agregar a Harmoni el
> **Régimen de Construcción Civil (RCC)** y el **Régimen Minero**, con el
> **Roster Matricial** (jornadas atípicas 14x7 / 21x7) enlazado a la planilla.
>
> Fecha: 2026-06-30. Estado: propuesta (no implementado).

---

## 0. Resumen ejecutivo

- **RCC** es un régimen **rígido y estatutario**: sueldo por **categoría** (Operario/Oficial/Peón) desde tabla CAPECO-FTCCP, conceptos propios (BUC, BAE, altura, dominical), CTS y gratificaciones **distintas** al régimen general, pago **semanal**. Los softwares del mercado lo manejan como **planilla aparte**. → En Harmoni requiere: tabla de jornales por categoría + estrategia de cálculo propia + planilla semanal.
- **Minería** NO es un esquema rígido: es **régimen general + una capa configurable**. Lo único legal universal es el **Ingreso Mínimo Minero (RMV +25%)**, SCTR y la **jornada atípica acumulativa** (14x7). Los bonos (altitud, socavón/profundidad, alimentación, hospedaje) son **por convenio colectivo** → se modelan como **conceptos configurables**. → Encaja bien con el catálogo `ConceptoRemunerativo` actual + el Roster.
- **Roster Matricial**: ya modela 14x7/21x7 correctamente (`RegimenTurno.jornada_tipo=ACUMULATIVA`), pero **está desconectado del cálculo de planilla**. Cerrar esa brecha es el trabajo transversal que sirve a AMBOS regímenes (y a cualquier empresa foránea).

---

## 1. Marco normativo

### 1.1 Construcción Civil (Convención Colectiva CAPECO-FTCCP, R.M. 197-2025-TR)

Categorías y **jornal básico diario 2026**:

| Categoría | Jornal básico 2026 | BUC (% del básico) |
|-----------|--------------------|--------------------|
| Operario  | S/ 87.30 | 32% |
| Oficial   | S/ 68.50 | 30% |
| Peón      | S/ 61.65 | 30% |

Conceptos propios del régimen:

- **BUC** (Bonificación Unificada de Construcción): % del jornal básico según categoría (arriba). Reemplaza varios conceptos del régimen general.
- **BAE** (Bonificación por Alta Especialización): adicional para operarios especializados según especialidad.
- **Bono por altura**: **8%** del básico (2026, subió desde 7%).
- **Dominical**: pago del día de descanso semanal (domingo) sobre el jornal.
- **CTS**: **15%** del total de jornales básicos percibidos (incluye 3% de utilidades). NO es el esquema DL 650 del régimen general.
- **Gratificación**: **40 jornales** básicos (1/5 por mes laborado).
- **Asignación escolar**: **30 jornales/año** por hijo en edad escolar.
- **Compensación vacacional**: **10%** del jornal básico por día efectivo trabajado.
- **Movilidad**: incluida en el neto semanal.
- **Descuentos**: ONP **13%** + **CONAFOVICER 2%** (aporte vivienda, reemplaza otros).
- **Pago SEMANAL** (no mensual).
- Fondo de capacitación empleador: **0.45%** del jornal básico (2026, antes monto fijo).

Fuentes: [CAPECO-FTCCP 2026 (PDF)](https://www.capeco.org/descargas/CC2026/CAPECO_FTCCP_Remuneraciones%202026_%20FV.pdf) ·
[El Peruano — CC 2026](https://elperuano.pe/noticia/286045-construccion-civil-2026-revisa-si-te-corresponde-el-nuevo-aumento-del-jornal) ·
[Juris.pe — Régimen construcción civil](https://juris.pe/blog/regimen-laboral-construccion-civil-peru/) ·
[Tablas salariales 2026 (FTCCP)](https://www.ftccperu.com/media/attachments/2025/12/30/tablas-salariales-2026-construccion-civil.pdf)

### 1.2 Minería (D.S. 030-89-TR y convenios colectivos)

- **Ingreso Mínimo Minero**: no menor a **RMV + 25%** (piso legal). Aplica a obreros/empleados de minería, incluidos contratistas/subcontratistas.
- **SCTR obligatorio** (actividad de alto riesgo), nivel de riesgo elevado.
- **Jornada atípica/acumulativa** (14x7, 4x3, 12x9): permitida por la naturaleza especial. La **jornada promedio del ciclo no puede exceder el máximo legal**: horas totales del ciclo ÷ total de días (incluye descanso). Ej. 14x7 a 12h = 168h ÷ 21 días = **8h/día promedio**.
- **Bonos por altitud, trabajo en socavón/subterráneo/profundidad, alimentación, hospedaje, movilidad**: **NO son ley universal**, se pactan por **convenio colectivo** de cada empresa/sindicato. → Modelar como **conceptos configurables**, no como esquema fijo.

Fuentes: [Perú Contable — Guía régimen minero](https://www.perucontable.com/laboral/guia-completa-del-regimen-laboral-minero-normas-y-regulaciones-clave/) ·
[Perú Contable — Remuneración minera](https://www.perucontable.com/laboral/remuneracion-del-trabajador-minero/) ·
[Juris.pe — Jornadas atípicas/acumulativas](https://juris.pe/blog/conoce-jornadas-atipicas-acumulativas/) ·
[UDEP — Jornadas atípicas sector minero (PDF)](https://pirhua.udep.edu.pe/backend/api/core/bitstreams/de2aa862-b38e-4fc2-804e-114b814426de/content)

### 1.3 Cómo lo estructuran los softwares del mercado

- **RCC**: planilla **separada** (semanal), maestro de trabajadores **por categoría**, tabla de jornales editable por vigencia (cambia cada año por convenio), conceptos propios (BUC/BAE/altura/dominical), CTS 15% y gratificación de 40 jornales calculados aparte, aporte CONAFOVICER.
- **Minería**: planilla mensual del régimen general con **piso de ingreso mínimo minero**, **conceptos de convenio** parametrizables por empresa, y **roster/jornada acumulativa** que alimenta días y horas.

---

## 2. Estado actual de Harmoni (evidencia)

### 2.1 Lo que YA existe y sirve

- **Catálogo de conceptos configurable**: `ConceptoRemunerativo` (`nominas/models.py:36`) con `tipo`, `formula`, afectaciones (`afecto_cts`, `afecto_essalud`, ...), mapeo PLAME (`codigo_plame`), y `aplicar_automatico`. → Agregar BUC/BAE/altura/CONAFOVICER es **data**, no código.
- **Roster Matricial**:
  - `Roster` (`personal/models.py:1396`): 1 fila = persona × día, con `codigo` (T/D/DL/DLA/V/L/...), aprobación por celda.
  - `RegimenTurno` (`asistencia/models.py:24`): 14x7/21x7/5x2, `jornada_tipo` (ACUMULATIVA/SEMANAL/ROTATIVA/NOCTURNA), `dias_trabajo_ciclo`, `dias_descanso_ciclo`, y propiedades `ciclo_total_dias`, `horas_max_ciclo`.
  - `TipoHorario` (`asistencia/models.py:150`): entrada/salida por tipo de día.
  - Vista `roster_matricial()` (`personal/views/roster.py:70`) operativa.
  - `Personal.calcular_dias_libres_ganados()` (`personal/models.py:718`) lee el roster.
- **Campos de régimen en Personal**: `regimen_laboral` (`:619`, CharField libre), `regimen_turno` (`:624`, "14x7"), `condicion` (`:556`, FORANEO/LOCAL/LIMA), `grupo_tareo` (`:549`, STAFF/RCO), `jornada_horas` (`:610`).
- **Parámetros legales versionados**: `PeriodoNomina` congela `rmv_snapshot`, `uit_snapshot`, `parametros_snapshot`. SCTR y Vida Ley ya parametrizables en `ConfiguracionSistema`.

### 2.2 Las brechas (lo que falta)

1. **Motor de cálculo acoplado al régimen general** (`nominas/engine.py:667` `calcular_registro`): asignación familiar, HHEE, AFP/ONP, gratificación, CTS, IR 5ta hardcodeados a DL 728. **`Personal.regimen_laboral` no se usa en el cálculo.**
2. **Roster → Nómina DESCONECTADO**: `RegistroNomina.dias_trabajados` (`nominas/models.py:280`) es manual/hardcoded (default 30). El engine no lee `Roster` ni `RegimenTurno`.
3. **Sin promedio de jornada acumulativa**: `horas_max_ciclo` se calcula pero no se valida ni se usa como base de HHEE. En 14x7/21x7 no hay base correcta para horas extra.
4. **Descanso físico (DL/DLA) no impacta el sueldo**.
5. **Sin categorías OPERARIO/OFICIAL/PEÓN** (hoy `Personal.categoria` = NORMAL/CONFIANZA/DIRECCION) ni tabla de jornales CAPECO.
6. **`CruceTareoRoster`** (`asistencia/models.py:1060`) existe como estructura (Fase 2) pero sin ejecución automática.

---

## 3. Diseño propuesto

### 3.1 Modelo de régimen (base para todo)

- Convertir `Personal.regimen_laboral` a **choices**: `GENERAL`, `CONSTRUCCION_CIVIL`, `MINERIA` (extensible a `AGRARIO`, `MYPE`).
- Opcional: `Empresa.rubro` para default del régimen y validaciones.
- El engine selecciona la **estrategia** de cálculo según `regimen_laboral`.

### 3.2 Construcción Civil

Nuevos modelos:

```python
# nominas/models.py
class CategoriaConstruccion(models.TextChoices):
    OPERARIO = 'OPERARIO', 'Operario'
    OFICIAL  = 'OFICIAL',  'Oficial'
    PEON     = 'PEON',     'Peón'

class JornalConstruccion(models.Model):
    categoria      = models.CharField(max_length=20, choices=CategoriaConstruccion.choices)
    jornal_diario  = models.DecimalField(max_digits=8, decimal_places=2)
    buc_pct        = models.DecimalField(max_digits=5, decimal_places=2)   # 32 / 30
    vigencia_desde = models.DateField()
    vigencia_hasta = models.DateField(null=True, blank=True)
    fuente         = models.CharField(max_length=100, default='CAPECO-FTCCP')
    # unique por (categoria, vigencia_desde)
```

- Campo `Personal.categoria_construccion` (choices) usado solo si `regimen_laboral=CONSTRUCCION_CIVIL`.
- Conceptos (seed `seed_conceptos_construccion`): `buc`, `bae`, `bono-altura`, `dominical`, `cts-cc` (15%), `grati-cc` (40 jornales), `asig-escolar`, `comp-vacacional` (10%/día), `conafovicer` (2%, DESCUENTO).
- **Planilla semanal**: `PeriodoNomina.tipo = 'SEMANAL_CC'` (o `frecuencia`), sueldo = `jornal_diario × días_trabajados` (no `sueldo_base/30`).
- **Estrategia** `EstrategiaConstructor`: sobrescribe sueldo (jornal×día), BUC, dominical, CTS 15%, gratificación 40 jornales, CONAFOVICER; mantiene ONP/AFP e IR según reglas.

### 3.3 Minería

- **No** requiere modelos nuevos rígidos. Usa `ConceptoRemunerativo` para bonos de convenio: `ingreso-minimo-minero` (piso RMV+25%), `bono-altitud`, `bono-socavon`, `bono-profundidad`, `alimentacion`, `hospedaje`, `movilidad`.
- **Piso de ingreso mínimo minero**: post-cálculo, si `total_ingresos_computables < RMV×1.25` → completar con concepto de nivelación.
- SCTR nivel de riesgo minero vía `ConfiguracionSistema` (override de tasa por póliza/período).
- **Estrategia** `EstrategiaMinero`: régimen general + piso minero + activación de conceptos de convenio del trabajador/empresa. La jornada la resuelve el Roster (§3.4).

### 3.4 Roster → Asistencia → Nómina (transversal, sirve a ambos)

Este es el eslabón crítico. Propuesta:

1. **Servicio `roster_a_dias(personal, periodo)`** (`nominas/services/asistencia_link.py`, nuevo): cuenta desde `Roster` (o `RegistroTareo` real) los `dias_trabajados`, `dias_descanso`, `dias_falta` del período y puebla `RegistroNomina`.
2. **Promedio de jornada acumulativa**: usar `RegimenTurno.horas_max_ciclo` como base. HHEE = horas del ciclo por encima del promedio legal (168h/21d = 8h/día), no sobre 8h fija.
3. **Descanso físico**: días `DL/DLA/DS` no se pagan como trabajados (evita el doble cobro).
4. **Activar `CruceTareoRoster`**: management command que compara proyectado vs real y marca variaciones antes de calcular la planilla.

### 3.5 Arquitectura de cálculo (Strategy pattern)

```
nominas/engine.py            → orquestador; helpers compartidos (IR, AFP/ONP, redondeo)
nominas/estrategias/
    base.py                  → EstrategiaCalculo (ABC): calcular_registro(registro, conceptos)
    regimen_general.py       → EstrategiaRegimenGeneral (código actual, refactorizado)
    construccion.py          → EstrategiaConstructor
    mineria.py               → EstrategiaMinero
```

El engine elige la estrategia por `registro.personal.regimen_laboral`. Evita el spaghetti de `if/elif` y es escalable a agrario/MYPE.

---

## 4. Roadmap por fases

| Fase | Alcance | Esfuerzo | Depende de |
|------|---------|----------|------------|
| **F0 — Régimen como choice** | `regimen_laboral` → choices; selector de estrategia (aunque todas apunten a la actual al inicio). | 1-2 días | — |
| **F1 — Roster → Nómina** | Servicio que puebla `dias_trabajados`/HHEE desde Roster+Tareo; promedio de jornada acumulativa; descanso físico. **Sirve a todos los regímenes.** | 1-1.5 sem | F0 |
| **F2 — Strategy pattern** | Extraer `EstrategiaRegimenGeneral` del engine actual (sin cambiar resultados; tests de regresión). | 3-5 días | F0 |
| **F3 — Construcción Civil** | `JornalConstruccion`, categorías, conceptos (seed), planilla semanal, `EstrategiaConstructor`. | 1-2 sem | F1, F2 |
| **F4 — Minería** | Conceptos de convenio (seed), piso ingreso mínimo minero, `EstrategiaMinero`, SCTR nivel minero. | 4-6 días | F1, F2 |
| **F5 — Cruce Tareo-Roster** | Command de cruce + validación de topes legales (48h/sem promedio). | 3-4 días | F1 |

**Ruta recomendada:** F0 → F1 → F2 → (F3 y F4 en paralelo) → F5.
F1 es la de mayor ROI porque desbloquea el cálculo correcto de cualquier empresa foránea/atípica, no solo estos dos regímenes.

---

## 5. Riesgos y consideraciones

- **Jornales CAPECO cambian cada año** (convenio) → `JornalConstruccion` con vigencia + comando de import anual desde CSV.
- **Tope legal de jornada acumulativa** (promedio ≤ 48h/sem) → validación bloqueante en F5.
- **PLAME/SUNAT**: cada concepto nuevo necesita su `codigo_plame` correcto (revisar tabla oficial T-Registro/PLAME).
- **Regresión del régimen general**: F2 debe mantener resultados idénticos (usar los 50+ tests de engine existentes como red).
- **Empresas mixtas** (general + construcción + minería en el mismo cliente): el motor ya soporta `regimen_laboral` por persona; la planilla debe poder segmentar por régimen y frecuencia (mensual vs semanal).

---

## 6. Archivos clave (referencia)

| Archivo | Rol |
|---------|-----|
| `nominas/models.py:36` `ConceptoRemunerativo` | Catálogo de conceptos (extensible sin código) |
| `nominas/models.py:280` `RegistroNomina` | `dias_trabajados` (hoy manual) — objetivo de F1 |
| `nominas/engine.py:667` `calcular_registro` | Motor a refactorizar en estrategias (F2) |
| `personal/models.py:619/624/556` | `regimen_laboral` / `regimen_turno` / `condicion` |
| `personal/models.py:718` `calcular_dias_libres_ganados` | Ya lee el Roster |
| `personal/models.py:1396` `Roster` | Programación por día |
| `asistencia/models.py:24` `RegimenTurno` | Ciclos 14x7/21x7, jornada acumulativa |
| `asistencia/models.py:1060` `CruceTareoRoster` | Cruce real vs proyectado (F5) |
