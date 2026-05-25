# Diseño: Liquidaciones, Propinas e ISC — Harmoni

> Documento para Edwin · pre-demo · explica el estado actual, el diseño recomendado, y cómo presentarlo al cliente.

---

## 1. LIQUIDACIONES — flujo unificado al cese

### 1.1 Estado actual (cómo está hoy en Harmoni)

Hoy, cuando un trabajador cesa:

- Se le pone manualmente `estado='Cesado'` + `fecha_cese` en su ficha de `Personal`.
- Se genera por separado un período tipo `LIQUIDACION` en `PeriodoNomina` (existe en el modelo, está sub-usado).
- La boleta del último mes y la liquidación van en documentos separados.
- **No hay un disparador** (signal) que conecte cese → liquidación → offboarding.

### 1.2 Diseño propuesto (lo que debería pasar)

Cuando RRHH marca a un trabajador como cesado:

```
[1] Marcar cese
    └─ desde ficha del empleado → botón "Iniciar proceso de cese"
       ├─ pide: fecha_cese, motivo, observaciones
       └─ ejecuta:
          - Personal.estado = 'Cesado'
          - Personal.fecha_cese = <fecha>
          - Personal.motivo_cese = <motivo>
          - dispara signal: post_cese_personal

[2] Signal post_cese_personal (automático)
    ├─ Genera LiquidacionLaboral (modelo dedicado, ver §1.4)
    │   - vacaciones truncas pendientes
    │   - gratificación trunca (proporcional al semestre)
    │   - CTS trunca (proporcional al semestre)
    │   - sueldo pendiente del mes en curso (días trabajados)
    │   - HE acumuladas no compensadas
    │   - menos descuentos (préstamos pendientes, adelantos, embargos)
    │
    ├─ Genera RegistroNomina del último mes (días efectivos)
    ├─ Une ambos en una BOLETA ÚNICA tipo "Boleta + Liquidación de cese"
    │   (formato PDF unificado: cabecera empresa + datos cese + tabla
    │    sueldo del mes + tabla beneficios truncos + total a recibir)
    │
    └─ Dispara workflow de offboarding (ver §1.3)

[3] Workflow offboarding (etapas configurables)
    ├─ Etapa 1: Encuesta de salida (trabajador)
    ├─ Etapa 2: Devolución de activos (IT/jefe inmediato)
    ├─ Etapa 3: Liquidación pagada (RRHH + tesorería)
    ├─ Etapa 4: Carta de no adeudo + certificado de trabajo
    └─ Etapa 5: Cierre administrativo (revocar accesos, archivar)

[4] Salidas finales
    ├─ Boleta unificada (PDF, firma digital del trabajador)
    ├─ Certificado de trabajo (PDF)
    ├─ Constancia de cese (PDF, SUNAT BAJA T-REGISTRO)
    ├─ Acta de devolución de activos
    └─ Encuesta exit interview en el portal del trabajador
```

### 1.3 Quién implementa cada parte (estado real del código hoy)

| Componente | Estado |
|------------|--------|
| Modelo `Personal.estado='Cesado'` + `fecha_cese` | ✅ ya existe |
| Modelo `PeriodoNomina(tipo='LIQUIDACION')` | ✅ ya existe |
| Cálculo de vacaciones truncas | ⚠️ existe `engine.calcular_vacaciones()`, no unificado |
| Cálculo de gratificación trunca | ✅ `engine.calcular_gratificacion()` con `dias_trabajados` |
| Cálculo de CTS trunca | ✅ `engine.calcular_cts()` con `dias_trabajados` |
| Signal `post_cese_personal` | ❌ falta |
| Modelo `LiquidacionLaboral` (header con motivo + total) | ❌ falta |
| PDF boleta unificada sueldo + liquidación | ⚠️ generador de boleta existe; falta variante "liquidación" |
| Workflow offboarding | ⚠️ módulo `workflows` está, falta el flujo pre-armado |
| Carta de no adeudo | ❌ falta plantilla |
| Encuesta exit interview | ⚠️ módulo `encuestas` existe, falta plantilla "exit" |

### 1.4 Modelo `LiquidacionLaboral` propuesto

