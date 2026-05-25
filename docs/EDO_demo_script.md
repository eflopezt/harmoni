# Harmoni × Sabores del Sur — Demo Script

**Versión 2026-05-21 · Duración objetivo: 25-30 minutos**

> Guion para presentar Harmoni al equipo de Sabores del Sur (gastronomía premium, 24 RUCs).
> Pensado para Edwin como presentador. Cada sección incluye qué decir, qué mostrar y la transición a la siguiente.

---

## 🎯 Antes de empezar (checklist 5 min antes)

- [ ] **URL**: https://demo.harmoni.pe
- [ ] **Login admin**: `demo / demo`
- [ ] **Login trabajador**: `71445678 / demo123` (Hans Pérez, mesero en Bistró Costero)
- [ ] Browser en modo **incógnito** (cookies limpias para que veas el flujo de login limpio)
- [ ] **Pestañas pre-cargadas** (Ctrl+T):
  1. /login/
  2. /empresas/pulse/ (pre-loginado)
  3. /nominas/comparativo/
  4. /nominas/apertura/
  5. /asistencia/briefing/
- [ ] **Volumen del micrófono** OK
- [ ] **Tab para Hans** en segundo browser (Firefox o ventana incógnita separada)

**Si algo falla**: recuerda que es una demo. Tienes 3 fallbacks:
1. Refresca la página
2. "Eso es exactamente lo que vamos a configurar para ustedes en setup"
3. Ve a la próxima sección y vuelves después

---

## ⏱ Flujo de demo — 30 minutos

### 0:00–0:03 — Apertura (3 min)

**Lo que dices**:
> "Hoy les voy a mostrar Harmoni: un ERP de RRHH específicamente diseñado para grupos gastronómicos premium en Perú. Lo construimos pensando en operaciones como la suya — múltiples RUCs, brigadas profesionales, alta exigencia de calidad.
>
> La promesa es simple: **toda la operación de RRHH en una sola pantalla**, integrado con su sistema actual de contabilidad (Spring, en su caso). No reemplazamos Spring. Lo complementamos quirúrgicamente en el módulo que más les duele: RRHH.
>
> Lo que verán hoy ya está corriendo. No es una maqueta — es el sistema real con 70 trabajadores en 9 locales del grupo."

**Lo que muestras**: Login screen `/login/`

---

### 0:03–0:08 — Pulse del Grupo (5 min)

**Login como admin, ir a `/empresas/pulse/`**

**Lo que dices**:
> "Esta es la pantalla que el dueño del grupo o gerente general abre cada mañana con su café. **Pulse del Grupo.**
>
> Cada tarjeta es uno de sus 9 locales activos. El punto verde, amarillo o rojo indica la salud operativa en tiempo real:
> - **Verde**: cobertura completa, sin alertas
> - **Amarillo**: hay algo que atender (contratos por vencer, faltas excedidas)
> - **Rojo**: incidente operativo
>
> Y arriba ven los KPIs agregados: headcount total, planilla del último período en neto y costo empresa, alertas activas."

**Click en una tarjeta verde** (ej. Restaurante Insignia):

> "Hago click y entro al detalle del local. Aquí veo: trabajadores activos, asistencia de hoy (presentes/faltas), briefings programados para hoy y los próximos 2 días, planilla del último período, contratos por vencer en 30 días.
>
> Y desde aquí, **acciones rápidas** — crear briefing, emitir boletas del período, comparativo mensual."

**Frase gancho**:
> "Esto no se ofrece en ningún otro ERP del mercado peruano. Aquí está la operación de los 24 RUCs en una sola pantalla, sin tener que abrir 24 reportes distintos."

**Transición**: "Veamos un caso de uso operacional típico: el briefing del día."

---

### 0:08–0:13 — Briefing del Día (5 min)

**Ir a `/asistencia/briefing/`**

