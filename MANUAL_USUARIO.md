# MANUAL DE USUARIO — HARMONI ERP
### Sistema de Gestión de Recursos Humanos
**Versión 1.0 · Marzo 2026**

---

> **Empresa de referencia**: Minera Andes SAC (Andes Mining) — 234 colaboradores (193 STAFF + 41 RCO)

---

## Tabla de Contenidos

1. [Introducción](#1-introducción)
2. [Acceso al Sistema](#2-acceso-al-sistema)
3. [Dashboard Principal](#3-dashboard-principal)
4. [Módulo Personal](#4-módulo-personal)
5. [Módulo Asistencia / Tareo](#5-módulo-asistencia--tareo)
6. [Módulo Vacaciones y Permisos](#6-módulo-vacaciones-y-permisos)
7. [Módulo Nóminas](#7-módulo-nóminas)
8. [Analytics & People Intelligence](#8-analytics--people-intelligence)
9. [Módulo Reclutamiento](#9-módulo-reclutamiento)
10. [Módulo Capacitaciones](#10-módulo-capacitaciones)
11. [Módulo Evaluaciones de Desempeño](#11-módulo-evaluaciones-de-desempeño)
12. [Módulo Encuestas y Clima Laboral](#12-módulo-encuestas-y-clima-laboral)
13. [Módulo Disciplinaria](#13-módulo-disciplinaria)
14. [Módulo Préstamos y Adelantos](#14-módulo-préstamos-y-adelantos)
15. [Módulo Estructura Salarial](#15-módulo-estructura-salarial)
16. [Módulo Onboarding y Offboarding](#16-módulo-onboarding-y-offboarding)
17. [Módulo Comunicaciones](#17-módulo-comunicaciones)
18. [Portal del Empleado](#18-portal-del-empleado)
19. [Harmoni AI — Asistente Inteligente](#19-harmoni-ai--asistente-inteligente)
20. [Configuración del Sistema](#20-configuración-del-sistema)
21. [Atajos de Teclado y Tips](#21-atajos-de-teclado-y-tips)
22. [Preguntas Frecuentes](#22-preguntas-frecuentes)

---

## 1. Introducción

### ¿Qué es Harmoni ERP?

Harmoni es un sistema de gestión de Recursos Humanos diseñado específicamente para empresas peruanas. Integra en una sola plataforma todos los procesos del ciclo de vida del colaborador: desde el reclutamiento y onboarding, pasando por la gestión diaria de asistencia y nóminas, hasta las evaluaciones de desempeño, capacitaciones y procesos disciplinarios.

El sistema está construido pensando en la legislación laboral peruana vigente (D.Leg. 728, D.Leg. 713, DS 003-97-TR, entre otros), garantizando que los cálculos de horas extras, vacaciones, gratificaciones y CTS se realicen conforme a ley.

### Filosofía del sistema

Harmoni trabaja en armonía con su entorno. Cada módulo está conectado con los demás: un empleado registrado en Personal aparece automáticamente en Asistencia, Vacaciones, Nóminas y el Portal del Empleado. No existe doble ingreso de datos.

El sistema comunica — no el usuario. Las alertas, notificaciones y señales proactivas permiten que el equipo de RRHH actúe antes de que los problemas escalen.

### Tipos de usuario

| Perfil | Descripción |
|--------|-------------|
| **Administrador** | Acceso total al sistema. Configura parámetros, usuarios y permisos. |
| **RRHH** | Gestiona todos los módulos operativos: personal, asistencia, vacaciones, nóminas, etc. |
| **Jefe / Gerente** | Aprueba solicitudes de su equipo, visualiza reportes de su área. |
| **Empleado** | Accede al Portal del Empleado: consulta su asistencia, solicita vacaciones, ve sus recibos. |

### Convenciones de este manual

- **Rutas de navegación**: se indican como `Menu > Submenu > Opción`
- **Campos obligatorios**: marcados con asterisco (*) en el sistema
- **Formato monetario**: S/ 1,234.56 (sol peruano, punto decimal, coma de miles)
- **Grupos de trabajo**: STAFF = personal en planilla con banco de horas; RCO = personal por recibo de honorarios
- **Ciclo de planilla**: del día 21 del mes anterior al día 20 del mes en curso

---

## 2. Acceso al Sistema

### Cómo ingresar

1. Abra su navegador web (Chrome, Firefox o Edge recomendados).
2. Ingrese la URL proporcionada por su administrador de sistemas.
3. En la pantalla de inicio de sesión, escriba su **usuario** y **contraseña**.
4. Haga clic en **Ingresar**.

### Recuperar contraseña

Si olvidó su contraseña:
1. En la pantalla de login, haga clic en **¿Olvidó su contraseña?**
2. Ingrese su correo electrónico registrado.
3. Recibirá un enlace de recuperación en su bandeja de entrada.
4. El enlace es válido por 24 horas.

### Cerrar sesión

Para cerrar sesión de forma segura, haga clic en su nombre (esquina superior derecha) y seleccione **Cerrar sesión**. Se recomienda cerrar sesión siempre que deje el equipo desatendido.

### Seguridad

- No comparta su contraseña con nadie, ni siquiera con el área de sistemas.
- Si detecta acceso no autorizado a su cuenta, notifique inmediatamente al administrador.
- El sistema registra todas las acciones (audit trail) con fecha, hora y usuario.

---

## 3. Dashboard Principal

### Qué hace

El Dashboard es la pantalla de inicio del sistema. Muestra un resumen ejecutivo del estado actual de la empresa en tiempo real: asistencia del día, alertas importantes, accesos rápidos a todos los módulos y señales de atención.

### Quién lo usa

Todo el personal con acceso al sistema. El contenido se adapta al perfil del usuario.

### Cómo acceder

Haga clic en el logo de Harmoni (esquina superior izquierda) o en `Inicio` del menú lateral.

### Componentes del Dashboard

#### Saludo y fecha
El sistema muestra un saludo personalizado ("Buenos días, [nombre]") junto con la fecha actual. Cuando corresponda, aparece un **banner contextual** con efemérides relevantes (Día Internacional de la Mujer, Día del Trabajo, etc.).

#### KPIs del día (panel "Hoy")
Muestra en tiempo real:
- **Total de colaboradores**: 234 activos en Minera Andes SAC
- **Presentes**: colaboradores con marcación de entrada registrada hoy
- **Faltas**: ausencias sin justificación del día
- **Permisos**: colaboradores con permiso aprobado activo

**Ejemplo Minera Andes SAC**: 234 colaboradores, 182 presentes, 21 faltas, 9 permisos.

#### Gráfico de distribución STAFF / RCO
Donut chart interactivo que muestra la proporción de personal STAFF (planilla) vs. RCO (honorarios). En Minera Andes SAC: 193 STAFF (82%) y 41 RCO (18%).

#### Alertas destacadas
Chips de color según urgencia:
- **Amarillo (advertencia)**: situaciones que requieren atención próxima. Ejemplo: "101 contratos vencen en 30 días"
- **Rojo (peligro)**: situaciones urgentes que requieren acción inmediata

Haga clic en cualquier chip para ir directamente al listado correspondiente.

#### Accesos rápidos a módulos
Cards organizadas por categoría que llevan directamente a cada módulo del sistema. Las cards muestran un ícono representativo y el nombre del módulo.

### Notas importantes

- El Dashboard se actualiza automáticamente. No es necesario refrescar la página.
- Los KPIs reflejan el estado al momento de la consulta.
- Los banners contextuales se configuran en `Configuración > Calendario Laboral > Feriados`.

---

## 4. Módulo Personal

### Qué hace

Gestiona el maestro de empleados de la empresa. Contiene la ficha completa de cada colaborador: datos personales, laborales, contractuales y organizacionales. Es el módulo central del sistema — todos los demás módulos dependen de la información registrada aquí.

### Quién lo usa

Principalmente el equipo de RRHH y los administradores del sistema. Los gerentes pueden consultar la información de su equipo (según permisos configurados).

### Cómo acceder

`Personal > Empleados` en el menú lateral izquierdo.

### Funcionalidades principales

#### Lista de empleados
La pantalla principal muestra todos los empleados activos con:
- **DNI**: documento de identidad
- **Nombres y Apellidos**
- **Cargo**: puesto de trabajo
- **Subárea**: unidad organizacional de segundo nivel
- **Grupo**: STAFF o RCO
- **Estado**: Activo, Inactivo, Suspendido
- **Sueldo**: remuneración mensual

**Minera Andes SAC**: 234 colaboradores activos — 193 STAFF y 41 RCO.

#### Filtros disponibles
- Por estado (Activo / Inactivo / Suspendido)
- Por grupo (STAFF / RCO)
- Por subárea o área
- Búsqueda libre por nombre, DNI o cargo

#### Perfil del empleado
Al hacer clic en un empleado, se abre su ficha completa con las siguientes pestañas:

**Pestaña General**
- Foto de perfil
- Datos personales (DNI, fecha de nacimiento, correo, teléfono, dirección)
- Datos laborales (cargo, área, subárea, tipo de contrato, fecha de ingreso)
- Indicadores rápidos: antigüedad en la empresa, días de vacaciones disponibles, horas en banco de horas

**Pestaña Nómina**
- Remuneración mensual y componentes
- Tipo de contrato y vigencia
- AFP o SNP y datos de afiliación
- Cuenta bancaria para depositar remuneraciones

**Pestaña Vacaciones**
- Saldo de días disponibles por año
- Historial de vacaciones tomadas
- Solicitudes pendientes de aprobación

**Pestaña Asistencia**
- Resumen del ciclo actual: faltas, horas extras, tardanzas
- Acceso al detalle del tareo del empleado

**Pestaña Préstamos**
- Préstamos vigentes con saldo pendiente
- Cuotas descontadas y próximas

**Pestaña Salario**
- Posición en la banda salarial
- Compa-ratio (posición relativa dentro del rango)
- Historial de incrementos

**Pestaña Permisos**
- Permisos y licencias solicitados
- Estado de cada solicitud (Pendiente / Aprobado / Rechazado)

**Pestaña Desarrollo**
- Capacitaciones completadas y en curso
- Evaluaciones de desempeño recientes
- Plan de desarrollo individual (PDI)

#### Registrar nuevo empleado
1. En la lista de empleados, haga clic en el botón **+ Nuevo Empleado** (esquina superior derecha).
2. Complete los campos obligatorios (*):
   - DNI, Nombres, Apellidos
   - Fecha de nacimiento
   - Fecha de ingreso
   - Cargo
   - Área y Subárea
   - Grupo (STAFF / RCO)
   - Tipo de contrato
   - Remuneración mensual
3. Suba la foto de perfil (opcional pero recomendado).
4. Haga clic en **Guardar**.

El empleado quedará disponible automáticamente en todos los módulos del sistema.

#### Gestión de áreas y subáreas
`Personal > Áreas` permite crear y gestionar la estructura organizacional:
- Crear áreas (unidades de primer nivel)
- Crear subáreas vinculadas a un área
- Asignar responsables por área
- Ver el organigrama resultante

#### Contratos
`Personal > Contratos` muestra todos los contratos registrados con fecha de vencimiento. El sistema alerta automáticamente cuando un contrato está próximo a vencer:
- Alerta amarilla: 60 días antes del vencimiento
- Alerta roja: 30 días antes del vencimiento

**Minera Andes SAC**: 101 contratos vencen en los próximos 30 días.

#### Roster (control de viajes)
`Personal > Roster` aplica exclusivamente al personal foráneo que viaja al lugar de trabajo (mina, campamento, etc.). Es un control proyectado para la compra anticipada de pasajes aéreos. El roster puede o no cumplirse según la operación.

- Vista matricial: empleados vs. fechas de entrada/salida
- Importación masiva desde Excel
- El roster NO está relacionado directamente con la asistencia diaria

#### Reportes de personal
`Personal > Reportes` ofrece plantillas de reportes predefinidos:
- Listado de empleados activos con datos completos
- Personal por área y subárea
- Contratos próximos a vencer
- Cumpleaños del mes
- Antigüedad del personal

### Flujo de trabajo: incorporar un nuevo empleado

1. Reciba el expediente de contratación del nuevo colaborador.
2. Ingrese a `Personal > Empleados > + Nuevo Empleado`.
3. Complete todos los datos personales y laborales.
4. Registre el tipo y vigencia del contrato en la pestaña **Nómina**.
5. El sistema notifica automáticamente al área de Sistemas para crear las credenciales de acceso.
6. El empleado aparecerá automáticamente en el módulo de Asistencia desde su fecha de ingreso.
7. Si el empleado requiere proceso de onboarding, ingrese a `Onboarding > Nuevo Proceso`.

### Notas importantes

- El **personal de confianza y dirección** está registrado en el sistema pero NO tiene control de faltas ni horas extras. Solo se registra presencia y se gestionan vacaciones, gratificación, CTS y AFP.
- El **DNI** es el identificador único — no se puede repetir en el sistema.
- Los cambios en remuneración quedan registrados en el historial salarial de cada empleado.
- Al dar de baja a un empleado, el sistema solicita el motivo (renuncia, despido, vencimiento de contrato, etc.) y registra la fecha de cese.

---

## 5. Módulo Asistencia / Tareo

### Qué hace

Registra y procesa la asistencia diaria de todos los colaboradores. Calcula automáticamente horas extras (HE), tardanzas, faltas y días sin salida. Gestiona el Banco de Horas para personal STAFF y genera los insumos para nómina.

### Quién lo usa

Equipo de RRHH para importar y revisar marcaciones. Jefes de área para aprobar solicitudes de horas extras. Empleados para consultar su asistencia desde el Portal.

### Cómo acceder

`Asistencia` en el menú lateral izquierdo.

### Conceptos clave

| Término | Significado |
|---------|-------------|
| **HE 25%** | Horas extras en día hábil (primeras 2 horas: 25% recargo) |
| **HE 35%** | Horas extras en día hábil (desde la 3ra hora: 35% recargo) |
| **HE 100%** | Horas extras en feriado o domingo laborado (100% recargo, D.Leg. 713) |
| **SS (Sin Salida)** | Día en que el empleado marcó entrada pero no marcó salida. Se cuenta como día trabajado completo, sin HE. |
| **Banco de Horas** | Para personal STAFF, las HE se convierten en horas compensadas en lugar de pago directo. |
| **LSG** | Licencia sin goce de haber |
| **Ciclo** | Período del día 21 del mes anterior al día 20 del mes en curso |

### Funcionalidades principales

#### Dashboard de Asistencia
`Asistencia > Dashboard` muestra el resumen del ciclo actual:

- Total STAFF: 193 personas
- Total RCO: 41 personas
- HE Total ciclo: 978 horas acumuladas
- Faltas / LSG: 97 registros
- Sin Salida (SS): 197 registros

Desglose de horas extras:
- HE 25%: 652.9 horas
- HE 35%: 200.7 horas
- HE 100%: 124.7 horas

Banco de Horas:
- 115 personas con saldo
- 346.6 horas saldo total acumulado

#### Vista Unificada
`Asistencia > Vista Unificada` es la tabla maestra del tareo con todas las personas:

- 277 filas (empleados)
- Columnas: T (tardanzas) / SS (sin salida) / DL (días laborados) / FA (faltas) / VAC (vacaciones) / HE 25% / HE 35% / HE 100% / HE Total
- Filtros por grupo (STAFF / RCO), mes, año y búsqueda por nombre

**KPIs del ciclo filtrado**: 1,017.3h HE total, 110 faltas, 1,264 días-persona trabajados.

#### Vista STAFF
`Asistencia > Vista STAFF` muestra exclusivamente el personal de planilla con el detalle de su banco de horas y horas extras a pagar.

#### Vista RCO
`Asistencia > Vista RCO` muestra el personal por recibo de honorarios. Las HE del personal RCO van directamente a pago en nómina (no al banco de horas).

#### Banco de Horas
`Asistencia > Banco de Horas` muestra el saldo acumulado de cada empleado STAFF:
- Horas ingresadas (HE generadas)
- Horas usadas (compensaciones tomadas)
- Saldo disponible
- Historial de movimientos

#### Justificaciones
`Asistencia > Justificaciones` permite documentar las ausencias o incidencias:
- Justificar una falta con sustento
- Adjuntar documentos de respaldo (certificado médico, etc.)
- Flujo de aprobación por el jefe inmediato

#### Papeletas
`Asistencia > Papeletas` gestiona las papeletas de salida y permisos dentro del horario laboral:
- Crear papeleta (salida con goce / salida sin goce)
- Aprobación del jefe inmediato
- Registro automático en el tareo

#### Solicitudes de Horas Extras
`Asistencia > Solicitudes HE` permite al empleado o al jefe solicitar la autorización previa de horas extras:
- El jefe envía la solicitud indicando empleado, fecha y horas estimadas
- RRHH aprueba o rechaza
- Las HE quedan pre-autorizadas y se controlan en el cierre del ciclo

#### Importación de marcaciones
`Asistencia > Importar` soporta múltiples fuentes de datos de asistencia:

**Desde reloj biométrico (ZKTeco)**
1. Descargue el archivo de marcaciones del software del reloj biométrico.
2. Ingrese a `Asistencia > Importar > Biométrico`.
3. Seleccione el archivo (formato .dat o .csv).
4. El sistema mapea automáticamente los registros a los empleados por DNI.
5. Revise las excepciones (empleados no mapeados) y corrija manualmente.
6. Haga clic en **Procesar Importación**.

**Desde Excel/SUNAT**
`Asistencia > Importar > SUNAT` para planillas electrónicas en formato SUNAT.

**Desde Synkro**
`Asistencia > Importar > Synkro` para sistemas de control de acceso Synkro.

**Desde S10**
`Asistencia > Importar > S10` para empresas que usan S10 como sistema de origen.

### Flujo de trabajo: cierre mensual de asistencia

1. A partir del día 21, inicie la revisión del ciclo que cierra el día 20.
2. Ingrese a `Asistencia > Vista Unificada` y filtre por el mes a cerrar.
3. Revise los registros de SS (sin salida) — confirme si fueron días trabajados o ausencias.
4. Procese las justificaciones pendientes en `Asistencia > Justificaciones`.
5. Verifique el Banco de Horas de personal STAFF.
6. Exporte el resumen para el proceso de nómina.
7. Ingrese al módulo `Cierre` para ejecutar el cierre formal del mes.

### Notas importantes

- Las **HE 100%** aplican a feriados laborados y domingos/días de descanso obligatorio (DSO) trabajados, conforme al D.Leg. 713.
- El personal STAFF acumula las HE en el Banco de Horas. El personal RCO recibe las HE como pago adicional en la boleta.
- Un día **Sin Salida (SS)** se considera día trabajado completo y se paga normalmente, pero no genera horas extras.
- El **personal de confianza y dirección** aparece en el módulo de asistencia solo para registro de presencia. No se calculan HE ni se controlan faltas.

---

## 6. Módulo Vacaciones y Permisos

### Qué hace

Gestiona el ciclo completo de vacaciones y permisos del personal: acumulación de saldos, solicitudes, aprobaciones, goce efectivo y venta de vacaciones. También administra los 12 tipos de permiso/licencia establecidos en la legislación laboral peruana.

### Quién lo usa

Empleados para solicitar sus vacaciones y permisos. Jefes para aprobar o rechazar solicitudes. RRHH para supervisar saldos y gestionar el calendario de vacaciones.

### Cómo acceder

`Vacaciones` en el menú lateral izquierdo.

### Funcionalidades principales

#### Panel de Vacaciones
`Vacaciones > Panel` muestra el estado general:

**Minera Andes SAC (cifras actuales)**:
- 69 solicitudes en el sistema
- 20 en estado PENDIENTE de aprobación
- 14 APROBADAS (programadas)
- 21 COMPLETADAS (ya disfrutadas)
- 9 EN_GOCE (empleados actualmente de vacaciones)
- 4,324 días acumulados total en la empresa
- 234 colaboradores con saldo disponible

#### Saldos de vacaciones
`Vacaciones > Saldos` muestra el saldo de cada empleado:
- Días acumulados por año de servicio (30 días por año según D.Leg. 713)
- Días tomados
- Días pendientes disponibles
- Trunco vacacional (fracción proporcional al tiempo servido)

El sistema calcula automáticamente los saldos en base a la fecha de ingreso y los períodos ya disfrutados.

#### Solicitar vacaciones
**Flujo para el empleado (desde el Portal)**:
1. Ingrese al Portal del Empleado.
2. Haga clic en **Mis Vacaciones > Solicitar Vacaciones**.
3. Seleccione las fechas de inicio y fin.
4. El sistema muestra los días hábiles que se descontarán.
5. Agregue un comentario si lo desea.
6. Haga clic en **Enviar Solicitud**.
7. Su jefe inmediato recibirá una notificación para aprobar.

**Flujo para RRHH (registro directo)**:
1. `Vacaciones > Crear Solicitud`
2. Seleccione el empleado, fechas y tipo (vacaciones / anticipadas / venta).
3. Guarde y apruebe directamente si tiene permisos de aprobación.

#### Tipos de permiso y licencia (12 tipos Perú)

Harmoni gestiona los siguientes tipos conforme a la legislación vigente:

| Tipo | Base Legal | Con Goce |
|------|-----------|----------|
| Maternidad (pre y post natal) | Ley 26644 | Sí |
| Paternidad | Ley 29409 | Sí |
| Fallecimiento de familiar | DS 003-97-TR | Sí |
| Matrimonio | Convenio colectivo | Según política |
| Enfermedad (con certificado médico) | DS 003-97-TR | Sí (con subsidio EsSalud desde el 21vo día) |
| Licencia sindical | Ley 25593 | Sí |
| Capacitación / Comisión de servicios | Política interna | Sí |
| Licencia sin goce de haber | DS 003-97-TR | No |
| Donación de sangre | Ley 27282 | Sí (1 día) |
| Adopción | Ley 27409 | Sí |
| Asistencia médica (propios o familiares) | Política interna | Según política |
| Permiso personal (horas) | Política interna | Según política |

#### Permisos Panel
`Vacaciones > Permisos` lista todas las solicitudes de permiso:
- Vista consolidada por estado (Pendiente / Aprobado / Rechazado / Anulado)
- Filtros por tipo de permiso, área, fechas
- Flujo de aprobación configurable (un nivel o dos niveles)

#### Calendario de vacaciones
`Vacaciones > Calendario` muestra en vista mensual las vacaciones aprobadas de todo el personal, permitiendo planificar la cobertura y evitar ausencias simultáneas en el mismo equipo.

#### Tipos de permiso configurables
`Vacaciones > Tipos de Permiso` permite al administrador gestionar los tipos disponibles, indicando si son con o sin goce, si requieren sustento, la duración máxima y si descuentan del saldo de vacaciones.

### Flujo de trabajo: aprobar una solicitud de vacaciones

1. El jefe recibe notificación por correo/sistema de nueva solicitud.
2. Ingresa a `Vacaciones > Panel` o al módulo de Aprobaciones.
3. Revisa las fechas solicitadas y el saldo disponible del empleado.
4. Verifica el calendario del área para confirmar que la cobertura está asegurada.
5. Hace clic en **Aprobar** o **Rechazar** (con comentario obligatorio en caso de rechazo).
6. El empleado recibe notificación automática de la decisión.

### Notas importantes

- La vacación **trunca** es proporcional al tiempo trabajado. Si un empleado tiene 6 meses de servicio y termina el contrato, se le pagan 15 días de vacaciones truncas.
- La **venta de vacaciones** permite al empleado vender hasta 15 de los 30 días anuales por acuerdo escrito.
- El sistema alerta cuando un colaborador acumula más de 60 días de vacaciones pendientes (riesgo de vacaciones vencidas).
- Las vacaciones **no se pierden** — el empleado tiene hasta 1 año adicional para disfrutarlas después del año de acumulación, más 1 año para cobrar la compensación si no las tomó.

---

## 7. Módulo Nóminas

### Qué hace

Calcula y procesa la planilla mensual incluyendo todos los conceptos remunerativos y no remunerativos: sueldo básico, horas extras, descuentos AFP/ONP, gratificaciones, CTS e impuesto a la renta de 5ta categoría. Genera boletas de pago, reportes contables y archivos para los bancos.

### Quién lo usa

El equipo de Nóminas/RRHH para procesar y aprobar la planilla. Gerencia Financiera para revisar el costo empresa. Empleados para consultar sus boletas en el Portal.

### Cómo acceder

`Nóminas` en el menú lateral izquierdo.

### Conceptos clave del sistema de nóminas peruano

| Concepto | Descripción |
|----------|-------------|
| **AFP / ONP** | Sistema previsional. AFP: fondo privado (aportación ~10% + prima de seguro + comisión). ONP: sistema público (13% del sueldo). |
| **Gratificación** | 2 gratificaciones anuales (julio y diciembre) equivalentes a 1 sueldo mensual cada una. |
| **CTS** | Compensación por Tiempo de Servicios. Se deposita en mayo y noviembre (0.5 sueldo + 1/6 de gratificación proporcional). |
| **IR 5ta Categoría** | Retención mensual del Impuesto a la Renta sobre ingresos laborales dependientes. Se calcula sobre la renta anual proyectada. |
| **UIT** | Unidad Impositiva Tributaria. Valor de referencia para cálculos tributarios (S/ 5,350 en 2025). |
| **RMV** | Remuneración Mínima Vital (S/ 1,025 desde mayo 2022). |

### Funcionalidades principales

#### Panel de Nóminas
`Nóminas > Panel` muestra todos los períodos de nómina registrados:

**Minera Andes SAC — Último período (Febrero 2026)**:
- Trabajadores en planilla: 259
- Neto a pagar: S/ 118,880
- Costo empresa: S/ 192,252
- Estado: Aprobado

#### Crear nuevo período
1. `Nóminas > Nuevo Período`
2. Seleccione mes y año del período.
3. El sistema importa automáticamente los datos de asistencia del ciclo cerrado.
4. Revise y ajuste las novedades:
   - Horas extras del ciclo
   - Descuentos por faltas/tardanzas
   - Préstamos y adelantos con cuota en el período
   - Bonos y adicionales
5. Ejecute el cálculo preliminar.
6. Revise el resumen y los cálculos de IR 5ta, AFP/ONP.
7. Apruebe el período para proceder al pago.

#### Conceptos de nómina configurables
`Nóminas > Conceptos` lista todos los conceptos de ingreso y descuento:
- Conceptos fijos: sueldo básico, asignación familiar
- Conceptos variables: HE 25%, HE 35%, HE 100%, bonos de productividad
- Descuentos: AFP/ONP, IR 5ta, cuotas de préstamos, tardanzas

#### Boletas de pago
Cada período genera automáticamente las boletas de pago de todos los empleados:
- Formato PDF con el diseño oficial
- Disponibles en el Portal del Empleado
- El empleado puede marcar "Constancia de Lectura"
- Se envían automáticamente por correo (si está configurado el servidor SMTP)

#### Gratificaciones
`Nóminas > Gratificaciones` procesa los pagos de julio y diciembre:
- Cálculo automático proporcional para empleados con menos de 6 meses en el período
- Incluye la bonificación extraordinaria (9% del monto de la gratificación)
- Genera los archivos para el banco

#### CTS
`Nóminas > CTS` gestiona los depósitos semestrales de mayo y noviembre:
- Cálculo automático por empleado
- Destino al banco CTS elegido por el empleado
- Constancia de depósito para el trabajador

#### Impuesto a la Renta 5ta Categoría
`Nóminas > IR 5ta` muestra el cálculo mensual de retenciones:
- Proyección anual de rentas
- Aplicación de deducciones (7 UIT fija + gastos adicionales)
- Cálculo de la retención mensual escalonada
- Regularización en diciembre

#### Liquidaciones
`Nóminas > Liquidaciones` procesa los pagos finales por cese:
- Beneficios sociales: vacaciones truncas, CTS, gratificación trunca
- Compensación por tiempo de servicios acumulada
- Generación del certificado de trabajo

#### Flujo de caja
`Nóminas > Flujo de Caja` proyecta los pagos futuros de nóminas, CTS y gratificaciones para la planificación financiera.

### Flujo de trabajo: proceso de nómina mensual

1. **Semana 3 del mes** (a partir del día 21): Cierre del ciclo de asistencia.
2. Verificar que todos los incidentes estén resueltos (justificaciones, SS, HE aprobadas).
3. `Nóminas > Nuevo Período` → crear el período del mes.
4. Importar novedades: nuevos ingresos, ceses, cambios salariales, préstamos nuevos.
5. Ejecutar cálculo preliminar y revisar por empleado.
6. Enviar resumen a Gerencia Financiera para revisión.
7. Aprobar el período.
8. Generar archivos de transferencia bancaria.
9. Las boletas quedan disponibles automáticamente en el Portal del Empleado.

### Notas importantes

- El ciclo de planilla va del **día 21 del mes anterior al día 20 del mes en curso**.
- La **VistaNomina** tiene aproximadamente 60 columnas dinámicas según los conceptos activos.
- Los archivos de planilla pueden sincronizarse con SharePoint si la integración está configurada.
- El sistema exporta en formatos compatibles con CONCAR, SIGO, SAP y SIRE para la contabilización automática.
- Los parámetros legales (UIT, RMV, tasas AFP) se actualizan en `Configuración > Parámetros Legales`.

---

## 8. Analytics & People Intelligence

### Qué hace

Proporciona dashboards ejecutivos con indicadores clave de Recursos Humanos en tiempo real. Combina datos de todos los módulos para ofrecer una visión 360° del capital humano: headcount, rotación, ausentismo, costos, riesgos y tendencias.

### Quién lo usa

Gerencia General y Gerencia de RRHH para la toma de decisiones estratégicas. Jefes de área para monitorear sus equipos.

### Cómo acceder

`Analytics` en el menú lateral izquierdo.

### Dashboards disponibles

#### Dashboard Principal
`Analytics > Dashboard` muestra el panorama general:

**KPIs de Minera Andes SAC**:
- Headcount total: 234 colaboradores
- STAFF: 193 (82%)
- RCO: 41 (18%)
- Áreas: 35
- Asistencia: 100% (ciclo actual)
- Rotación: 0% (últimos 12 meses)

**Señales por módulo** (alertas de atención):
- 20 vacaciones pendientes de aprobación
- 22 permisos pendientes
- 47 préstamos activos
- 2 capacitaciones en curso
- 50 evaluaciones pendientes
- 6 vacantes abiertas

**Gráficos incluidos**:
- Donut de distribución STAFF/RCO
- Rotación mensual (últimos 12 meses)
- Horas extras mensuales acumuladas

**Próximos cumpleaños**: listado de colaboradores que cumplen años en los próximos 7 días.

#### Dashboard IA
`Analytics > Dashboard IA` es el panel ejecutivo potenciado con inteligencia artificial:

**KPIs en tiempo real**:
- 151 contratos que vencen en los próximos 60 días
- 18 alertas activas de RRHH
- 4 períodos de prueba que finalizan en 15 días

**Gráficos interactivos**:
- Evolución del Headcount (últimos 12 meses)
- Rotación mensual con tendencia

**Mini chat IA inline**: permite hacer preguntas de texto directamente desde el dashboard sin abrir el chat flotante.

**Widgets pinneados**: los gráficos que el usuario fija desde el chat IA aparecen aquí como widgets personalizados.

#### Headcount Analytics
`Analytics > Headcount` ofrece análisis detallado de la plantilla:
- Distribución por área, subárea, cargo y nivel
- Pirámide etaria
- Distribución por género
- Antigüedad promedio
- Ingresos y salidas del período

#### Análisis Salarial
`Analytics > Salarios` compara la estructura salarial:
- Dispersión de sueldos por cargo
- Comparación vs. mercado (si se han cargado datos de benchmark)
- Equidad interna por género y área
- Compa-ratio promedio por nivel

#### Riesgo de Attrition
`Analytics > Riesgo Attrition` identifica empleados con mayor probabilidad de renuncia según indicadores como: ausentismo alto, evaluaciones bajas, tiempo sin incremento, etc.

#### Alertas de RRHH
`Analytics > Alertas` centraliza todas las alertas del sistema:
- Contratos próximos a vencer
- Vacaciones acumuladas en exceso
- Evaluaciones de desempeño vencidas
- Períodos de prueba por concluir
- Préstamos con cuotas atrasadas

#### Snapshots / Reportes Periódicos
`Analytics > Snapshots` guarda fotografías del estado del sistema en fechas clave (fin de mes, cierre de año) para análisis comparativo histórico.

### Notas importantes

- Los dashboards se actualizan en tiempo real al consultar.
- Los gráficos son interactivos: haga clic en las barras/segmentos para ver el detalle.
- Los **widgets del Dashboard IA** son personalizables por usuario — cada gerente puede configurar su propio panel.
- Los datos de rotación se calculan con la fórmula: (Salidas / Promedio Plantilla) x 100.

---

## 9. Módulo Reclutamiento

### Qué hace

Gestiona el proceso completo de selección de personal: publicación de vacantes, recepción de candidatos, evaluación en pipeline kanban, entrevistas y contratación. Incluye un portal de empleo público para postulantes externos.

### Quién lo usa

El equipo de Reclutamiento y RRHH. Jefes que solicitan posiciones. Candidatos externos a través del portal público.

### Cómo acceder

`Reclutamiento` en el menú lateral izquierdo.

### Funcionalidades principales

#### Panel de Vacantes
`Reclutamiento > Vacantes` muestra todas las posiciones abiertas:

**Minera Andes SAC**:
- 9 vacantes activas
- 15 candidatos en proceso
- 12 en pipeline kanban

**Indicadores clave**:
- Tasa de conversión (postulantes → contratados)
- Tiempo promedio de cierre de vacante

#### Crear vacante
1. `Reclutamiento > Nueva Vacante`
2. Complete: título del cargo, área, número de plazas, perfil requerido (competencias, experiencia, formación).
3. Defina el rango salarial y beneficios.
4. Seleccione si se publicará en el portal externo.
5. Establezca la fecha límite de postulación.
6. Active la vacante para recibir postulaciones.

#### Pipeline Kanban
`Reclutamiento > Pipeline` muestra los candidatos en tablero kanban por etapas:
- **Postulación**: candidatos que aplicaron
- **Revisión CV**: perfiles en evaluación inicial
- **Entrevista RR.HH.**: agendados para primera entrevista
- **Entrevista Técnica**: con el jefe del área
- **Oferta**: negociación y oferta formal
- **Contratado / Descartado**

Arrastre las tarjetas de candidato entre columnas para actualizar su estado.

#### Agendar entrevistas
`Reclutamiento > Entrevistas` permite:
- Programar entrevistas con candidatos
- Invitar entrevistadores internos
- Registrar resultados y puntajes
- Ver historial de entrevistas por candidato

#### Scoring de candidatos
`Reclutamiento > Scoring` evalúa candidatos con una rubrica predefinida:
- Competencias requeridas con ponderación
- Puntaje por entrevistador
- Puntaje final ponderado
- Ranking automático de candidatos

#### Portal de Empleo Público
Página pública accesible sin login para postulantes externos:
- Lista de vacantes abiertas con descripción y requisitos
- Formulario de postulación online
- Carga de CV y documentos
- Seguimiento del estado de la postulación

#### Publicar en plataformas externas
`Reclutamiento > Publicar` conecta con plataformas externas de empleo para publicar las vacantes en múltiples canales simultáneamente.

### Flujo de trabajo: proceso de selección

1. El jefe de área solicita una nueva posición.
2. RRHH crea la vacante en el sistema y la publica.
3. Los candidatos postulan por el portal o se cargan manualmente.
4. RRHH filtra candidatos y avanza los calificados al pipeline.
5. Se agendan entrevistas con los candidatos seleccionados.
6. Se registran puntajes de cada entrevistador.
7. Se elige al candidato final y se emite la oferta formal.
8. Al aceptar la oferta, se crea el registro en `Personal > Empleados` desde el perfil del candidato.
9. Se inicia automáticamente el proceso de Onboarding.

---

## 10. Módulo Capacitaciones

### Qué hace

Gestiona el plan de capacitación de la empresa como un LMS (Learning Management System) ligero: cursos, inscripciones, asistencia, requerimientos legales y certificaciones. Permite cumplir con las obligaciones de capacitación del Reglamento de SST y otras normativas.

### Quién lo usa

RRHH para planificar y registrar capacitaciones. Jefes para ver el estado de su equipo. Empleados para ver sus capacitaciones y descargar certificados.

### Cómo acceder

`Capacitaciones` en el menú lateral izquierdo.

### Funcionalidades principales

#### Panel de Capacitaciones
`Capacitaciones > Panel` muestra el estado del plan de capacitación:

**Minera Andes SAC (2026)**:
- 8 capacitaciones programadas
- 85% de empleados capacitados (199 de 234)
- 24 horas capacitadas promedio por persona
- 4 certificaciones próximas a vencer

**Top cursos por inscripción**:
1. Power BI para RR.HH. — 234 inscritos
2. Negociación y Comunicación — 226 inscritos

**Gráficos**: distribución de capacitaciones por categoría (seguridad, habilidades blandas, técnico, etc.)

#### Crear capacitación
1. `Capacitaciones > Nueva Capacitación`
2. Complete: nombre, categoría, instructor, modalidad (presencial/virtual), fechas, duración en horas.
3. Defina el aforo máximo.
4. Active la inscripción para que los empleados puedan registrarse.

#### Inscripción masiva
`Capacitaciones > Asignación Masiva` permite inscribir grupos de empleados de una vez:
- Por área o subárea completa
- Por cargo o nivel
- Por selección manual

#### Asistencia a capacitaciones
Registre la asistencia al finalizar cada sesión. Los empleados que no asistieron pueden ser reagendados.

#### Requerimientos de capacitación
`Capacitaciones > Requerimientos` gestiona las capacitaciones obligatorias por cargo o área:
- Inducción general (todos los empleados nuevos)
- Capacitación en SST (obligatoria por ley, mínimo 4 horas al año)
- Capacitaciones técnicas por cargo
- El sistema alerta cuando un empleado no ha cumplido sus requerimientos

#### Certificaciones
`Capacitaciones > Certificaciones` controla los certificados con fecha de vencimiento:
- Licencias de manejo
- Certificaciones técnicas
- Cursos de seguridad que requieren renovación
- Alerta automática cuando la certificación está por vencer

### Notas importantes

- Las capacitaciones en SST son **obligatorias por ley** (Ley 29783). El sistema facilita su seguimiento y reporte ante la autoridad fiscalizadora.
- Los certificados generados por el sistema tienen firma del instructor y del responsable de RRHH.
- El historial de capacitaciones es parte del perfil del empleado y se puede ver en la pestaña **Desarrollo** de la ficha personal.

---

## 11. Módulo Evaluaciones de Desempeño

### Qué hace

Gestiona el ciclo completo de evaluación de desempeño: evaluaciones 360°, objetivos (OKR), 9-Box Grid, comparativa de competencias y Planes de Desarrollo Individual (PDI). Permite medir el rendimiento del personal de forma objetiva y estructurada.

### Quién lo usa

RRHH para configurar ciclos y plantillas. Jefes para evaluar a su equipo. Empleados para autoevaluarse y ver sus resultados.

### Cómo acceder

`Evaluaciones` en el menú lateral izquierdo.

### Funcionalidades principales

#### Dashboard de Evaluaciones
`Evaluaciones > Dashboard` muestra el estado del proceso:

**Minera Andes SAC**:
- 190 evaluaciones totales en el sistema
- 50 evaluaciones pendientes activas
- Puntaje global promedio: 81.9%
- 2 ciclos cerrados

**Ciclo Q1 2026** (en curso):
- 62% de avance
- En fase de evaluación

**9-Box Grid actual**:
- 7 colaboradores en casilla "Estrella" (alto desempeño, alto potencial)
- 7 en "Alto Potencial"
- 11 en "Núcleo" (desempeño promedio, potencial medio)

#### Ciclos de evaluación
`Evaluaciones > Ciclos` gestiona los períodos de evaluación:
- Crear un nuevo ciclo (nombre, fechas de inicio y cierre)
- Seleccionar la plantilla de evaluación a usar
- Definir quiénes serán evaluados (toda la empresa o grupos específicos)
- Monitorear el avance

#### Plantillas de evaluación
`Evaluaciones > Plantillas` define las rúbricas de evaluación:
- Competencias evaluadas (liderazgo, trabajo en equipo, orientación a resultados, etc.)
- Ponderación de cada competencia
- Escala de calificación (numérica, descriptiva)
- Tipo: autoevaluación, evaluación del jefe, 360° (pares + subordinados)

#### Completar una evaluación
1. El evaluador recibe notificación de evaluación pendiente.
2. Ingresa a `Evaluaciones > Mis Evaluaciones` o al link del correo.
3. Selecciona la evaluación pendiente.
4. Para cada competencia, asigna una calificación y agrega comentarios.
5. Revisa el resumen y hace clic en **Enviar Evaluación**.

#### 9-Box Grid
`Evaluaciones > 9-Box Grid` posiciona automáticamente a cada empleado en la matriz:
- Eje X: Desempeño (resultado de la evaluación)
- Eje Y: Potencial (evaluación específica de potencial)
- 9 casillas: de "Necesita Apoyo" a "Estrella"

Permite identificar a los talentos clave y a quienes necesitan planes de mejora.

#### OKRs (Objetivos y Resultados Clave)
`Evaluaciones > OKRs` gestiona los objetivos individuales y de equipo:
- Definir objetivos trimestrales o anuales
- Establecer resultados clave medibles (con métricas numéricas)
- Seguimiento de avance en tiempo real
- Vinculación con la evaluación de desempeño

#### Planes de Desarrollo Individual (PDI)
`Evaluaciones > PDI` permite crear planes de acción personalizados:
- Áreas de mejora identificadas en la evaluación
- Acciones específicas con responsable y fecha
- Seguimiento del cumplimiento del plan

#### Comparativa de Competencias
`Evaluaciones > Competencias` muestra un radar chart comparando las competencias de un empleado contra el perfil ideal del cargo.

### Flujo de trabajo: ciclo de evaluación trimestral

1. **RRHH**: Crea el ciclo en `Evaluaciones > Ciclos > Nuevo Ciclo`.
2. **RRHH**: Configura la plantilla, fechas y participantes.
3. **Sistema**: Envía notificaciones a evaluadores y evaluados.
4. **Empleados**: Completan la autoevaluación.
5. **Jefes**: Completan la evaluación de sus reportes directos.
6. **Pares/Subordinados** (si es 360°): completan sus evaluaciones.
7. **RRHH**: Monitorea el avance y envía recordatorios a los rezagados.
8. **Al cerrar el ciclo**: El sistema calcula puntajes ponderados y actualiza el 9-Box Grid.
9. **RRHH y Jefes**: Realizan sesiones de feedback con cada colaborador.
10. **PDI**: Se crean planes de desarrollo para empleados con oportunidades de mejora.

---

## 12. Módulo Encuestas y Clima Laboral

### Qué hace

Permite medir el clima organizacional, el compromiso (engagement) y el índice eNPS (Employee Net Promoter Score) a través de encuestas periódicas con anonimato real garantizado.

### Quién lo usa

RRHH para crear y gestionar encuestas. Gerencia para revisar resultados. Empleados para responder encuestas desde el Portal.

### Cómo acceder

`Encuestas` en el menú lateral izquierdo.

### Funcionalidades principales

#### Panel de Encuestas
`Encuestas > Panel` muestra el estado de todas las encuestas:

**Minera Andes SAC**:
- 4 encuestas en el sistema
- 2 encuestas activas:
  - Clima Laboral Q1-2026 (en curso)
  - eNPS Q1-2026 (en curso)
- 460 respuestas recibidas este mes

#### Crear encuesta
1. `Encuestas > Nueva Encuesta`
2. Defina: nombre, tipo (clima / eNPS / pulso / satisfacción), fechas activas.
3. Configure el anonimato: **real** (no se puede rastrear al respondente) o **relativo** (anonimato por área).
4. Diseñe las preguntas: escala Likert, opción múltiple, texto libre, NPS (0-10).
5. Seleccione la audiencia (toda la empresa o grupos específicos).
6. Active la encuesta para que esté disponible en el Portal.

#### Encuesta eNPS
El **Employee Net Promoter Score** pregunta: "En una escala del 0 al 10, ¿qué tan probable es que recomiendes esta empresa como lugar de trabajo?"

- Promotores (9-10): empleados satisfechos y comprometidos
- Neutros (7-8): satisfechos pero no entusiastas
- Detractores (0-6): empleados insatisfechos

**Fórmula**: eNPS = % Promotores − % Detractores. Rango: −100 a +100.

#### Resultados y análisis
`Encuestas > Resultados` muestra:
- Tasa de respuesta
- Resultados por pregunta con gráficos
- Comparación entre períodos (¿el clima mejoró respecto al trimestre anterior?)
- Resultados por área (cuando el anonimato lo permite)
- Comentarios cualitativos anonimizados

#### Pulsos rápidos
Las encuestas tipo **pulso** son de 3-5 preguntas, se envían frecuentemente (semanal o quincenal) y toman menos de 2 minutos en completar. Permiten monitorear el clima de forma continua sin fatiga de encuesta.

### Notas importantes

- El **anonimato real** significa que ni RRHH ni ningún administrador puede identificar qué empleado respondió qué. Las respuestas se procesan de forma agregada.
- Se recomienda no enviar encuestas de clima a grupos de menos de 5 personas para proteger el anonimato.
- La frecuencia recomendada: una encuesta de clima completa al año + pulsos trimestrales + eNPS semestral.

---

## 13. Módulo Disciplinaria

### Qué hace

Gestiona los procesos disciplinarios laborales conforme al DS 003-97-TR (Ley de Productividad y Competitividad Laboral). Documenta las faltas graves, los procedimientos de descargo y las medidas disciplinarias aplicadas, con control de plazos legales.

### Quién lo usa

RRHH y la Gerencia Legal/Gerencia General para los procesos formales. Los jefes de área para iniciar el proceso cuando detectan una infracción.

### Cómo acceder

`Disciplinaria` en el menú lateral izquierdo.

### Funcionalidades principales

#### Dashboard Disciplinario
`Disciplinaria > Dashboard` muestra el estado de todos los procesos:

**Minera Andes SAC**:
- 7 medidas en el año 2026
- 4 procesos en curso
- 3 pendientes de descargo
- 3 resueltos
- Alertas de plazos vencidos destacadas en rojo

#### Tipos de falta grave (15 tipos según DS 003-97-TR)
El sistema incluye los 15 tipos de falta grave tipificados:
1. Incumplimiento de obligaciones de trabajo
2. Desobediencia a las órdenes del empleador
3. Falta de honradez
4. Violencia o actos de indisciplina
5. Injuria al empleador o representantes
6. Abandono de trabajo (3 días injustificados)
7. Impuntualidad reiterada (más de 3 tardanzas en 30 días)
8. Hostigamiento sexual
9. Utilización o entrega a terceros de información reservada
10. Sustracción o daño intencional a los bienes del empleador
11. Inasistencias injustificadas (3 consecutivas o 5 en 15 días)
12. Conductas de acoso moral
13. Concurrir al trabajo bajo efectos del alcohol o drogas
14. Rendimiento deficiente (previa advertencia)
15. Negativa injustificada a someterse a exámenes médicos

#### Crear proceso disciplinario
1. `Disciplinaria > Nuevo Proceso`
2. Seleccione el empleado involucrado.
3. Seleccione el tipo de falta.
4. Ingrese la descripción detallada de los hechos con fecha y lugar.
5. Adjunte las pruebas (documentos, correos, reportes).
6. El sistema genera automáticamente la **Carta de Pre-Aviso** con los plazos legales.

#### Proceso de descargo
El empleado tiene derecho a responder los cargos. El sistema controla el plazo legal (6 días hábiles para presentar descargo):
1. Se notifica al empleado la apertura del proceso.
2. El empleado presenta su descargo (por escrito o en audiencia).
3. RRHH registra el descargo en el sistema.
4. El sistema alerta cuando el plazo está por vencer.

#### Medidas disciplinarias
Según la gravedad y el resultado del proceso:
- **Amonestación verbal**: sin registro formal en el expediente
- **Amonestación escrita**: queda en el legajo del trabajador
- **Suspensión sin goce**: días de suspensión sin pago
- **Despido por falta grave**: previa carta de despido

#### Control de plazos
El sistema alerta cuando los plazos legales están próximos a vencer:
- Amarillo: 2 días antes del vencimiento
- Rojo: plazo vencido

### Notas importantes

- Todo proceso disciplinario debe seguir el procedimiento legal. Saltarse pasos puede generar una demanda por despido arbitrario.
- La **carta de pre-aviso** debe indicar la causa específica del despido y el período dentro del cual el trabajador puede presentar su descargo.
- Recomendamos siempre consultar con asesoría legal antes de ejecutar un despido por falta grave.
- El sistema genera los documentos formales (cartas, notificaciones) con los datos del empleado y la empresa ya completados.

---

## 14. Módulo Préstamos y Adelantos

### Qué hace

Gestiona los préstamos que la empresa otorga a sus empleados y los adelantos de sueldo o gratificación. Controla el cronograma de cuotas, los descuentos en planilla y el saldo pendiente.

### Quién lo usa

RRHH y el área de Nóminas para registrar y aprobar préstamos. Empleados para ver el estado de sus préstamos desde el Portal.

### Cómo acceder

`Préstamos` en el menú lateral izquierdo.

### Funcionalidades principales

#### Panel de Préstamos
`Préstamos > Panel` muestra el estado de todos los préstamos:

**Minera Andes SAC**:
- 133 préstamos en el sistema
- 47 en curso (cuotas pendientes)
- 24 pendientes de aprobación
- S/ 79,000 saldo total pendiente
- 0 cuotas vencidas

#### Registrar nuevo préstamo
1. `Préstamos > Nuevo Préstamo`
2. Seleccione el empleado.
3. Tipo: Préstamo / Adelanto de Sueldo / Adelanto de Gratificación.
4. Monto solicitado.
5. Número de cuotas y monto por cuota.
6. Fecha de inicio del descuento.
7. El sistema genera automáticamente el cronograma de pagos.
8. Envíe a aprobación del jefe de área y/o gerencia según política.

#### Aprobar préstamo
1. `Préstamos > Pendientes de Aprobación`
2. Revise la solicitud del empleado.
3. Verifique que el descuento mensual no supere el 30% de su remuneración neta (límite recomendado).
4. Apruebe o rechace con comentario.

#### Cronograma de cuotas
Cada préstamo muestra:
- Tabla de cuotas: número, fecha, monto, estado (pagada / pendiente / vencida)
- Progreso visual (barra de avance)
- Saldo pendiente total

Las cuotas se descuentan automáticamente en el proceso de nómina del mes correspondiente.

#### Adelantos de gratificación
Los adelantos de gratificación se registran y descuentan en el pago de julio o diciembre según corresponda.

### Notas importantes

- El descuento por préstamos en planilla no puede exceder el **70% del sueldo líquido** del trabajador (límite legal de embargabilidad).
- Si un empleado renuncia o es cesado, el saldo pendiente del préstamo se descuenta de su liquidación final.
- Los préstamos sin interés otorgados a trabajadores no están afectos a impuestos adicionales si cumplen con los límites establecidos por SUNAT.

---

## 15. Módulo Estructura Salarial

### Qué hace

Define y gestiona las bandas salariales de la empresa: rangos mínimo-medio-máximo por cargo y nivel. Permite analizar la equidad interna, calcular el compa-ratio de cada empleado y simular el impacto de incrementos salariales.

### Quién lo usa

RRHH y la Gerencia para definir la política salarial. El área de Compensaciones para mantener la equidad interna.

### Cómo acceder

`Salarios` en el menú lateral izquierdo.

### Funcionalidades principales

#### Bandas Salariales
`Salarios > Bandas` muestra todas las bandas definidas:

**Minera Andes SAC**:
- 131 bandas activas
- 205 empleados cubiertos por una banda
- 100% de empleados en rango (ninguno fuera de su banda)
- Compa-ratio global: 1.000 (promedio en punto medio)

**Gráfico de bandas** (Min/Medio/Máx por nivel):
- Junior
- Semi Senior
- Senior
- Lead
- Gerente

#### Crear banda salarial
1. `Salarios > Nueva Banda`
2. Seleccione el cargo o grupo de cargos.
3. Ingrese los valores mínimo, punto medio y máximo de la banda.
4. Defina la vigencia (fecha de inicio y fin).

#### Compa-ratio
El **compa-ratio** mide dónde está el sueldo de un empleado dentro de su banda:
- **Compa-ratio < 1**: empleado por debajo del punto medio (posiblemente underpaid)
- **Compa-ratio = 1**: empleado exactamente en el punto medio
- **Compa-ratio > 1**: empleado por encima del punto medio

Fórmula: Compa-ratio = Sueldo actual / Punto medio de la banda

#### Equidad Salarial
`Salarios > Equidad` analiza si existen brechas salariales injustificadas:
- Comparación por género
- Comparación por antigüedad
- Identificación de outliers (sueldos fuera de rango)

#### Simulador de Incrementos
`Salarios > Simulaciones` permite proyectar el costo de diferentes escenarios de incremento:
1. Cree una nueva simulación.
2. Defina el criterio: incremento fijo (%), incremento por meritocracia, ajuste a banda.
3. Seleccione el grupo objetivo (toda la empresa, un área, un nivel).
4. El sistema calcula el impacto en la planilla mensual y anual.
5. Compare múltiples escenarios y exporte a Excel para presentar a gerencia.

### Notas importantes

- La RMV (Remuneración Mínima Vital) es el límite inferior absoluto. Ninguna banda puede tener un mínimo por debajo de S/ 1,025.
- Se recomienda revisar las bandas salariales una vez al año y ajustarlas a la UIT vigente y a las condiciones del mercado laboral.
- Los empleados fuera de rango (por encima del máximo) son marcados en rojo para su revisión.

---

## 16. Módulo Onboarding y Offboarding

### Qué hace

Gestiona los procesos de incorporación (onboarding) y salida (offboarding) de los colaboradores a través de checklists configurables por área y cargo. Garantiza que ningún paso se omita y que la experiencia del nuevo empleado sea positiva desde el primer día.

### Quién lo usa

RRHH para crear y supervisar procesos. Los responsables de cada paso (TI, Seguridad, Jefe de área) para completar sus tareas asignadas. El nuevo empleado para seguir su propio proceso desde el Portal.

### Cómo acceder

`Onboarding` en el menú lateral izquierdo.

### Funcionalidades principales

#### Panel de Onboarding
`Onboarding > Panel` muestra todos los procesos activos:

**Minera Andes SAC**:
- 15 procesos en el sistema
- 6 en curso
- 7 completados
- 2 cancelados
- 38 pasos vencidos (requieren atención)

Cada proceso muestra una barra de avance porcentual.

#### Plantillas de onboarding
`Onboarding > Plantillas` permite crear plantillas reutilizables por cargo o área:
1. `Onboarding > Plantillas > Nueva Plantilla`
2. Defina el nombre (ej.: "Onboarding Ingeniero de Campo").
3. Agregue pasos con: descripción, responsable, días desde el ingreso para completarlo, documentos requeridos.

**Pasos típicos de onboarding**:
- Día 0: Preparar puesto de trabajo (TI)
- Día 0: Crear credenciales de acceso (Sistemas)
- Día 1: Firma de contrato (RRHH)
- Día 1: Entrega de EPP y uniformes (Almacén)
- Día 1: Inducción general de la empresa (RRHH)
- Día 1: Inducción SST (Seguridad)
- Día 3: Presentación al equipo (Jefe de área)
- Semana 1: Capacitación en sistemas internos (Sistemas)
- Mes 1: Evaluación de fin de período de prueba (RRHH)

#### Proceso de onboarding individual
1. Al contratar a un empleado, se activa automáticamente la plantilla correspondiente.
2. O ingrese a `Onboarding > Nuevo Proceso` y seleccione empleado + plantilla.
3. El sistema asigna cada paso al responsable y envía notificaciones.
4. Cada responsable marca su paso como completado al terminar.
5. El progreso es visible en tiempo real.

#### Offboarding
`Onboarding > Offboarding` gestiona las salidas del personal:

**Pasos típicos de offboarding**:
- Notificación de cese a todas las áreas
- Entrega de activos (laptop, credenciales, EPP)
- Liquidación final (RRHH/Nóminas)
- Encuesta de salida (opcional)
- Desactivación de accesos (TI)
- Firma de acta de entrega (Almacén)
- Carta de recomendación (si aplica)

#### Mi Onboarding (Portal del Empleado)
El nuevo empleado puede ver desde el Portal el estado de su proceso: qué pasos están completados, cuáles están pendientes y qué documentos necesita presentar.

### Notas importantes

- Los **pasos vencidos** (que debieron completarse en una fecha anterior y no se marcaron) se muestran en rojo y generan alertas en el Dashboard.
- El onboarding bien ejecutado reduce significativamente la rotación temprana (primeros 90 días).
- Se pueden crear diferentes plantillas para: empleados presenciales, remotos, ejecutivos, personal de campo, etc.

---

## 17. Módulo Comunicaciones

### Qué hace

Motor de notificaciones y comunicaciones internas. Permite enviar notificaciones automáticas del sistema, comunicados masivos y correos institucionales a grupos de empleados. Gestiona las plantillas de comunicación y el servidor de correo saliente.

### Quién lo usa

RRHH para comunicados masivos y notificaciones. Gerencia para comunicaciones institucionales. El sistema lo usa internamente para todas las notificaciones automáticas (aprobaciones, alertas, recordatorios).

### Cómo acceder

`Comunicaciones` en el menú lateral izquierdo.

### Funcionalidades principales

#### Panel de Comunicados
`Comunicaciones > Comunicados` lista todos los comunicados enviados o programados:
- Filtrar por estado (Borrador / Enviado / Programado)
- Ver estadísticas de apertura (si el servidor de correo lo soporta)

#### Crear comunicado
1. `Comunicaciones > Nuevo Comunicado`
2. Defina el asunto y el cuerpo del mensaje.
3. Use el editor de texto enriquecido para formato profesional.
4. Seleccione los destinatarios:
   - Todos los empleados
   - Por área o subárea
   - Por cargo o nivel
   - Lista manual de empleados
5. Adjunte archivos si necesita.
6. Envíe inmediatamente o programe para fecha y hora específica.

#### Plantillas de comunicación
`Comunicaciones > Plantillas` guarda plantillas reutilizables:
- Comunicados de cumpleaños
- Bienvenida a nuevos empleados
- Recordatorios de capacitación
- Comunicados de días no laborables
- Informes de nómina

#### Notificaciones del sistema
`Comunicaciones > Notificaciones` muestra el historial de todas las notificaciones automáticas enviadas por el sistema:
- Solicitudes de vacaciones aprobadas/rechazadas
- Alertas de contratos próximos a vencer
- Recordatorios de evaluaciones pendientes
- Alertas de cuotas de préstamos

#### Configuración SMTP
`Comunicaciones > Configuración SMTP` (solo Administradores):
- Servidor de correo saliente
- Puerto y protocolo (TLS/SSL)
- Credenciales de la cuenta de envío
- Correo remitente (ej.: noreply@minera-andes.com.pe)
- Prueba de conexión

#### Mis Notificaciones (Portal del Empleado)
Cada empleado puede ver en el Portal el historial de sus notificaciones recibidas del sistema.

---

## 18. Portal del Empleado

### Qué hace

Es el espacio personal de cada colaborador dentro de Harmoni. Permite al empleado consultar su información, realizar solicitudes y hacer seguimiento de sus trámites sin depender del área de RRHH para cada consulta.

### Quién lo usa

Todos los empleados de la empresa. Es el módulo de cara al colaborador.

### Cómo acceder

`Portal` en el menú lateral izquierdo. O directamente desde la URL del portal si el sistema tiene acceso separado para empleados.

### Secciones del Portal

#### Mi Resumen
Página principal del Portal. Muestra de un vistazo:
- Días de vacaciones disponibles
- Horas en banco de horas
- Préstamos vigentes
- Próximas capacitaciones
- Evaluaciones pendientes
- Últimas notificaciones

#### Mi Perfil
El empleado puede ver (y solicitar actualizar) sus datos personales:
- Foto de perfil
- Datos de contacto
- Número de cuenta bancaria
- AFP/ONP y datos de afiliación

Para modificar datos, el empleado envía una solicitud de cambio que RRHH debe aprobar.

#### Mi Asistencia
Vista del tareo personal del empleado:
- Marcaciones del mes (entrada/salida)
- Faltas, tardanzas, horas extras
- Comparación vs. horario esperado

#### Banco de Horas
Solo para empleados STAFF:
- Saldo de horas disponibles
- Historial de horas acumuladas y usadas
- Solicitar compensación (tomar horas del banco como días libres)

#### Mi Roster
Solo para personal foráneo:
- Cronograma de entradas y salidas programadas
- Fechas de vuelos (si están cargadas)

#### Mis Vacaciones
- Saldo disponible por año de servicio
- Historial de vacaciones tomadas
- Botón para **Solicitar Vacaciones**
- Estado de las solicitudes pendientes

#### Mis Permisos
- Historial de permisos y licencias
- Botón para **Solicitar Permiso** (por tipo: médico, personal, etc.)
- Estado de las solicitudes

#### Mis Justificaciones
- Justificar una falta o tardanza
- Adjuntar sustento (certificado médico, etc.)
- Estado de la justificación (pendiente / aprobada / rechazada)

#### Solicitudes HE
El empleado puede solicitar autorización previa para trabajar horas extras:
- Indicar fecha y horas estimadas
- El jefe recibe la solicitud para aprobar o rechazar
- Las HE pre-autorizadas se registran en el tareo al confirmarse

#### Mis Papeletas
- Solicitar papeleta de salida (durante horario de trabajo)
- Historial de papeletas anteriores

#### Mis Recibos (Boletas de Pago)
- Lista de boletas disponibles por mes
- Descargar PDF de la boleta
- Marcar "He leído mi boleta" (constancia de lectura)

#### Mis Evaluaciones
- Ver evaluaciones pendientes de completar
- Resultados de evaluaciones pasadas
- Plan de Desarrollo Individual asignado

#### Organigrama
Vista del organigrama de la empresa (sin datos de salarios) para que el empleado conozca la estructura organizacional.

#### Directorio
Directorio de contactos de todos los empleados: nombre, cargo, área, correo interno y teléfono de extensión.

### Notas importantes

- El Portal es **autoservicio**: reduce la carga operativa de RRHH en consultas repetitivas.
- Cada acción del empleado genera una solicitud en el módulo correspondiente de RRHH para su aprobación.
- El Portal está optimizado para móviles — los empleados pueden acceder desde su teléfono.

---

## 19. Harmoni AI — Asistente Inteligente

### Qué hace

Harmoni AI es el asistente inteligente integrado en el sistema. Permite hacer consultas en lenguaje natural sobre cualquier dato del sistema, generar gráficos interactivos, exportar reportes a Excel y obtener insights ejecutivos de forma instantánea.

### Quién lo usa

Principalmente Gerencia y RRHH para análisis rápidos y reportes ad-hoc.

### Cómo acceder

- **Botón flotante**: ícono de robot (esquina inferior derecha de cualquier pantalla)
- **Atajo de teclado**: `Ctrl + Shift + H`

### Interfaz del chat

Al abrir el chat, verá:
- **Área de conversación**: historial de mensajes con el asistente
- **Quick actions (chips)**: botones de acceso rápido para consultas frecuentes
- **Campo de texto**: para escribir su pregunta
- **Botón de clip**: para adjuntar archivos (PDF, Excel, imagen)
- **Botón de expandir**: para ver el chat en modo pantalla completa
- **Botón de cerrar**: para minimizar el chat sin perder el historial

### Quick Actions disponibles

Haga clic en cualquiera de estos chips para una consulta inmediata:

| Chip | Qué hace |
|------|----------|
| **Resumen** | Resumen ejecutivo del estado actual de RRHH |
| **Empleados** | Total de empleados y distribución |
| **Asistencia** | Estado de asistencia del ciclo actual |
| **Pendientes** | Todas las tareas pendientes de aprobación |
| **Contratos** | Contratos próximos a vencer |
| **Vacaciones** | Estado de vacaciones del período |
| **Capacitaciones** | Avance del plan de capacitación |
| **Evaluaciones** | Estado del ciclo de evaluación activo |
| **Por Área** | Distribución de empleados por área |
| **Género** | Distribución por género |
| **Por Edad** | Pirámide etaria del personal |
| **Dashboard** | Genera el dashboard ejecutivo completo |
| **Reporte Excel** | Exporta reporte ejecutivo en archivo .xlsx |
| **Ayuda** | Muestra los comandos disponibles |

### Consultas de ejemplo

**Consultas simples de datos:**
- "¿Cuántos empleados activos hay y cómo está la asistencia hoy?"
- "¿Cuántas vacaciones pendientes hay?"
- "¿Cuántos contratos vencen este mes?"
- "¿Qué empleados tienen más de 30 días de vacaciones acumuladas?"
- "Muéstrame las alertas de RRHH activas"

**Consultas con gráficos:**
- "Muéstrame un gráfico del personal por área"
- "Gráfico de horas extras por mes del año"
- "Donut de distribución STAFF vs RCO"
- "Evolución del headcount en los últimos 6 meses"

**Consultas con contexto (follow-up):**
El asistente recuerda el contexto de la conversación por 30 minutos. Puede hacer preguntas de seguimiento:
- "¿Cuántos empleados activos hay?" → "234"
- "¿Y cuántas son mujeres?" → El sistema entiende que se refiere a los empleados activos

**Dashboard Ejecutivo:**
Escriba "dashboard de gerencia" o haga clic en el chip **Dashboard**. El chat se expande automáticamente y muestra 4 gráficos en grid 2x2:
1. Distribución de Personal por Área (barras horizontales)
2. Evolución del Headcount (línea temporal)
3. Personal por Género (donut)
4. Personal por Tipo STAFF/RCO (donut)

**Exportar a Excel:**
Escriba "exportar reporte ejecutivo en Excel" o haga clic en el chip **Reporte Excel**. El sistema genera un archivo .xlsx con 4 hojas:
1. Resumen KPI (indicadores clave)
2. Headcount por Área (tabla completa)
3. Tendencias (datos mensuales)
4. Alertas Activas (pendientes urgentes)

Haga clic en el botón **Descargar Reporte Ejecutivo (.xlsx)** para guardar el archivo.

### Adjuntar documentos

Haga clic en el botón de **clip** para adjuntar:
- **PDF**: el sistema extrae el texto y puede responder preguntas sobre el contenido
- **Excel (.xlsx, .xls)**: puede analizar tablas, calcular totales, comparar datos
- **Imagen**: procesamiento OCR para documentos escaneados o fotos de documentos

**Ejemplo de uso:**
- Adjunte un extracto del T-Registro y pregunte: "¿Hay algún empleado registrado aquí que no esté en Harmoni?"
- Adjunte una planilla Excel antigua y pregunte: "¿Cuánto fue el costo de planilla en marzo 2025?"

### Modo maximizar

Haga clic en el botón de expandir (esquina superior derecha del chat) para ver el chat en pantalla completa. Ideal para visualizar los gráficos ejecutivos en mayor tamaño.

### Pin al Dashboard IA

Cuando el asistente genera un gráfico, aparece un botón **Pin al Dashboard**. Al hacer clic, el gráfico queda fijado en `Analytics > Dashboard IA` como widget personalizado. Cada usuario tiene su propio panel IA personalizable.

### Modo fallback (sin IA configurada)

Si el sistema no tiene un proveedor de IA configurado, el asistente funciona en **modo fallback**: responde consultas directas de datos del sistema usando lógica interna, sin capacidad de lenguaje natural avanzado. Las consultas directas de datos siguen funcionando normalmente.

### Notas importantes

- El contexto conversacional dura **30 minutos**. Después de ese tiempo, el asistente comienza una nueva conversación sin recordar el historial anterior.
- Para mejor rendimiento, sea específico en sus preguntas: "empleados del área de Geología con más de 5 años" es mejor que "empleados antiguos".
- Los datos que muestra el AI son en tiempo real, tomados directamente de la base de datos de Harmoni.
- La configuración del proveedor de IA se realiza en `Configuración > Inteligencia Artificial`.

---

## 20. Configuración del Sistema

### Qué hace

Permite al Administrador parametrizar todos los aspectos del sistema: parámetros legales (UIT, RMV), feriados, tipos de permiso, configuración de correo, integraciones y mucho más.

### Quién lo usa

Exclusivamente el Administrador del sistema.

### Cómo acceder

`Configuración` en el menú lateral izquierdo (visible solo para Administradores).

### Secciones de configuración

#### Parámetros Generales
- Nombre y datos de la empresa
- Logo corporativo
- Moneda y formato de números
- Zona horaria y formato de fecha

#### Parámetros Legales (Perú)
- **UIT**: Unidad Impositiva Tributaria vigente
- **RMV**: Remuneración Mínima Vital
- **Tasas AFP**: comisión por administradora (Integra, Prima, Profuturo, Habitat)
- **Tasa ONP**: 13%
- **Tasas IR 5ta Categoría**: tramos y porcentajes vigentes

#### Feriados
Lista de feriados oficiales del año. El sistema incluye todos los feriados nacionales del Perú. Se pueden agregar feriados regionales o días no laborables de la empresa.

#### Tipos de contrato
Configurar los tipos de contrato disponibles:
- Plazo indeterminado (sin fecha de fin)
- Plazo fijo: servicio específico, obra determinada, inicio de actividad, etc.
- Por necesidades del mercado

#### Configuración de Horarios
Definir los horarios de trabajo y tolerancias:
- Hora de entrada y salida por turno
- Tolerancia de tardanza (ej.: 5 minutos)
- Turnos rotativos

#### Gestión de Usuarios y Accesos
- Crear usuarios del sistema
- Asignar roles (Admin, RRHH, Jefe, Empleado)
- Sincronizar usuarios con empleados del sistema

#### Configuración SMTP (correo saliente)
- Servidor de correo, puerto y protocolo
- Credenciales de la cuenta de envío
- Prueba de conexión

#### Inteligencia Artificial
- Proveedor de IA: GEMINI / DEEPSEEK / OPENAI / OLLAMA / NINGUNO
- API Key del proveedor (encriptada en la base de datos)
- Modelo a usar
- Proveedor OCR para documentos escaneados

#### Integraciones
- **T-Registro**: exportación en formato SUNAT para declaración de altas y bajas
- **PLAME**: exportación de planilla mensual para AFP Net
- **Biométrico ZKTeco**: configuración del reloj biométrico para importación automática
- **Sistemas contables**: CONCAR, SIGO, SAP, SIRE

---

## 20.4 Conceptos Remunerativos Configurables

Harmoni permite configurar todos los conceptos de planilla (ingresos, descuentos, aportes) con sus flags de afectación legal y mapeo SUNAT.

**URL:** `/nominas/conceptos/configurar/`

### Qué se configura en cada concepto

#### 📋 Identidad
- **Código (slug):** identificador único (ej. `vale_canasta`)
- **Nombre:** texto visible
- **Categoría:** 15 categorías (Sueldo, Bonificación, Comisión, Alimentación, Movilidad, etc.)
- **Tipo:** Ingreso / Descuento trabajador / Aporte empleador
- **Subtipo:** Remunerativo / No remunerativo / Provisión

#### 🧮 Fórmula
- **FIJO:** Monto en S/ fijo (Ej: Vale canasta S/ 200)
- **PORCENTAJE:** % sobre remuneración computable (Ej: Bonif riesgo 5%)
- **HE_25 / HE_35 / HE_100:** Horas extras según %
- **AFP_APORTE / AFP_COMISION / AFP_SEGURO:** Cálculos AFP
- **ONP:** 13% sistema nacional
- **ESSALUD:** 9% empleador
- **IR_5TA:** Retención impuesto a la renta 5ta categoría
- **GRATIFICACION / CTS:** Provisiones
- **MANUAL:** Entrada manual por trabajador

#### ⚖️ Afectaciones legales (7 flags críticas)
| Flag | Significado |
|---|---|
| `afecto_essalud` | Afecto a aporte ESSALUD 9% del empleador |
| `afecto_afp` | Afecto a AFP (10% aporte + comisión + prima) |
| `afecto_onp` | Afecto a ONP 13% |
| `afecto_renta` | Afecto a IR 5ta categoría |
| `afecto_cts` | Computa para CTS (mayo/nov) |
| `afecto_gratif` | Computa para Gratificación (jul/dic) |
| `afecto_vacaciones` | Computa para vacaciones truncas al cese |

#### 🏛️ Mapeo SUNAT / PLAME
- **Código PLAME:** código oficial SUNAT del concepto (4 dígitos)
- **Casilla PLAME:** columna del archivo plano
- **Código T-Registro:** código SUNAT para alta/baja

### 28 Templates pre-armados

**URL:** `/nominas/conceptos/configurar/templates/`

Aplicar con 1 click. Vienen con todas las afectaciones y código PLAME oficial SUNAT.

| Categoría | Conceptos disponibles |
|---|---|
| **Ingresos remunerativos** | Sueldo básico (0121), Asig familiar (0201), Comisiones (0103), HE 25%/35% (0105/0106), Asig vacacional (0210), Vacaciones truncas (0114), Bonif riesgo (0202), Bono desempeño (0307) |
| **Ingresos NO remunerativos** | Canasta (0903), Movilidad (0908), Refrigerio (0914), Prestación alimentaria (0112), Propinas/Recargo/Asig escolar (0925) |
| **Descuentos trabajador** | ONP (0607), AFP aporte/comisión/seguro (0608/0609/0610), IR 5ta (0605), EPS aporte (0611), Mandato judicial (0703), Préstamo (0704), Adelanto (0705) |
| **Aportes empleador** | ESSALUD 9% (0804), EPS crédito (0807), SCTR Salud/Pensión (0812/0813) |
| **Gratif/CTS** | Gratif Fiestas Patrias (0301), Gratif Navidad (0302), Bonif extraord gratif (0312), CTS provisión (0904) |

### 🔥 Caso especial: EPS y Bonificación Extraordinaria

Cuando un trabajador está afiliado a una **EPS particular** (Rímac, Pacífico, etc.), las gratificaciones cambian:

| Concepto | Sin EPS | Con EPS |
|---|---:|---:|
| **Bonificación extraordinaria** (Ley 30334 / 29351) | 9.00% | **6.75%** |
| **ESSALUD efectivo** del empleador sobre gratif | 9.00% | **6.75%** |

La diferencia de 2.25% se va al aporte de la EPS particular (Ley 26790 art. 15).

**Harmoni lo aplica automáticamente** cuando `Personal.tiene_eps = True`. La boleta muestra el % efectivo correcto.

### Comando para inicializar conceptos en cliente nuevo

```bash
# Crea los 28 conceptos base con códigos PLAME
docker exec harmoni-web python manage.py seed_conceptos_base

# Solo actualizar códigos PLAME (no crear nuevos)
docker exec harmoni-web python manage.py seed_conceptos_base --update-plame

# Reset (CUIDADO — borra conceptos no-sistema)
docker exec harmoni-web python manage.py seed_conceptos_base --reset
```

---

## 20.6 Liquidación al Cese

Al dar de baja a un trabajador, Harmoni calcula automáticamente todos los beneficios pendientes.

**URL:** `/nominas/liquidaciones/`

### Beneficios cubiertos

1. **CTS trunca** — proporcional a meses trabajados en el semestre actual no depositados
2. **Gratificación trunca** — proporcional a meses trabajados en el semestre del cese
3. **Bonificación extraordinaria trunca** — 9% (o 6.75% con EPS) sobre gratif trunca
4. **Vacaciones truncas** — 1/12 sueldo por mes trabajado, no descansadas
5. **Aguinaldo** (si aplica al régimen)
6. **Saldos pendientes** — días trabajados del mes de cese

### Flujo

1. Marcar trabajador como `Cesado` con `fecha_cese` y `motivo_cese`
2. Entrar a `/nominas/liquidaciones/<id_trabajador>/`
3. Sistema calcula automáticamente
4. Click "Generar PDF" → documento firmable
5. Imprimir + firma física, archivar en legajo

### Marco legal cubierto
- Art. 21 LRJ (D.S. 003-97-TR)
- Ley 27735 (Gratificaciones — bonif extraordinaria)
- Ley 26790 (EPS y crédito empleador)
- D.Leg. 650 (CTS)
- D.Leg. 713 (Vacaciones)

---

## 20.7 Audit Log de Conceptos (Bitácora de Cambios)

**Compliance fiscal + diagnóstico**: cada cambio en cualquier concepto remunerativo queda registrado automáticamente.

### Acceso
**Menú → Nóminas → Conceptos → Audit log** (botón en barra superior)
URL: `/nominas/conceptos/configurar/audit-log/`

### Qué se captura
- **Acción**: CREATE, UPDATE, DELETE, ACTIVAR, DESACTIVAR, AUTOFIX, TEMPLATE, CSV_IMPORT
- **Detalle**: campo modificado + valor anterior + valor nuevo
- **Quién**: usuario (username congelado aunque luego se elimine)
- **Dónde**: IP de origen, URL/vista que generó el cambio
- **Cuándo**: timestamp con segundos de precisión

### Filtros disponibles
- Por **código** de concepto (búsqueda parcial)
- Por **usuario** que hizo el cambio
- Por **acción** específica (ej: solo DELETE)
- Por **rango de tiempo** (24h, 7 días, 30 días, 90 días)

### Historial por concepto
Desde la pantalla de editar cualquier concepto → botón **"Ver historial"** muestra el timeline visual completo de ese concepto específico.

### Export CSV
Botón **"Export CSV"** en la bitácora descarga los logs filtrados como CSV para auditorías externas, archivado o análisis offline. Hasta 5,000 filas por export.

### Retención
Por defecto los logs se conservan indefinidamente. Para implementar retention policy:
```bash
python manage.py cleanup_audit_logs --dias 365              # purga > 1 año
python manage.py cleanup_audit_logs --dias 730 --dry-run    # simulación 2 años
python manage.py cleanup_audit_logs --conservar-creates     # mantiene CREATE/DELETE
```

### Casos de uso reales
1. **Auditoría fiscal**: "¿quién cambió la flag afecto_renta del concepto X antes del cierre de mes?"
2. **Recuperación**: "¿cómo estaba configurado este concepto hace 2 semanas? Volvámoslo así."
3. **Diagnóstico**: "Este mes la planilla salió diferente. ¿Algún concepto cambió en los últimos 30 días?"

---

## 20.8 Validador de Onboarding

**¿Está mi empresa lista para procesar planilla en producción?** Una sola página responde con un score 0-100 y los pasos faltantes.

### Acceso
**Menú → Nóminas → Validador Onboarding**
URL: `/nominas/onboarding/validador/`

### Categorías que verifica
1. **Empresa**: RUC, razón social, representante legal, logo, dirección
2. **Conceptos & PLAME**: cantidad activos, críticos (sueldo, ESSALUD, IR), códigos PLAME asignados
3. **Personal**: trabajadores cargados, CUSPP en AFP, fecha de alta
4. **Planilla**: períodos generados, aprobados, saldos de apertura
5. **Tasas legales**: AFPs configuradas y vigentes

### Score
- **≥ 90**: ¡Empresa lista para producción!
- **70-89**: Configuración mejorable (warnings)
- **< 70**: Requiere atención inmediata (hay errors)

Cálculo: 100 − penalización proporcional al peso de cada check.
Cada **error** resta su peso completo (0-100); cada **warning** resta el 50%; los OK e info no penalizan.

### Próximas acciones priorizadas
La página muestra el **Top 5 de acciones recomendadas** ordenadas por severidad y peso, con un botón "Resolver" que lleva directamente a la pantalla del fix.

### Reporte PDF
Botón **"Descargar PDF"** genera un reporte profesional para enviar al cliente. Útil como evidencia de configuración o sales asset ("Aquí está la prueba de que tu sistema está al 95%").

### API JSON
Endpoint integrable: `GET /api/v1/nominas/onboarding/` devuelve el score completo en JSON. Útil para:
- Health-checks de CI/CD
- Dashboards externos
- Alertas automáticas (ej: Slack si score < 80)

---

## 20.9 Mi Día Nóminas

**Dashboard personal del admin RR.HH.** Responde a "¿Qué tengo que hacer hoy en planilla?".

### Acceso
**Menú → Nóminas → Mi Día Nóminas** (al tope del menú)
URL: `/nominas/mi-dia/`

### Bloques
1. **Saludo personalizado**: "Buenos días, [tu nombre]" + fecha actual
2. **Pendientes recomendados (smart actions)**: detecta automáticamente según estado real:
   - Período en BORRADOR → "Generar planilla"
   - Período CALCULADO → "Aprobar planilla"
   - Período APROBADO sin contabilizar → "Exportar asiento contable"
   - ≥5 acuses sin firmar → "Notificar trabajadores"
   - Inconsistencias en conceptos → "Revisar configuración"
   - Período APROBADO → "Exportar PLAME"
3. **Período actual**: KPIs en vivo (trabajadores, bruto, descuentos, neto)
4. **Cambios recientes 7 días**: últimos audit logs con link al detalle
5. **Hoy / Esta semana / Próximas 4 semanas**: calendario laboral peruano
   - Gratificación julio/diciembre (15)
   - CTS mayo/noviembre (15)
   - IR 5ta Categoría enero (31)
   - Utilidades marzo (31)
6. **Status compacto**: acuses pendientes, inconsistencias, cambios 7d

### API JSON (mobile-ready)
Endpoint: `GET /api/v1/nominas/mi-dia/` devuelve el dashboard completo en JSON, listo para consumir desde apps mobile futuras.

---

## 20.10 Snapshot y Restore de Conceptos

Para backup defensivo antes de cambios masivos o migración entre ambientes.

### Crear snapshot
```bash
python manage.py snapshot_conceptos                          # snapshots/conceptos_YYYYMMDD_HHMMSS.json
python manage.py snapshot_conceptos --label "antes-bulk"     # con etiqueta
python manage.py snapshot_conceptos --out /tmp/backup.json   # destino custom
```

### Restaurar
```bash
# Modo MERGE (default — UPSERT por código)
python manage.py snapshot_conceptos --restore backup.json --dry-run    # simulación
python manage.py snapshot_conceptos --restore backup.json

# Modo RESET (borra los no-sistema y recrea)
python manage.py snapshot_conceptos --restore backup.json --strategy reset
```

### Casos de uso
- **Pre-bulk action**: antes de ejecutar auto-fix masivo o CSV import grande
- **Migración**: snapshot de prod → restore en demo (o entre clientes)
- **Recuperación**: alguien sobreescribió 30 conceptos por error → restore en 5 segundos

### Compliance
Todas las operaciones de restore quedan registradas en el **audit log** con el usuario superuser que ejecutó el comando y la acción `UPDATE`/`CREATE` según corresponda.

---

## 20.5 Planes Comerciales (Starter / Profesional / Business / Enterprise)

Harmoni tiene 4 planes según el tamaño de tu empresa:

| Plan | Precio (S/) | Colaboradores | Para |
|---|---:|---:|---|
| **Starter** | 149/mes | hasta 30 | Empresas pequeñas, planilla básica |
| **Profesional** | 399/mes | hasta 100 | PYMEs con reclutamiento y capacitación |
| **Business** | 799/mes | hasta 300 | Empresas medianas con IA y BI |
| **Enterprise** | Personalizado | 300+ | Holdings multi-empresa |

### ¿Qué incluye el Plan Starter (S/149/mes)?

**Sí incluye** (lo mínimo necesario para correr planilla):
- Personal — alta, baja, edición básica
- Asistencia y papeletas — el administrador registra permisos/licencias manualmente
- Planilla mensual completa con cálculos peruanos (AFP/ONP, IGV, gratificaciones, CTS, 5ta categoría)
- Boleta de pago en PDF — descarga local (no envío automático)
- Vacaciones — gestión desde el panel admin
- Exportes contables (Concar, Siscont, Excel Universal)
- AFPnet (TXT) y PLAME (CSV) para SUNAT
- Cierre mensual y comparativo histórico
- Soporte por email

**No incluye** (disponible en planes superiores):
- Portal del trabajador (sin self-service)
- Envío/notificación automática de boletas
- Solicitudes de horas extras desde el portal
- Reclutamiento + Pipeline IA, CV parser, predictor de rotación
- Capacitaciones / Evaluaciones 360 / Disciplinaria formal
- Organigrama visual / Calendario laboral / Contratos formales con renovación
- Roster matricial / Banco de horas
- Workflows de aprobación / Bandas salariales / Préstamos
- Comunicaciones masivas (campañas, WhatsApp)
- Pulse del Grupo, Briefing del Día, Cuadrícula Semanal (gastronomía)
- Dashboard Ejecutivo, BI Excel, Analytics
- PDFs avanzados (solo boleta y constancia legal)
- Multi-empresa (1 RUC en Starter)

### Cómo activar el Plan Starter para un cliente

**Desde Django admin (UI):**
1. Ir a `/admin/empresas/empresa/`
2. Editar la empresa del cliente
3. En la sección **Plan comercial**, seleccionar `STARTER`
4. Guardar — el cambio aplica inmediatamente (no requiere redeploy)

**Desde CLI (recomendado para bulk o automatización):**
```bash
docker exec harmoni-web python manage.py set_empresa_plan <RUC> STARTER

# Listar planes actuales de todas las empresas:
docker exec harmoni-web python manage.py set_empresa_plan --list
```

### Hard cap de trabajadores

Cada plan tiene un tope:
- Starter: 30 trabajadores activos
- Profesional: 100
- Business: 300
- Enterprise: sin tope

Si intentas dar de alta el worker #31 en una empresa Starter, el sistema bloquea
con un `ValidationError` que apunta a `/upgrade/`. Para superar el tope, hay que
cambiar el plan a uno superior.

### Página de upgrade

Cuando un user del Plan Starter intenta acceder a una feature bloqueada
(ej. `/reclutamiento/`), es redirigido automáticamente a `/upgrade/`, donde puede:
- Ver comparativa de los 4 planes
- Hacer clic en "Quiero este plan" → abre WhatsApp con mensaje pre-llenado
- O enviar email a ventas@harmoni.pe

### Demos comerciales con auto-login

Para presentar Harmoni a un prospecto sin que tenga que teclear credenciales:

| URL | Plan | Caso de uso |
|---|---|---|
| `https://demo.harmoni.pe/d/starter/` | Starter | Demo Pixel Motion (agencia 25 personas) |
| `https://demo.harmoni.pe/d/enterprise/` | Enterprise | Demo Grupo EDO (gastronomía, 24 RUCs) |

Estos links logean automáticamente al user demo correcto y redirigen al home.
Útiles para WhatsApp / email de ventas — un solo clic.

### API: consultar el plan vigente

```http
GET /api/v1/me/plan/
Authorization: Bearer <jwt>

Response 200:
{
    "plan": "STARTER",
    "plan_display": "Starter — S/ 149/mes (hasta 30 colaboradores)",
    "max_trabajadores": 30,
    "trabajadores_actuales": 25,
    "es_starter": true,
    "features_bloqueadas": ["reclutamiento", "portal", ...],
    "upgrade_url": "/upgrade/",
    "empresa": { "ruc": "20612345678", "razon_social": "..." }
}
```

Útil para integraciones que necesiten saber qué features están disponibles
antes de invocarlas.

---

## 21. Atajos de Teclado y Tips

### Atajos de teclado

| Atajo | Acción |
|-------|--------|
| `Ctrl + Shift + H` | Abrir/cerrar el chat de Harmoni AI |
| `Escape` | Cerrar modales y paneles emergentes |
| `Ctrl + F` | Buscar en la página (función del navegador) |

### Tips de productividad

**Dashboard:**
- Los chips de alerta en el Dashboard son clicables y llevan directamente al listado del problema. No los ignore.
- Agregue `Analytics > Dashboard IA` como su pestaña de inicio para tener siempre el pulso de la empresa.

**Personal:**
- Antes de registrar un nuevo empleado, busque por DNI para evitar duplicados.
- Use la importación masiva desde Excel si incorpora más de 5 empleados a la vez.

**Asistencia:**
- Importe las marcaciones del biométrico todos los lunes para tener el tareo al día.
- Revise los registros SS (sin salida) semanalmente — no espere al cierre del mes.

**Vacaciones:**
- El calendario de vacaciones es un aliado para la planificación. Úselo antes de aprobar nuevas solicitudes.
- Configure la alerta de vacaciones acumuladas en exceso para evitar contingencias laborales.

**AI Chat:**
- El chip "Dashboard" genera el dashboard ejecutivo más rápido que navegar por el menú.
- Use "exportar reporte ejecutivo en Excel" para tener un reporte listo para presentaciones en segundos.
- Pruebe el contexto conversacional: haga una pregunta, luego un follow-up, y vea cómo el asistente entiende la relación.

**General:**
- Todas las tablas del sistema son **ordenables** haciendo clic en el encabezado de columna.
- Los filtros activos se muestran como chips bajo la barra de búsqueda. Haga clic en la X para quitarlos.
- Los reportes exportados a Excel están listos para usar en PowerPoint o para enviar por correo.

---

## 22. Preguntas Frecuentes

### Acceso y usuarios

**¿Por qué no puedo ver ciertos módulos?**
Su perfil de usuario tiene permisos limitados. Solicite al Administrador del sistema que revise y amplíe sus permisos si necesita acceder a módulos adicionales.

**¿Puedo usar Harmoni desde mi celular?**
Sí. El sistema está optimizado para dispositivos móviles. Use el navegador de su teléfono (Chrome recomendado). El Portal del Empleado tiene una experiencia móvil especialmente optimizada.

**¿Qué hago si olvidé mi contraseña?**
Haga clic en "¿Olvidó su contraseña?" en la pantalla de inicio de sesión. Ingrese su correo registrado y recibirá un enlace de recuperación.

### Asistencia y tareo

**¿Qué es un registro "Sin Salida" (SS)?**
Es cuando el empleado marcó entrada pero no marcó salida al final del día. El sistema lo registra como día trabajado completo (sin descuento), pero no genera horas extras. Al final del mes, RRHH debe confirmar si efectivamente fue un día completo o una ausencia.

**¿Por qué aparecen más de 234 personas en la Vista Unificada?**
La Vista Unificada puede incluir empleados que estuvieron activos en algún momento del ciclo consultado, aunque ya no estén activos. También puede incluir personal histórico si el filtro de estado no está aplicado.

**¿Las HE del personal STAFF se pagan o se compensan?**
Para el personal STAFF, las horas extras se acumulan en el **Banco de Horas** y se compensan con tiempo libre adicional. Para el personal RCO, las HE se pagan directamente en el recibo de honorarios del mes.

### Vacaciones

**¿Cuántos días de vacaciones corresponden por ley?**
30 días calendarios por año de servicio, conforme al D.Leg. 713. El empleado tiene derecho a tomarlos luego de completar el año de servicios.

**¿Se pueden tomar vacaciones antes de completar el año?**
Sí, son las "vacaciones anticipadas" (vacaciones convencionales). Se acuerdan por escrito entre el empleado y el empleador. El empleado "debe" los días hasta que complete el año.

**¿Qué pasa si el empleado no tomó sus vacaciones?**
Las vacaciones no se pierden. El empleado tiene hasta un año adicional para disfrutarlas, y un año más para cobrar su compensación económica equivalente. Sin embargo, se generan contingencias laborales y posibles multas de SUNAFIL si los días se acumulan en exceso.

### Nóminas

**¿Cuándo se depositan las gratificaciones?**
En julio (para la gratificación de Fiestas Patrias) y diciembre (para la gratificación de Navidad). La fecha límite legal es el 15 de julio y el 15 de diciembre respectivamente.

**¿Cuándo se realiza el depósito de CTS?**
Dos veces al año: en mayo (período noviembre-abril) y noviembre (período mayo-octubre). El depósito debe realizarse como máximo el 15 de mayo y el 15 de noviembre.

**¿Por qué el IR 5ta categoría varía cada mes?**
Porque se calcula en base a la proyección anual de ingresos. Si hay variaciones mensuales (bonos, HE, cambios salariales), la retención del mes se ajusta para que al final del año la retención total sea exacta.

### Harmoni AI

**¿El Harmoni AI puede equivocarse?**
El asistente trabaja con datos directos de la base de datos del sistema, por lo que los datos cuantitativos son precisos. En interpretaciones o análisis complejos, es recomendable verificar con los módulos correspondientes.

**¿Mis conversaciones con el AI son privadas?**
Las consultas al AI se procesan a través del proveedor configurado (Gemini, DeepSeek, etc.). No se envían datos personales identificables de los empleados, solo datos agregados y estadísticos. Consulte la política de privacidad del proveedor con su administrador.

**¿Puedo usar el AI para editar datos del sistema?**
En las versiones actuales, el AI puede asistir en la generación de documentos y reportes, pero la modificación de datos en el sistema se realiza a través de los módulos correspondientes con los controles de aprobación habituales.

### Técnicas y soporte

**¿Cómo actualizo los parámetros legales cuando cambia la UIT o RMV?**
Ingrese a `Configuración > Parámetros Legales` y actualice los valores. El cambio aplica a todos los cálculos futuros. Los cálculos históricos no se modifican retroactivamente.

**¿Qué hago si el sistema está lento?**
Primero intente refrescar la página (F5). Si el problema persiste, verifique su conexión a internet. Si el problema es generalizado, contacte a su administrador del sistema.

**¿Cómo reporto un error en el sistema?**
Capture una pantalla del error (tecla Print Screen o herramienta de recorte), anote los pasos que realizó antes del error, y envíe esta información al equipo de soporte técnico de Harmoni.

---

## Glosario de términos

| Término | Definición |
|---------|-----------|
| **AFP** | Administradora de Fondos de Pensiones. Sistema privado de jubilación. |
| **CTS** | Compensación por Tiempo de Servicios. Beneficio social de depósito semestral. |
| **D.Leg. 713** | Decreto Legislativo de Descansos Remunerados. Base legal de vacaciones, feriados y descanso semanal. |
| **DS 003-97-TR** | Ley de Productividad y Competitividad Laboral. Base de contratos y faltas graves. |
| **eNPS** | Employee Net Promoter Score. Índice de recomendación de la empresa como lugar de trabajo. |
| **Gratificación** | Pago extraordinario equivalente a 1 sueldo mensual en julio y diciembre. |
| **HE** | Horas Extras. Trabajo realizado más allá de la jornada ordinaria. |
| **IR 5ta Categoría** | Impuesto a la Renta de quinta categoría. Tributo sobre ingresos laborales dependientes. |
| **LSG** | Licencia Sin Goce de haber. Permiso no remunerado. |
| **ONP** | Oficina de Normalización Previsional. Sistema público de jubilación (13% del sueldo). |
| **PDI** | Plan de Desarrollo Individual. Plan de acción para el crecimiento profesional del colaborador. |
| **RCO** | Recibo de Honorarios. Modalidad de contratación por prestación de servicios independientes. |
| **RMV** | Remuneración Mínima Vital. Sueldo mínimo legal (S/ 1,025). |
| **Roster** | Control de programación de viajes para personal foráneo (mina, campamento). |
| **STAFF** | Personal en planilla (relación laboral dependiente). |
| **SS** | Sin Salida. Día en que el empleado marcó entrada pero no registró salida. |
| **SUNAFIL** | Superintendencia Nacional de Fiscalización Laboral. Entidad que fiscaliza el cumplimiento laboral. |
| **UIT** | Unidad Impositiva Tributaria. Valor de referencia para cálculos tributarios. |
| **VistaNomina** | Vista consolidada de la planilla con todos los conceptos remunerativos y no remunerativos. |

---

## Información de contacto y soporte

Para soporte técnico, capacitación adicional o consultas sobre el sistema, contacte al equipo de soporte de Harmoni a través del canal interno designado por su empresa.

---

*Manual de Usuario — Harmoni ERP v1.0*
*Fecha de publicación: Marzo 2026*
*Este documento describe las funcionalidades del sistema a la fecha de publicación. Las funcionalidades pueden actualizarse en versiones posteriores.*