```python
class LiquidacionLaboral(models.Model):
    personal       = models.OneToOneField(Personal, on_delete=PROTECT)
    fecha_cese     = models.DateField()
    motivo_cese    = models.CharField(max_length=50, choices=[
        ('RENUNCIA',     'Renuncia voluntaria'),
        ('DESPIDO',      'Despido (causa justa)'),
        ('DESPIDO_ARB',  'Despido arbitrario (indemnización)'),
        ('MUTUO',        'Mutuo disenso'),
        ('CADUCIDAD',    'Caducidad de contrato'),
        ('JUBILACION',   'Jubilación'),
        ('FALLECIMIENTO','Fallecimiento'),
        ('PERIODO_PRUEBA','No supera período de prueba'),
    ])
    observaciones      = models.TextField(blank=True)

    # Conceptos calculados
    vacaciones_truncas = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    gratif_trunca      = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cts_trunca         = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    sueldo_mes_curso   = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    he_no_compensadas  = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    indemnizacion      = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # arbitrario
    otros_pagos        = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Descuentos
    prestamos_pendientes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    adelantos_pendientes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    embargo              = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    otros_descuentos     = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Totales
    total_bruto = models.DecimalField(max_digits=12, decimal_places=2)
    total_neto  = models.DecimalField(max_digits=12, decimal_places=2)

    # Workflow
    estado = models.CharField(max_length=20, choices=[
        ('BORRADOR',     'Borrador'),
        ('CALCULADA',    'Calculada'),
        ('APROBADA',     'Aprobada por RRHH'),
        ('FIRMADA',      'Firmada por trabajador'),
        ('PAGADA',       'Pagada'),
        ('CERRADA',      'Cerrada'),
    ], default='BORRADOR')
    aprobada_por = models.ForeignKey(User, null=True, ...)
    firmada_en   = models.DateTimeField(null=True)
    pagada_en    = models.DateTimeField(null=True)

    # Vínculo con boleta unificada y workflow offboarding
    registro_nomina = models.OneToOneField('nominas.RegistroNomina', null=True, on_delete=SET_NULL)
    instancia_flujo = models.OneToOneField('workflows.InstanciaFlujo', null=True, on_delete=SET_NULL)
```

### 1.5 Cómo presentarlo al cliente (frase corta)

> *"Hoy cuando un trabajador cesa, lo más común en otros ERPs es generar la liquidación a mano en Excel y dispararla por mail. En Harmoni el cese es **un solo botón**: marcás la fecha y el motivo, y el sistema calcula vacaciones truncas, gratificación trunca, CTS, sueldo del mes, descuenta préstamos pendientes, emite la boleta + liquidación unificada en PDF, abre la encuesta de salida en el portal del empleado, le notifica al jefe que devuelva los activos, y genera la carta de no adeudo. Todo queda firmado digitalmente y registrado en audit log para SUNAFIL."*

### 1.6 Ruta de implementación priorizada (post-demo)

| Sprint | Entregable | Estado |
|--------|------------|--------|
| Sprint 1 (2 sem) | Modelo `LiquidacionLaboral` + migración + signal `post_cese_personal` + cálculo de truncas reutilizando `engine` | ✅ implementado |
| Sprint 2 (2 sem) | PDF boleta unificada (sueldo + liquidación) + Workflow offboarding pre-armado + wizard `/personal/<id>/cesar/` 3 pasos | ✅ implementado |
| Sprint 3 (1 sem) | Carta no adeudo + certificado de trabajo + encuesta exit + UI botones en detalle de liquidación | ✅ implementado |
| Sprint 4 (1 sem) | Tests E2E + docs cliente + capacitación RRHH | ⏳ pendiente |

**Total: ~6 semanas**.

### 1.7 Sprint 3 — Documentos al cese (✅ implementado 2026-05-25)

Tres entregables, todos visibles en `/nominas/liquidacion/<id>/` para
trabajadores cesados:

**a) Carta de no adeudo y liberación mutua**

- Generador: `nominas/cartas.py::generar_carta_no_adeudo(liquidacion)`
- Endpoint: `GET /nominas/liquidacion/<liquidacion_id>/carta-no-adeudo/`
- Nombre URL: `nominas_carta_no_adeudo_pdf`
- Acceso: `@staff_member_required`
- Estructura: header con logo + razón social + RUC + dirección, título
  "CARTA DE NO ADEUDO Y LIBERACIÓN MUTUA", cuerpo formal peruano con
  detalle de conceptos pagados y monto total, doble firma (empleador /
  trabajador), footer con N° doc, hash de integridad SHA-256 y QR de
  verificación. Tamaño A4.

**b) Certificado de trabajo**

- Generador: `nominas/cartas.py::generar_certificado_trabajo(personal)`
- Endpoint: `GET /personal/<personal_id>/certificado-trabajo/`
- Nombre URL: `personal_certificado_trabajo_pdf`
- Acceso: `@staff_member_required`. Devuelve 400 si el trabajador no
  está cesado.
- Estructura: header de empresa, título "CERTIFICADO DE TRABAJO",
  cuerpo con período laborado (alta/cese), cargo y desempeño
  (omitido si motivo de cese fue despido por causa justa), firma
  RRHH centrada, footer con N° doc + hash + QR.