**Lo que dices**:
> "Esto es lo que llamamos **Briefing del Día** — el pre-shift handover estilo brigade kitchen. La idea: 15-30 minutos antes del servicio, el jefe de local comunica a la brigada todo lo crítico del día.
>
> Hoy tenemos 3 briefings activos: 2 publicados (verde) y 1 borrador (amarillo). Los cerrados (gris) son de turnos pasados."

**Click en un briefing publicado** (ej. Bistró Costero):

> "Aquí ven el contenido completo del briefing:
> - **Covers esperados**: 42 (reservaciones + walk-ins estimados)
> - **Especiales del día**: tres platos que el sommelier debe ofrecer
> - **86's**: items sin stock — crítico que el salón sepa antes de tomar pedidos
> - **VIPs y alergias**: la información que protege al restaurante de una crisis
> - **Dress code**: protocolo del día
>
> Y a la derecha, **trail auditable**: quién leyó el briefing y a qué hora.
>
> Para un restaurante premium, esto es compliance operativo. Si alguien dice 'no sabía del alérgico de la mesa 4', queda registrado que sí leyó el briefing a las 11:35am."

**Frase gancho**:
> "Esta feature no existe en Sling, Combine, ni 7shifts. Es uniqueness de Harmoni — pensada para gastronomía premium peruana."

**Transición**: "Y esto no es solo para el jefe — el trabajador lo ve en su portal. Permítanme cambiar de usuario."

---

### 0:13–0:17 — Portal del Trabajador (4 min)

**Abrir segunda ventana en incógnito → login Hans (71445678 / demo123)**

**Lo que dices**:
> "Este es Hans Pérez, mesero senior en Bistró Costero. Cuando entra a su portal, lo primero que ve es el **briefing del día** — el mismo que su jefe acaba de publicar.
>
> Lee los covers esperados, los especiales, los 86's, las alergias. Le da un click a 'Marcar como leído' y el sistema registra la lectura.
>
> Más abajo ve su información personal: su último neto pagado con botón para descargar la boleta PDF, sus solicitudes pendientes, sus capacitaciones próximas, su cumple, sus compañeros del mes."

**Click en "Mis Boletas"**:

> "Aquí está la boleta de mayo 2026, lista para descargar. Diseño S10 sobrio — una página, formato profesional, con QR de verificación y hash de integridad.
>
> Y el botón de **Constancia** — el documento DS 009-2011-TR que SUNAFIL puede pedir en una fiscalización para demostrar que el trabajador recibió su boleta."

**Frase gancho**:
> "Cumplimiento normativo automático. No es un PDF adjunto a un email — es un trail forense."

**Transición**: "Volvamos al lado administrativo para ver cómo se procesa una planilla de las 24 empresas a la vez."

---

### 0:17–0:23 — Emisión de Boletas + Comparativo (6 min)

**Login admin → `/nominas/`**

**Lo que dices**:
> "Aquí veo todos los períodos de planilla. El último — Mayo 2026 — ya está calculado para los 70 trabajadores. Click en el período."

**Click en período Mayo 2026**:

> "70 trabajadores, S/ 145K en neto, S/ 233K en costo empresa total. Las acciones disponibles dependen del estado: puedo recalcular, aprobar, exportar CSV, descargar el ZIP con todas las boletas en PDF (las 70 a la vez), generar PLAME para SUNAT, T-Registro, **reporte ejecutivo** (PDF de 1 página para el dueño), y comparativo mensual."

**Click en "Reporte Ejecutivo"**:
> "Una página, formato ejecutivo: resumen financiero, distribución STAFF/RCO, top 5 conceptos, distribución régimen pensionario AFP/ONP. Listo para enviar al dueño por correo o WhatsApp."

**Volver atrás → click en "Comparativo Mensual"**:

