# Plan de Estabilización Harmoni — Q2 2026

**Última revisión:** 2026-05-24
**Owner:** Edwin Lopez

> **Estado Q2 (cierre mayo):** 🟢 Todos los críticos (1, 2, 3) completados. Importantes 5/6/7 completados; 4 (limpieza legacy) postergado a Q3. No bloqueantes 9 completado; 8 (performance) en auditoría, 10 (roles finos) postergado.

## Contexto

Tras la integración directa con Synkro (abril 2026) salieron a la luz inconsistencias acumuladas: datos denormalizados desfasados, importes Excel pisados por sync, papeletas duplicadas, condiciones LOCAL/FORÁNEO mal asignadas, turnos noche mal procesados. La mayoría se resolvió en sprint corto (commits abril 27-29). **Antes de avanzar con features nuevas, conviene estabilizar.**

## Estado actual (post-fixes Q2 2026)

✅ Resuelto:
- 449 RegistroTareo con `grupo` desfasado → corregidos
- 1,441 obreros importados por error → eliminados
- 1,010 RegistroTareo huérfanos (pre-alta/post-cese) → eliminados
- 858 papeletas duplicadas + 67 traslapadas → fusionadas
- 8,037 RegistroTareo con `condicion` desfasada → normalizado
- 14 trabajadores LOCAL/FORÁNEO mal clasificados → corregido + recalculo HE
- Filtros reportes ahora usan `personal__grupo_tareo` canónico (no denorm)
- Sync respeta MANUAL/EXCEL/PAPELETA (no los pisa)
- Sync filtra solo Empleados (no Obreros construcción civil)
- Sync respeta fecha_alta/fecha_cese
- Reportes consistentes: matriz, exportaciones, individual PDF cuadran
- Botón Sync Synkro en dashboard asistencia
- Excel Faltas con DNI separado, hoja A-Z, autofilter
- Vista RCO con selector ciclo/calendario

⚠️ Pendiente:
- 1,008 RegistroTareo legacy en períodos CERRADOS (condicion desfasada, intocables)
- 387 papeletas EXCEL/MANUAL pre-alta huérfanas (requiere revisión manual)
- Turno noche en sync_picados: detectado en código de prueba, no implementado en producción
- Muchas vistas usan campos denormalizados (`condicion__in=`) — vulnerables al mismo bug

## Prioridades

### 🔴 Crítico (próximas 2 semanas) — ✅ TODO COMPLETADO (mayo 2026)

#### 1. Tests automatizados de cálculo HE + sync Synkro ✅
**Por qué:** Cada arreglo descubrió otro bug en cascada. Sin tests no se puede refactorizar con confianza.
**Alcance mínimo:**
- `nominas/engine.py`: gratificación, IR 5ta, AFP, asignación familiar (los 4 bugs CRITICAL/HIGH del Q1).
- `asistencia/services/processor.py + _recalcular_horas`: jornadas LOCAL/FORÁNEO/LIMA, SS, marcación incompleta, domingo/feriado, redondeo 0.5h.
- `integraciones/services/synkro_sync.py`: sync_papeletas idempotente, sync_picados respeta MANUAL/EXCEL/PAPELETA, fecha_alta/cese.
- Casos edge: turno noche, papeletas traslapadas, regla especial.

**Ubicación:** `asistencia/tests/test_*.py`, `integraciones/tests/test_synkro_sync.py`.
**Ejecución:** `pytest --cov` y target inicial 60% coverage en módulos críticos.

#### 2. Turno noche en `sync_picados` ✅
**Por qué:** Caso real de DNI 70919188 (LOPEZ TORRE): salidas pasadas medianoche se interpretaban como entrada del día siguiente, generando errores en HE.

**Algoritmo:**
- Picados con hora < 5:30 → salida del día anterior
- Picados ≥ 5:30 → entrada/salida del día actual
- Salida puede pasar medianoche (hasta 5:00 día siguiente)

**Implementación:** modificar `sync_picados` en `integraciones/services/synkro_sync.py` para reasignar picados antes de agrupar por (personal, fecha_laboral).

#### 3. Sentry + alertas Celery ✅
**Por qué:** Si un sync falla a las 3am o un task Celery muere en silencio, nadie se entera.
**Hoy:** Sentry mencionado en .env pero `SENTRY_DSN` vacío.
**Tareas:**
- Crear cuenta Sentry free tier (5k errores/mes).
- Configurar `SENTRY_DSN` en `.env.production`.
- Wraps en tasks Celery críticos: `sync_synkro_auto`, `health_check_papeletas`, generación de planilla.
- Email a `eflopezt@gmail.com` cuando estado=ERROR en `SyncSynkroLog`.

