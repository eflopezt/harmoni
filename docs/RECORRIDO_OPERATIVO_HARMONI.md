# Recorrido operativo de Harmoni

Este documento define el camino recomendado para operar una empresa en Harmoni. La regla es simple: cada etapa debe terminar con evidencia suficiente para que la siguiente no tenga que corregir datos anteriores.

## Roles

| Rol | Responsabilidad principal |
|---|---|
| Administrador de empresa | Configuración del RUC, accesos y responsables |
| RR. HH. | Legajos, contratos, movimientos, vacaciones y salidas |
| Reclutamiento | Requisiciones, candidatos, entrevistas y contratación |
| Jefe de área | Horarios, asistencia y decisiones asignadas |
| Nóminas | Validación, cálculo, aprobación, pago y contabilización |
| Trabajador | Solicitudes, documentos, boletas y confirmaciones desde su portal |

## 1. Preparar

1. Seleccionar el RUC correcto en el selector de empresa.
2. Completar RUC, razón social, dirección fiscal y representante legal.
3. Configurar áreas, cargos, centros de costo, horarios y responsables.
4. Crear o importar trabajadores con fecha de alta, sueldo base y sistema pensionario.
5. Vincular usuarios y perfiles de acceso con el mínimo permiso necesario.
6. Ejecutar el validador de planilla antes del primer período.

**Listo cuando:** no hay datos legales críticos, cada trabajador activo pertenece a una empresa y los legajos tienen fecha de alta y sueldo base.

## 2. Atraer

1. Crear la requisición en borrador con motivo, prioridad y responsable.
2. Enviar a aprobación y registrar la decisión.
3. Publicar la vacante aprobada.
4. Registrar postulantes, CV, fuente y consentimiento.
5. Mover candidatos por etapas con notas y evidencia de entrevista.
6. Contratar desde la postulación ganadora para conservar la trazabilidad.

**Listo cuando:** la persona contratada tiene una postulación cerrada, responsable identificable y fecha de ingreso acordada.

## 3. Incorporar

1. Crear el proceso de onboarding desde la contratación.
2. Asignar responsable y fecha límite a cada tarea.
3. Recabar contrato, documentos, examen, accesos, equipo e inducción.
4. Crear el acceso al portal del trabajador.
5. Completar u omitir cada paso dejando comentario y usuario responsable.

**Listo cuando:** el checklist no tiene tareas vencidas y los accesos, activos y documentos obligatorios tienen evidencia.

## 4. Operar

1. Mantener roster y horarios antes del inicio de la semana.
2. Importar o sincronizar marcaciones.
3. Resolver faltas, tardanzas, permisos, papeletas y horas extra.
4. Atender la bandeja unificada de aprobaciones por prioridad.
5. Revisar contratos que vencen en los siguientes 30 días.
6. Publicar briefings cuando el rubro use operación por turnos.

**Listo cada día:** no hay incidencias vencidas sin responsable y toda excepción que afectará planilla está aprobada o rechazada.

## 5. Pagar

1. Ejecutar el validador de onboarding de nómina.
2. Abrir el período regular de la empresa seleccionada.
3. Consolidar asistencia, ingresos, descuentos, préstamos y vacaciones.
4. Revisar anomalías y variaciones frente al período anterior.
5. Calcular, aprobar y cerrar con usuarios distintos cuando sea posible.
6. Emitir boletas, registrar acuses, exportar banco/SUNAT y contabilizar.

**Listo cada mes:** el período está cerrado, el total pagado tiene evidencia y los archivos externos corresponden al mismo RUC y período.

## 6. Desvincular

1. Registrar el cese con fecha y motivo canónico.
2. Iniciar el offboarding y asignar responsables.
3. Recuperar activos y revocar accesos.
4. Calcular, revisar, aprobar, firmar y pagar la liquidación.
5. Emitir certificado y documentos de salida.
6. Cerrar el proceso solo con todos los pasos resueltos u omitidos con sustento.

**Listo cuando:** no quedan activos ni accesos abiertos, la liquidación está cerrada y la trazabilidad del cese puede reconstruirse.

## Control diario

El Centro de Comando (`/comando/`) ordena los bloqueos por severidad y enlaza la pantalla donde se resuelven. No calcula puntajes de salud. Muestra conteos y estados derivados de registros reales.

La misma revisión puede ejecutarse desde operaciones:

```bash
python manage.py audit_processes
python manage.py audit_processes --empresa 3 --json
python manage.py audit_processes --fail-on-critical
```

## Reglas de datos

- La empresa de la sesión nunca concede autorización; solo reduce el alcance permitido.
- El modo consolidado es exclusivo del superusuario de plataforma.
- Ningún indicador ejecutivo debe derivarse de fórmulas simuladas.
- Un dato sin empresa se considera deuda de calidad y no debe aparecer en una vista de cliente.
- Una aprobación debe conservar solicitante, decisor, fecha, estado y comentario.
- Un período cerrado no se corrige en silencio: se revierte o ajusta con trazabilidad.