> "Y esto — **Comparativo Mensual** — es la vista que la gerencia espera al cierre de cada mes. Evolución de 6 meses: trabajadores, neto, costo empresa. Tabla con deltas porcentuales. Y un botón para exportar a Excel.
>
> Esto es lo que su contador les arma manualmente cada mes en una hoja de Excel. Ahora se genera automáticamente."

**Transición**: "Ya vimos cómo se procesa. Ahora veamos lo más importante del proyecto para ustedes: cómo arrancan."

---

### 0:23–0:27 — Saldos de Apertura (Onboarding Express) (4 min)

**Ir a `/nominas/apertura/`**

**Lo que dices**:
> "Esto es nuestra propuesta diferenciadora para Sabores del Sur. **Onboarding Express.**
>
> Lo típico para implementar un sistema de RRHH nuevo es migrar 12 meses de historia. Eso son 4-5 semanas de trabajo, su IT involucrado, riesgo de duplicar boletas. La industria lo hace así.
>
> Harmoni lo hace al revés: **no migramos historia. Cargamos saldos al corte.**"

**Mostrar el wizard "Onboarding Completado"** (debe estar verde con 70 trabajadores @ 31/05/2026):

> "Vean — esta empresa ya completó el wizard. 70 trabajadores inicializados al 31 de mayo de 2026.
>
> ¿Cómo se hizo? Tres pasos: definir fecha de corte, descargar plantilla Excel pre-llenada con todos los trabajadores activos, llenarla con saldos (CTS provisionada, gratificación, vacaciones pendientes, IR5 acumulado, préstamos), subirla. Validamos, mostramos preview, confirman."

**Click en "Descargar Plantilla Excel"** (muestra el Excel):

> "Esta plantilla la genera Harmoni con los nombres y DNIs ya cargados. Su equipo de RRHH solo llena las columnas amarillas. Lo importante: **es un Excel. No necesitan a IT.**
>
> Resultado: implementación de 2 semanas en lugar de 4-5. Time-to-value máximo."

**Frase gancho**:
> "No estamos pidiendo que cambien su forma de trabajar. Estamos pidiendo un Excel. Y desde el día 14, su próxima planilla la corren en Harmoni."

**Transición**: "Y para que su contador siga su día tranquilo con Spring..."

---

### 0:27–0:30 — Integración con Spring (3 min)

**Ir a `/integraciones/contable/`**

**Lo que dices**:
> "Aquí está el panel contable. Cuando cierran una planilla, Harmoni genera el asiento contable en **5 formatos a elección**: Excel Universal (compatible con cualquier ERP), CONCAR (el más común en Perú), Siscont, SAP, o SIRE PLE (el formato SUNAT oficial).
>
> Para ustedes que usan Spring: usamos el **Excel Universal** — un Excel simple, una hoja, 8 columnas estándar. Cualquier ERP del mercado puede importarlo. Su contador descarga el archivo, lo importa a Spring, y todo el módulo contable de Spring sigue funcionando exactamente como hoy.
>
> **Tres cosas le mandamos a Spring cada cierre**:
> 1. **El asiento contable de planilla** — desagregado por RUC y centro de costo
> 2. **El maestro actualizado de empleados** — para que su módulo de Logística sepa quién está activo
> 3. **Los costos por centro de costo** — para análisis de rentabilidad por local
>
> El resto de Spring — contabilidad, facturación, inventario — **no se toca**."

**Frase de cierre**:
> "Reemplazo quirúrgico del módulo de RRHH. Su contador no nota la diferencia, su equipo de RRHH gana un sistema moderno, y ustedes consolidan los 24 RUCs en una sola pantalla.
>
> Eso es Harmoni. ¿Qué preguntas tienen?"

---

## 🛡 Manejo de objeciones comunes

### "¿Y si Spring tiene formato propio para asientos?"

> "Para Excel Universal, CONCAR, Siscont, SAP y SIRE ya está listo. Si Spring tiene un formato custom, lo construimos como parte del proyecto — necesitamos una muestra del archivo que Spring importa hoy y en 1 sprint lo tienen."

