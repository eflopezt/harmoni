# Manual de Usuario Integral Harmoni

Este manual explica Harmoni desde el primer proceso hasta el último. Está pensado para implementación, capacitación y demostraciones con clientes en Perú.

## Principios de Uso

1. El dato se corrige en origen. Si una falta está mal, se corrige en Asistencia; si un contrato no cubre el período, se corrige en Contratos; si falta RUC o representante, se corrige en Calidad de datos.
2. Cada proceso debe dejar listo al siguiente. No se avanza con pendientes críticos si afectan contrato, asistencia, planilla, boleta, SUNAT o bancos.
3. No se trabaja en Excel paralelo. Excel queda para exportar, revisar o entregar, no como fuente principal.
4. La empresa activa define el alcance. En grupos multi-RUC, cada planilla se calcula por empresa, aunque Dirección pueda ver indicadores consolidados.
5. Toda acción importante debe quedar con responsable, fecha y evidencia.

## Ruta Oficial de Inicio a Fin

El usuario debe iniciar en Preparar, no en Contratos ni en Nómina. Contratos es parte de Incorporar; Nómina depende de todo lo anterior. La ruta oficial es:

Preparar -> Atraer -> Incorporar -> Operar -> Pagar -> Desarrollar -> Comunicar -> Dirigir -> Desvincular.

Cuando una empresa no usa reclutamiento, puede saltar Atraer, pero nunca debe saltar Preparar ni Operar antes de Pagar. Preparar define el dato maestro; Operar define las novedades del mes; Pagar solo debe consolidar y cerrar.

## Roles Habituales

| Rol | Qué hace |
|---|---|
| Administrador | Configura empresa, usuarios, accesos y reglas generales. |
| RR. HH. | Gestiona fichas, contratos, legajos, vacaciones, documentos y ceses. |
| Reclutamiento | Administra vacantes, candidatos, entrevistas y contratación. |
| Jefe de área | Revisa asistencia, aprueba solicitudes y valida novedades. |
| Nóminas | Valida pre-planilla, calcula, aprueba, emite boletas y exporta. |
| Dirección | Revisa indicadores, alertas, costos y riesgos. |
| Trabajador | Usa el portal para boletas, solicitudes, documentos y confirmaciones. |

## 01. Preparar

Objetivo: dejar lista la base de operación antes de contratar o calcular.

Dónde entrar: Calidad de datos, Empresas, Áreas, Usuarios, Accesos.

Pasos:

1. Seleccionar la empresa o RUC correcto.
2. Completar razón social, RUC, domicilio fiscal, ubigeo, representante legal, documento del representante, actividad económica, teléfono y correo de RR. HH.
3. Crear áreas, subáreas, cargos, sedes y centros de costo.
4. Crear usuarios administrativos y vincularlos con trabajadores cuando corresponda.
5. Asignar perfiles de acceso por rol.
6. Revisar Calidad de datos hasta que no existan bloqueos críticos.

Listo cuando:

- La empresa tiene datos legales suficientes para contratos, boletas y archivos SUNAT.
- Las personas activas tienen empresa, fecha de alta, sueldo base, cargo y régimen pensionario.
- Cada responsable tiene permisos y no existe acceso innecesario.

Errores comunes:

- Trabajar en vista consolidada y luego intentar cerrar una planilla como si fuera un solo RUC.
- Crear trabajadores sin empresa.
- Dar permisos amplios “por rapidez” y perder trazabilidad.

## 02. Atraer

Objetivo: cubrir una necesidad de personal sin perder origen ni evidencia.

Dónde entrar: Vacantes, Pipeline, CV express, Banco de talento, Entrevistas.

Pasos:

1. Crear una requisición o vacante con área, puesto, motivo, prioridad y responsable.
2. Solicitar aprobación si la empresa usa control previo.
3. Publicar la vacante o cargar candidatos.
4. Registrar CV, fuente, pretensión salarial, notas y entrevistas.
5. Mover candidatos por etapas del pipeline.
6. Seleccionar candidato y contratar desde la postulación.