**c) Encuesta exit interview**

- Seed idempotente: `python manage.py seed_exit_interview`
- Crea `Encuesta(tipo='SALIDA', estado='ACTIVA')` con **10 preguntas**
  estándar cubriendo motivo de salida, satisfacción general, eNPS,
  evaluación de jefe directo y compensación, reconocimiento y
  comentarios libres.
- Mix de tipos: `TEXTO` (libre), `ESCALA_10` (0-10), `ESCALA_5`
  (1-5), `OPCION` (sí/no/tal vez, sí/no/a veces).
- Match idempotente por `(titulo, tipo='SALIDA')`; preguntas se
  agregan solo si falta su `orden`.
- Integración con workflow: cuando la etapa 1 ("Encuesta de salida")
  del flujo offboarding está activa, la vista de detalle expone el
  botón "Enviar encuesta exit" enlazando a
  `/encuestas/responder/<encuesta_id>/`.

**Reutilizaciones clave**:
- Logo: mismo `harmoni-favicon-512.png` usado en `nominas/pdf.py`.
- Empresa: misma prioridad `Personal.empresa` → `ConfiguracionSistema`.
- Tokens y hashes: estructura sha256+SECRET_KEY como en `pdf.py`.

**Tests**: `nominas/tests/test_cartas.py` (12 tests) y
`encuestas/tests/test_exit_interview.py` (8 tests). Validan signature
PDF, extracción de texto con `pypdf`, autorización staff e
idempotencia del seed.

---

## 2. PROPINAS — distribución para gastronomía

### 2.1 Estado actual

`seed_demo_gastronomia.py` ya crea **2 conceptos remunerativos especiales**:

- `PROPINAS` — pago variable mensual a mozos/bartenders
- `RECARGO_CONSUMO` — el 10% que cobra el local al cliente

Y aplica líneas de propinas (S/200–800) en la última planilla a ~20 mozos. Pero **no hay regla de distribución automática** — RRHH lo carga manual hoy.

### 2.2 Diseño recomendado — Pool de propinas

En gastronomía profesional, las propinas se manejan con un **"pool" semanal o mensual**:

```
[1] Caja recibe propinas (sumadas por turno/día)
    └─ Se registran en concepto "Pool de propinas"

[2] Distribución por puntos (configurable por local)
    ├─ Mozos:         3 puntos
    ├─ Bartender:     2.5 puntos
    ├─ Hostess:       1.5 puntos
    ├─ Cocina:        1 punto (todos, parejo)
    ├─ Lavaplatos:    0.5 puntos
    └─ Ayudantes:     0.5 puntos

[3] Cálculo
    monto_por_persona = (pool_total × puntos_persona) / suma_puntos_turno

[4] Aparece como concepto NO remunerativo en la boleta
    (no afecta AFP/ONP/CTS/gratis — solo está en el neto pagado)
```

### 2.3 Modelo propuesto

```python
class ConfiguracionPropinas(models.Model):
    """Por local. Define modo y reglas."""
    empresa = models.ForeignKey(Empresa, on_delete=CASCADE)
    modo    = models.CharField(max_length=20, choices=[
        ('POOL_PUNTOS',  'Pool por puntos (recomendado)'),
        ('POOL_PAREJO',  'Pool dividido parejo'),
        ('INDIVIDUAL',   'Cada uno recibe lo suyo (mozo individual)'),
    ], default='POOL_PUNTOS')
    incluye_cocina  = models.BooleanField(default=True)
    incluye_admin   = models.BooleanField(default=False)
    porcentaje_casa = models.DecimalField(default=0)  # % que retiene el local


class PuntosPropinas(models.Model):
    """Tabla de puntos por cargo."""
    configuracion = models.ForeignKey(ConfiguracionPropinas)
    cargo         = models.ForeignKey(Cargo)
    puntos        = models.DecimalField(max_digits=4, decimal_places=2)


class PoolPropinas(models.Model):
    """Recolección semanal o mensual de propinas."""
    empresa     = models.ForeignKey(Empresa)
    fecha_inicio = models.DateField()
    fecha_fin    = models.DateField()
    monto_bruto  = models.DecimalField(max_digits=12, decimal_places=2)
    distribuido  = models.BooleanField(default=False)
    distribuido_en = models.DateTimeField(null=True)


class DistribucionPropinas(models.Model):
    """Detalle por trabajador."""
    pool       = models.ForeignKey(PoolPropinas)
    personal   = models.ForeignKey(Personal)
    puntos     = models.DecimalField(max_digits=4, decimal_places=2)
    monto      = models.DecimalField(max_digits=12, decimal_places=2)
    aplicado_en_nomina = models.ForeignKey(RegistroNomina, null=True)
```