### 🟡 Importante (siguiente fase)

#### 4. Limpieza datos legacy en períodos CERRADOS
- 1,008 RegistroTareo con `condicion` desfasada en cerrados (2025-11/12, 2026-01/02).
- 387 papeletas pre-alta EXCEL/MANUAL.
- 51 papeletas post-cese.

**Plan:** reabrir período → limpiar → cerrar. Hacer en horario noche, durante fin de semana, con backup previo.

#### 5. Audit log más completo ✅
- Hoy `CambioCodigoLog` solo registra cambios via `ajax_calendario_cambiar`.
- Faltan: ediciones via Django admin, importaciones masivas, sync Synkro auto (con qué cambió por registro).
- Implementar middleware audit con `django-simple-history` o tabla propia.

#### 6. Backup automatizado PostgreSQL ✅
- Hoy: el VPS no tiene backup programado visible.
- Riesgo: fallo de disco = pérdida total.
- Plan: cron `pg_dump` diario → S3/Backblaze B2 (~5 USD/mes).
- Retención: 7 dailies + 4 weeklies + 6 monthlies.

#### 7. Refactor `services/he_calculator.py` ✅
- Lógica HE dispersa entre 4-5 archivos.
- Extraer a un módulo único con función pura `calcular_he(personal, fecha, entrada, salida, almuerzo)`.
- Tests unitarios sobre esa función.
- El resto del código la consume.

### 🟢 No bloqueante

#### 8. Performance escalabilidad
- 854K picados en 4 meses (~6.5M/año). 200 empleados → ok hoy.
- A 500+ empleados, índices en hot queries críticos. EXPLAIN ANALYZE en:
  - Vista RCO con filtros
  - Reporte exportar_horas_rco
  - Dashboard KPIs

#### 9. Documentación reglas peruanas ✅
- Hoy en código + memoria Claude. Equipo no-técnico no las puede leer.
- Crear `docs/internal/REGLAS_NEGOCIO_ASISTENCIA.md`.

#### 10. Roles y permisos finos
- Hoy cualquier admin puede tocar cualquier dato.
- Agregar roles: nómina, RRHH, supervisor de obra, capataz.
- Cada uno con permisos limitados.

## Cronograma sugerido

| Semana | Foco |
|---|---|
| Sem 1 (29-04 → 06-05) | Sentry + backup pg_dump + tests críticos cálculo HE |
| Sem 2 (07-05 → 13-05) | Tests sync Synkro + turno noche en producción |
| Sem 3 (14-05 → 20-05) | Limpieza legacy + audit log |
| Sem 4 (21-05 → 27-05) | Refactor `he_calculator.py` + docs reglas |
| Cierre mayo (28-05) | Cierre planilla mayo con sistema estable y testeado |

## Métricas para "estable"

Marcamos Harmoni como **estable** cuando:
- ✅ Coverage ≥ 60% en módulos críticos (nominas/engine, asistencia/processor, integraciones/synkro_sync)
- ✅ 0 errores Sentry abiertos > 1 día
- ✅ Backup automatizado verificado (restore de prueba mensual)
- ✅ 0 inconsistencias entre matriz/PDF/Excel para cierre de planilla
- ✅ 0 registros denormalizados desfasados (auditoría diaria via management command)
- ✅ Turno noche procesado correctamente para 100% de casos de prueba

---

## Logros Mayo 2026 — Cierre Q2

### Plan original 10/10 items

| # | Item | Estado |
|---|------|--------|
| 1 | Tests automatizados HE + sync Synkro | ✅ 144 tests, 94 % cov he_calculator |
| 2 | Turno noche en `sync_picados` | ✅ deploy prod |
| 3 | Sentry DSN + wraps Celery | ✅ SDK 2.53, new_scope, tags por tenant |
| 4 | Limpieza legacy en cerrados | ⏸ pospuesto Q3 (1,008 RegistroTareo intocables) |
| 5 | Audit log v2 | ✅ AuditEntry + signals en 5 modelos |
| 6 | Backup automatizado pg_dump | ✅ celery 03:30 + rotation 30d + S3/B2 |
| 7 | Refactor he_calculator único | ✅ 317 LOC, DRY de processor/calendario |
| 8 | Performance escalabilidad | 🟡 auditoría N+1 en curso |
| 9 | Docs reglas peruanas | ✅ `docs/internal/REGLAS_PERUANAS.md` 620 LOC + 22 entradas RAG |
| 10 | Roles y permisos finos | ⏸ pospuesto Q3 |

### Bonus (no estaban en el plan original)