### "¿Qué pasa si decidimos volver a Spring después de 6 meses?"

> "Tienen toda su data en Harmoni. Les entregamos un export completo en Excel estándar — listo para re-cargar en Spring. **Sin data lock-in.** Es parte de nuestra garantía."

### "¿Cómo aseguran que la planilla calcula bien la primera vez?"

> "Hacemos un **parallel run** la semana 2 — corremos mayo en Spring y en Harmoni en paralelo, comparamos centavo a centavo. Si no coinciden, no hacemos go-live. Lo escribimos en el contrato."

### "¿Quién soporta a nuestro equipo el primer mes?"

> "Soporte intensivo los primeros 30 días: respuesta menor a 4 horas hábiles. Después, soporte estándar."

### "¿Qué pasa con SUNAFIL, PLAME, T-Registro, AFPnet?"

> "Harmoni genera los 4 archivos directamente. Su equipo solo los sube a SUNAT / AFPnet. **Cumplimiento total con DS 009-2011-TR, DS 001-98-TR, Ley 27735, DL 650, todo automatizado.**"

### "¿Y si tenemos un empleado especial con cálculo manual?"

> "Tenemos sistema de **conceptos remunerativos configurables** + override por trabajador. Cualquier caso de excepción se modela y queda en el sistema."

### "¿La data se queda en Perú?"

> "Sí. Servidores en Lima. Backup diario. Compliance con la Ley 29733 de Protección de Datos Personales."

---

## 📋 Después del demo (acciones de cierre)

1. **Enviar el anexo de cotización** con Onboarding Express (`docs/EDO_onboarding_express.md`)
2. **Pedir muestra del asiento contable que Spring importa** (para escoping del conector custom)
3. **Agendar próxima reunión** — idealmente con el contador de Sabores del Sur para validar la integración Spring
4. **Compartir credenciales demo limitadas**: Isabel podrá entrar al sandbox `https://demo.harmoni.pe` con un usuario propio para explorar a su ritmo (creamos un Personal nuevo con su nombre, password temporal)

---

## 🔧 URLs clave para el demo

| URL | Para mostrar |
|-----|--------------|
| https://demo.harmoni.pe/empresas/pulse/ | Pulse del Grupo (9 locales) |
| https://demo.harmoni.pe/empresas/pulse/2/ | Drill-down de un local |
| https://demo.harmoni.pe/asistencia/briefing/ | Lista de briefings |
| https://demo.harmoni.pe/nominas/ | Períodos de planilla |
| https://demo.harmoni.pe/nominas/comparativo/ | Comparativo mensual |
| https://demo.harmoni.pe/nominas/apertura/ | Wizard Onboarding Express |
| https://demo.harmoni.pe/nominas/periodos/1/ | Detalle período mayo 2026 |
| https://demo.harmoni.pe/integraciones/contable/ | Panel contable (5 formatos) |
| https://demo.harmoni.pe/mi-portal/ | Portal del trabajador (logueado como Hans) |

---

## 🎬 Variaciones del guion según audiencia

**Si en la reunión está el dueño (CEO/founder)**: enfatizar Pulse del Grupo, Reporte Ejecutivo, ROI rápido (2 semanas vs 5).

**Si está el gerente de operaciones**: enfatizar Briefing del Día, Cuadrícula del Local (cuando esté lista), control diario.

**Si está RRHH**: enfatizar wizard de Saldos de Apertura, conceptos configurables, automatización SUNAT/PLAME.

**Si está el contador**: enfatizar asiento contable formato Spring (Excel Universal), 5 formatos disponibles, no toca su workflow actual.

**Si está IT**: enfatizar arquitectura sin lock-in, exports estándar, integración por archivo (no requiere acceso a su BD), backup en Perú.

---

*Documento vivo. Editar después de cada demo con aprendizajes y nuevas objeciones.*