Listo cuando:

- El candidato ganador tiene decisión registrada.
- La oferta tiene puesto, sueldo, fecha de ingreso y empresa.
- El alta se puede iniciar sin volver a escribir los datos principales.

Flujo alterno:

- Si la empresa no usa reclutamiento, puede ir directo a Incorporar con Alta express.

## 03. Incorporar

Objetivo: crear una ficha única que alimente todo el ciclo laboral.

Dónde entrar: Control Tower, Alta express, Empleados, Contratos, Legajo, Onboarding, Firma.

Pasos:

1. Crear el trabajador desde el candidato contratado o Alta express.
2. Completar DNI, nombres, dirección, teléfono, correo, fecha de alta, empresa, área, cargo, sueldo y sistema pensionario.
3. Generar el contrato desde la ficha.
4. Revisar fecha de inicio y fecha de fin. En renovación, la nueva fecha de inicio debe continuar desde el último contrato vigente o vencido del trabajador.
5. Adjuntar o generar el PDF contractual.
6. Enviar a firma si aplica.
7. Crear onboarding con responsables y fechas límite.
8. Crear acceso al portal del trabajador.
9. Exportar alta T-Registro cuando el alta esté lista.

Listo cuando:

- La ficha del trabajador no está duplicada.
- El contrato cubre el período laboral correcto.
- El legajo tiene documentos obligatorios.
- Onboarding no tiene tareas vencidas críticas.
- El trabajador puede aparecer en turnos, asistencia y planilla.

Regla de renovación:

- Renovar con continuidad debe tomar el último contrato del trabajador.
- Si el último contrato termina el 31/03/2026, el nuevo contrato debe iniciar el 01/04/2026.
- El usuario define el nuevo vencimiento o una duración común; Harmoni calcula el inicio por trabajador.
- La renovación masiva debe mostrar progreso, resultado y errores por trabajador.

## 04. Operar

Objetivo: resolver el día a día antes de que llegue a nómina.

Dónde entrar: Roster, Asistencia, Papeletas, Vacaciones, Préstamos, Viáticos, Aprobaciones.

Pasos:

1. Programar turnos y roster antes del período de trabajo.
2. Importar marcas biométricas o registrar asistencia.
3. Resolver no marcajes, tardanzas, faltas, permisos y descansos.
4. Registrar vacaciones y aprobarlas por la bandeja correspondiente.
5. Registrar préstamos, adelantos, viáticos o descuentos internos.
6. Revisar la bandeja de aprobaciones.
7. Exportar o validar la información que pasará a pre-planilla.

Listo cuando:

- No hay faltas o no marcajes sin decisión si afectan pago.
- Las vacaciones aprobadas actualizan saldos.
- Las horas extra aprobadas están en el período correcto.
- Los préstamos y descuentos tienen cronograma y estado correcto.

Errores comunes:

- Ajustar horas directamente en nómina en vez de corregir asistencia.
- Duplicar descuentos manuales que ya vienen de préstamos o conceptos.
- Aprobar vacaciones después de calcular planilla sin recalcular.

## 05. Pagar

Objetivo: cerrar el mes con una sola fuente de cálculo.

Dónde entrar: Workflow mes, Pre-planilla, Períodos, Revisión, Boletas, Integraciones.

### Secuencia Oficial de Planilla

1. Entrar a Workflow mes.
2. Revisar Pre-planilla del mes.
3. Corregir bloqueos de datos, contratos, asistencia y conceptos.
4. Crear período si no existe.
5. Generar planilla.
6. Revisar variaciones, netos, descuentos, costo empresa y trabajadores incluidos.
7. Aprobar planilla.
8. Emitir boletas.
9. Exportar banco, PLAME, AFP Net, EsSalud, CTS o contabilidad según corresponda.
10. Cerrar período.

### Pre-planilla

