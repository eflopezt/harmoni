# Reporte de Testing — demo.harmoni.pe

**Fecha:** 2026-04-30
**Tester:** Claude (automatizado vía Claude in Chrome)
**Instancia:** demo.harmoni.pe (usuario `demo` / `demo`)

## Resumen ejecutivo

| Categoría | Count |
|---|---|
| ✅ Módulos accesibles GET | 12 |
| ✅ Funcionalidades core OK | login, vacante POST, listados, exports |
| 🐛 Bugs críticos | 1 (ya arreglado) |
| 🟡 Bugs menores | 3 |
| 🔵 Mejoras de UX/seed | 6 |

## ✅ Lo que funciona bien

| Módulo | URL | Estado |
|---|---|---|
| Login app + admin | `/login/`, `/admin/login/` | OK ambos |
| Dashboard inicio | `/` | OK con KPIs |
| Asistencia dashboard | `/asistencia/` | 20 personas, 515h HE, 44 faltas |
| Asistencia matriz | `/asistencia/calendario/` | 20 empleados, datos abril completos, tasa asistencia 87.7% |
| Asistencia papeletas | `/asistencia/papeletas/` | 23 vacaciones, columnas DNI/Trabajador OK |
| Asistencia KPIs | `/asistencia/kpis/` | OK |
| Asistencia exports | `/asistencia/exportar/` | OK |
| Vacaciones | `/vacaciones/` | UI OK (sin data) |
| Nóminas | `/nominas/` | UI OK (sin períodos) |
| Préstamos | `/prestamos/` | UI OK (sin data) |
| Documentos | `/documentos/` | OK |
| Personal | `/personal/` | 20 empleados listados |
| Personal detalle | `/personal/<id>/` | OK |
| Reclutamiento listado | `/reclutamiento/` | OK |
| Reclutamiento crear vacante | POST `/reclutamiento/nueva/` | **OK** (creó "Asistente Marketing" id=1) |
| Onboarding | `/onboarding/` | OK |
| Banner MODO DEMO | top de toda página | Visible, gradiente naranja-rojo |
| Reset diario 03:00 am | cron VPS | Activo |

## 🐛 Bugs encontrados

### 1. ✅ ARREGLADO — `NameError: name 'settings' is not defined` en `synkro_sync_status`
- **Síntoma:** 500 Internal Server Error en `/integraciones/synkro/sync-status/` (endpoint que polea cada minuto el botón Sync Synkro del dashboard).
- **Causa:** falta `from django.conf import settings` en la función.
- **Fix:** commit `9e655d7` agrega el import. Desplegado.

### 2. 🟡 Service Worker no registra (todas las páginas)
- **Síntoma:** Console warning en cada página:
  ```
  SecurityError: Failed to register a ServiceWorker for scope ('/') with script ('/static/js/sw.js'):
  The path of the provided scope ('/') is not under the max scope allowed ('/static/js/').
  ```
- **Impacto:** PWA no funciona offline; no afecta funcionalidad principal.
- **Fix sugerido:** agregar header `Service-Worker-Allowed: /` en nginx para `/static/js/sw.js`, o mover `sw.js` a la raíz (`/sw.js`).

### 3. 🟡 `Chart is not defined` en /prestamos/
- **Síntoma:** Console error `ReferenceError: Chart is not defined` al cargar `/prestamos/`.
- **Causa:** template ejecuta `new Chart(...)` antes de que Chart.js esté cargado, o falta el script tag.
- **Impacto:** las gráficas de cuotas pendientes no se renderizan (pero el listado y los KPIs sí).
- **Fix sugerido:** mover el `<script src="chart.js">` al `<head>` con `defer`, o envolver el inline script en `DOMContentLoaded`.

### 4. 🟡 CSRF token incorrecto en algún submit aislado
- **Síntoma:** log Django `Forbidden (CSRF token from POST has incorrect length.): /login/` aparece esporádicamente.
- **Causa probable:** alguna sesión se quedó con cookie csrftoken estale o hubo race con el reset diario.
- **Impacto:** ocasional, requiere reload de página para regenerar token.

## 🔵 Mejoras / faltantes

### 5. Datos seed insuficientes en Vacaciones, Nóminas, Préstamos
Los módulos cargan UI vacía. Para una demo más impactante:
- **Vacaciones:** crear `SaldoVacacional` para los 20 empleados (15 días anuales acumulados) + 3-5 `SolicitudVacacional` aprobadas/pendientes.
- **Nóminas:** crear 1-2 `PeriodoNomina` cerrados con líneas calculadas (sueldos, gratificación, AFP, IR 5ta) + boletas PDF generadas.
- **Préstamos:** 2-3 préstamos en curso con cuotas pagadas/pendientes.
- **Reclutamiento:** ahora hay 1 vacante creada por mí. Convendría seed con 3-4 vacantes en distintos estados (publicada, en proceso, cubierta) + candidatos.
- **Onboarding:** 1-2 procesos en curso para mostrar el flujo.

### 6. Páginas con 404 raros
- `/portal/` → 404 Harmoni (debería redirigir o mostrar el portal del colaborador)
- `/empleados/` → 404 (es `/personal/`, sería bueno alias)
- `/personal/empleado/<id>/` → 404 (es `/personal/<id>/`)

### 7. Banner instalación PWA en demo
- En la página `/reclutamiento/nueva/` aparece banner "Instalar Harmoni" sobre el botón Crear Vacante.
- **Impacto:** dificulta el click en demo.
- **Fix sugerido:** desactivar prompt de PWA en `DEMO_MODE`.

### 8. Falta de feedback visual al guardar
Al crear vacante exitosamente, redirige al detalle pero sin toast/banner de confirmación. UX mejorable.

### 9. Footer "© 2026" en demo y producción
Está bien pero año hardcodeado. Sugerencia: usar `{{ today|date:"Y" }}`.

### 10. Reclutamiento: dashboard muestra "0 vacantes" pero hay 1 creada
Verificar después del reset si los KPIs del dashboard se actualizan (puede ser caché).

## Conclusión

✅ La demo está **funcional para presentar al cliente** — todos los módulos críticos cargan sin errores 500. El único bug crítico de runtime (`NameError settings`) ya está arreglado.

🟡 Hay 3 bugs menores que conviene arreglar antes de la presentación final (Chart.js, Service Worker, CSRF esporádico).

🔵 Para que la demo "venda mejor", invertir 2-3 horas en seeds adicionales (nóminas con boletas, vacaciones, préstamos) — el cliente verá un sistema con datos donde todo es realista.

## Próximos pasos sugeridos

| # | Prioridad | Acción | Esfuerzo |
|---|---|---|---|
| 1 | Alta | Arreglar Chart.js order en `/prestamos/` | 15 min |
| 2 | Alta | Service Worker scope | 15 min |
| 3 | Alta | Seed de PeriodoNomina + boletas (1-2 períodos) | 1-2 h |
| 4 | Media | Seed de SolicitudVacacional + saldos | 30 min |
| 5 | Media | Seed de Préstamos con cuotas | 30 min |
| 6 | Media | Seed de 3-4 vacantes con candidatos | 30 min |
| 7 | Baja | Desactivar PWA prompt en DEMO_MODE | 10 min |
| 8 | Baja | Toast de confirmación al guardar | 15 min |

Total para tener una demo **realmente impactante**: ~5 horas de trabajo concentrado.