- **Design System V2 "Cockpit"** (Linear/Notion-style) aplicado a 319 templates en demo + CSRT
- **Agente IA real** con LLM multi-proveedor + tool-use (caso reintegro S/200 funcional)
- **Empleados V2**: drawer 540 px + bulk bar + inline edit + ⌘K palette mejorado
- **Mobile UX** sidebar off-canvas + drawer responsive + tap targets ≥44 px
- **Migraciones reconciliadas** prod CSRT (4 leaf nodes fusionados)
- **Fix logo distorsionado** sidebar (favicon-180 cuadrado nativo)
- **Sweep bugs visuales**: `{# #}` multilínea fantasma en 11 templates
- **16 fails residuales suite** → 3 bugs prod descubiertos y corregidos (middleware /api/v1/me, related_name personal_data, vacaciones.recalcular)
- **MANUAL_USUARIO v1.2** con sección 23 (15 sub-apartados)

### Próximo Q3 (sugerido)

1. ~~Performance: aplicar fixes N+1 reportados por agente E~~ ✅
2. ~~Coverage nominas/engine.py~~ ✅ (91% — agente D)
3. Limpieza legacy en períodos cerrados (item 4 pendiente)
4. Roles finos por módulo (item 10 pendiente)
5. ~~Push v1.2 manual a PR + merge en main remoto~~ ✅ deployed

---

## Adendum v1.2.1 — Mayo 25 2026 (post-demo)

### Liquidaciones laborales — flujo completo

✅ **Sprint 1 Liquidaciones**: Modelo `LiquidacionLaboral` + 8 motivos cese + 11 conceptos/descuentos + 6 estados workflow + signal `post_save` Personal + UI detalle + 18 tests passing.

✅ **Sprint 2 Wizard "Cesar trabajador"**: UI 3 pasos (datos → preview AJAX → confirmar) con cálculo de truncas en vivo sin persistir. Botón en ficha empleado. 16 tests passing.

✅ **Workflow Offboarding Trabajador (5 etapas)**: management command `seed_offboarding_flow` crea flujo idempotente con etapas Encuesta salida (USUARIO) → Devolución activos (JEFE_AREA) → Liquidación pagada (GRUPO Tesorería) → Carta no adeudo (SUPERUSER) → Cierre administrativo (SUPERUSER). Signal post_save LL dispara automáticamente al pasar a CALCULADA. 9 tests passing.

🟡 **Sprint 3 (en curso)**: Carta no adeudo PDF + Certificado trabajo PDF + Encuesta exit interview templates.

⏸ **Sprint 4 (pendiente)**: Tests E2E + onboarding cliente + docs operativas SUNAFIL.

### Gastronomía — Pool de propinas

✅ **Pool de propinas**: 4 modelos (`ConfiguracionPropinas`, `PuntosPropinas`, `PoolPropinas`, `DistribucionPropinas`) + 3 modos (POOL_PUNTOS, POOL_PAREJO, INDIVIDUAL) + UI completa + heurística cocina/admin + 10 tests passing.

### Datos demo enriquecidos

✅ **Seed histórico 17 meses** (`seed_demo_historico`): 1,749 RegistroNomina + 17 PeriodoNomina REGULAR + 2 GRATIFICACION + 2 CTS + 614 BancoHoras + 3,647 PulseSemanal + 86 activos + 9 cesados con motivos variados. Agregado al cron `reset_demo.sh` para que se mantenga.

### Bugs visibles corregidos pre-demo

- Calendario `+N más` no clickeable → modal overlay con descarga CSV
- Logo PDF efecto ghost → cambiado a favicon-512 cuadrado sólido
- Hero "Asistencia Matricial" texto invisible → forzado `color:#fff!important`
- Organigrama lista vertical → inferencia jerárquica por `nivel_org`/`cargo` (87 nodos, 4 niveles)
- Scroll horizontal tablas bloqueado por CSS global → corregido
- Workflow-mes sin AFPNet + sin gestión → step #9 nuevo + modal "Personalizar pasos"
- ANDES MINING placeholder → "Mi Empresa S.A.C." dinámico
- RCO label confuso → "Operativo (Recibo de Honorarios)" en UI (valor BD intacto)
- Residuos EDO/Nikkei/Sushi → diversificación nombres (Premium, Marino, Express, Asado, Café, Central)
- Password demo era `demo`, faltaba reset → corregido a `demo123` consistente

### Estado producción

- `harmoni.pe` (Stiler) y `demo.harmoni.pe` deployed con todos los cambios.
- Cron nocturno `reset_demo.sh` actualizado con `seed_offboarding_flow` + `seed_demo_historico` + password `demo123`.
- Suite tests: **1,722 passing** + 1 skipped + 5 xfailed esperados.