### 2.4 Cómo presentarlo al cliente

> *"Las propinas en gastronomía siempre son un dolor de cabeza: o las distribuís mal y se quejan los mozos, o las hacés en Excel y nadie audita. Harmoni tiene un **pool de propinas por puntos** configurable por local: defines cuántos puntos vale cada cargo (mozo, bartender, cocina, hostess), cargás el monto recolectado de la semana, y el sistema reparte automáticamente proporcional a los puntos. Aparece como concepto no remunerativo en la boleta del trabajador. Todo queda trazado."*

### 2.5 Estado / prioridad

- **Modelo de pool y puntos**: a implementar Sprint post-demo (3-5 días).
- **Conceptos `PROPINAS` y `RECARGO_CONSUMO`**: ya existen, sirven como placeholder.
- **Para la demo**: mencionar como "está armado el motor, configuración por UI viene en próxima release".

---

## 3. ISC — Impuesto Selectivo al Consumo

### 3.1 Aclaración importante

**El ISC NO aplica a planilla**. ISC es un tributo SUNAT sobre **bienes y servicios específicos**:

- Combustibles y carburantes
- Bebidas alcohólicas
- Cigarrillos
- Juegos de azar / casinos
- Vehículos nuevos
- Bebidas azucaradas, agua mineral
- Gaseosas

Lo paga el productor/importador, no el trabajador ni el empleador en planilla.

### 3.2 Lo que SÍ aplica a un restaurante

| Tributo | Quién lo paga | Dónde está en Harmoni |
|---------|---------------|----------------------|
| **IR 5ta categoría** | Trabajador (descuento planilla) | ✅ `engine.calcular_renta()` |
| **AFP/ONP** | Trabajador (descuento planilla) | ✅ `engine.calcular_registro()` |
| **EsSalud 9%** | Empleador (aporte) | ✅ `engine.calcular_essalud()` |
| **SCTR** | Empleador (si actividad de riesgo) | ✅ `models.PolizaSCTR` |
| **IR 3ra categoría** | Empresa (renta empresarial) | ❌ no es planilla, va por contabilidad |
| **IGV 18%** | Cliente final, retiene la empresa | ❌ no es planilla, va por POS/facturación |
| **ISC** (si vende bebidas alcohólicas, gaseosas) | Productor/importador del bien | ❌ no es planilla, va por contabilidad |

### 3.3 Cómo responder al cliente si pregunta por ISC

> *"El ISC no es un descuento de planilla — es un impuesto al producto (alcohol, gaseosas, etc.). Lo paga el proveedor de la mercadería, no el restaurante ni el trabajador. Si tu negocio vende bebidas alcohólicas o gaseosas, eso va por contabilidad general (libro de compras, IGV, IR 3ra), no por Harmoni. Harmoni cubre **todo lo que es planilla**: IR 5ta del trabajador, AFP/ONP, EsSalud, SCTR. Si necesitás integración contable, exportamos asiento a CONCAR/Siscont/SAP."*

---

## 4. Resumen para la presentación

| Pregunta | Respuesta corta |
|----------|-----------------|
| ¿Tienen liquidaciones? | Sí, integradas con el flujo de cese: 1 botón → boleta unificada + workflow offboarding + carta no adeudo + encuesta salida. (Roadmap: Sprint 1-4 post-demo.) |
| ¿Y las propinas? | Concepto pre-cargado. Pool por puntos configurable por local en próxima release. |
| ¿ISC? | No aplica a planilla — es impuesto al producto. Lo cubre tu contabilidad general. Harmoni hace IR 5ta, AFP/ONP, EsSalud, SCTR. |
| ¿Boleta + liquidación juntas? | Sí, en una sola PDF unificada al momento del cese (en roadmap, hoy van separadas). |
| ¿Disparador automático? | Sí, signal `post_cese_personal` activa: liquidación + offboarding + revocación accesos + encuesta exit. |

---

## 5. TODOs accionables post-demo

- [ ] Modelo `LiquidacionLaboral` + migración + signal
- [ ] Wizard "Cesar trabajador" (UI 3 pasos)
- [ ] PDF unificado sueldo + liquidación (variante de `nominas/pdf.py`)
- [ ] Workflow offboarding pre-armado (5 etapas)
- [ ] Modelo Pool de propinas + configuración por local
- [ ] UI distribución propinas (cargar pool, ver previsualización, aprobar)
- [ ] Encuesta exit interview (plantilla en módulo `encuestas`)
- [ ] Plantilla carta no adeudo + certificado trabajo