Qué revisa:

- Trabajadores incluidos en el período.
- Contratos que cubren el mes.
- Contratos que terminan en el período.
- Incidencias de asistencia.
- Préstamos, descuentos y conceptos variables.
- Datos obligatorios para boletas y archivos externos.

Cómo avanzar:

- Si un bloqueo tiene botón, entrar por ese botón, corregir en origen y volver a Pre-planilla.
- Si no hay bloqueos críticos, continuar a Período.

### Período

Estados habituales:

| Estado | Significado | Acción natural |
|---|---|---|
| Borrador | El período existe pero no tiene cálculo final. | Generar planilla. |
| Calculado | Ya existen registros de nómina. | Revisar y aprobar. |
| Aprobado | Nómina validada por responsable. | Emitir, exportar y cerrar. |
| Cerrado | Mes congelado con evidencia. | Consultar, descargar o auditar. |
| Cerrado sin boletas | Estado anómalo recuperable. | Regularizar cierre y recalcular. |

### Cierre Correcto

1. Generar planilla.
2. Revisar totales y casos atípicos.
3. Aprobar.
4. Emitir boletas.
5. Exportar archivos externos.
6. Cerrar.

Listo cuando:

- Todos los trabajadores que pertenecen al período están incluidos.
- Los cesados dentro del período no desaparecen antes de pagarles lo trabajado.
- Contratos y nómina usan el mismo criterio de cobertura del mes.
- Boletas, banco, PLAME y contabilidad salen del mismo período aprobado.
- El estado final es Cerrado.

## 06. Desarrollar

Objetivo: convertir desempeño y clima en acciones.

Dónde entrar: Evaluaciones, OKR, PDI, Capacitaciones, Encuestas, Disciplina, Equidad salarial.

Pasos:

1. Crear ciclo de evaluación o encuesta.
2. Asignar participantes, evaluadores y fechas.
3. Recibir respuestas o puntajes.
4. Revisar resultados por trabajador, área o empresa.
5. Generar planes de desarrollo, capacitación o acción disciplinaria si corresponde.
6. Comunicar compromisos y hacer seguimiento.

Listo cuando:

- Cada brecha crítica tiene responsable y acción.
- Las capacitaciones se asignan por necesidad real.
- El resultado no queda solo como reporte.

## 07. Comunicar

Objetivo: cerrar pendientes con mensajes trazables.

Dónde entrar: Notificaciones, Comunicados, Campañas, WhatsApp, Documentos laborales.

Pasos:

1. Elegir audiencia: todos, empresa, área, grupo o trabajadores específicos.
2. Crear comunicado, recordatorio, campaña o documento laboral.
3. Revisar texto, destinatarios y fecha.
4. Enviar o publicar.
5. Revisar lectura, acuse o pendientes.
6. Reenviar solo a quienes siguen pendientes.

Listo cuando:

- El mensaje tiene destinatarios claros.
- La lectura o acuse queda registrada.
- El documento vuelve al legajo si es laboral.

## 08. Dirigir

Objetivo: tomar decisiones con datos vivos y volver al módulo correcto.

Dónde entrar: Analytics, Alertas, Dashboard ejecutivo, Reportes, Auditoría, SUNAFIL.

Pasos:

1. Revisar indicadores de headcount, rotación, asistencia, costo laboral y pendientes.
2. Abrir alertas críticas.
3. Entrar al módulo origen desde la alerta.
4. Asignar o ejecutar la acción.
5. Revisar auditoría y reportes si se necesita sustento.

Listo cuando:

- Cada alerta crítica tiene acción o sustento.
- Los reportes salen del sistema, no de archivos paralelos.
- Dirección puede explicar el costo laboral y el estado de RR. HH. por empresa.

## 09. Desvincular

Objetivo: cerrar la relación laboral con evidencia completa.

Dónde entrar: Cese, Offboarding, Liquidaciones, Baja T-Registro, Documentos de salida.

Pasos:

1. Registrar fecha y motivo de cese.
2. Iniciar offboarding.
3. Asignar responsables para devolución de activos, accesos y documentos.
4. Calcular liquidación.
5. Revisar CTS, vacaciones, gratificación trunca, descuentos y pagos pendientes.
6. Aprobar liquidación.
7. Emitir documentos de salida.
8. Exportar baja T-Registro.
9. Cerrar historia laboral.

Listo cuando:

- No quedan activos ni accesos abiertos.
- La liquidación está aprobada y sustentada.
- La baja SUNAT está preparada.
- El trabajador queda cesado sin romper reportes históricos.

## Procesos Auxiliares

| Proceso auxiliar | Para qué sirve | Con qué se enlaza |
|---|---|---|
| Buscador global | Encontrar empleados, documentos, papeletas o acciones. | Todos los módulos. |
| Calidad de datos | Detectar campos incompletos o inconsistentes. | Preparación, ingreso y nómina. |
| Aprobaciones | Centralizar decisiones de jefes y RR. HH. | Vacaciones, asistencia, cambios y operación. |
| Legajo digital | Guardar evidencia por trabajador. | Contratos, boletas, documentos y SUNAFIL. |
| Firma | Formalizar contratos, anexos y documentos. | Incorporación, comunicación y salida. |
| Portal trabajador | Autoservicio del colaborador. | Boletas, solicitudes, documentos y confirmaciones. |
| Integraciones | Generar archivos para terceros. | SUNAT, bancos, AFP, EsSalud y contabilidad. |
| Auditoría | Ver quién cambió qué y cuándo. | Dirección, cumplimiento y soporte. |

## Checklist Diario

1. Revisar Inicio o Centro de Comando.
2. Atender alertas críticas.
3. Resolver aprobaciones pendientes.
4. Revisar contratos próximos a vencer.
5. Revisar asistencia del día anterior.
6. Confirmar si hay nuevos ingresos o ceses.

## Checklist Semanal

1. Revisar roster de la semana siguiente.
2. Validar vacaciones próximas.
3. Revisar onboarding y offboarding vencidos.
4. Revisar préstamos, viáticos y conceptos variables pendientes.
5. Revisar indicadores de clima, rotación o asistencia.

## Checklist Mensual de Nómina

1. Pre-planilla sin bloqueos críticos.
2. Contratos cubren el período.
3. Asistencia conciliada.
4. Vacaciones y permisos aprobados.
5. Préstamos y descuentos revisados.
6. Planilla generada.
7. Variaciones revisadas.
8. Planilla aprobada.
9. Boletas emitidas.
10. Banco, PLAME, AFP Net y contabilidad exportados.
11. Período cerrado.

## Criterios de Calidad para Demo o Cliente

Un recorrido está listo para presentación cuando:

- Se puede explicar el flujo de inicio a fin en menos de cinco minutos.
- Cada etapa tiene botón o enlace al siguiente paso.
- Un usuario nuevo sabe dónde está por el título, la etapa del flujo y la acción principal.
- Los procesos masivos muestran avance, resultado y errores.
- No hay mensajes contradictorios entre módulos.
- La planilla no permite avanzar con bloqueos críticos reales, pero sí permite regularizar estados anómalos con trazabilidad.

## Cómo Presentarlo

1. Empezar en Preparar mostrando empresa, calidad de datos y permisos.
2. Pasar a Atraer y convertir un candidato en alta.
3. Mostrar Incorporar con contrato, legajo y onboarding.
4. Mostrar Operar con asistencia, vacaciones y aprobaciones.
5. Cerrar Pagar con pre-planilla, cálculo, boletas e integraciones.
6. Mostrar Desarrollar y Comunicar como capas continuas.
7. Cerrar con Dirigir y Desvincular para demostrar control completo.

El mensaje principal para el cliente es: Harmoni reduce reprocesos porque cada dato nace en un lugar, se valida ahí y viaja al resto del sistema.
