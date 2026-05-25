# Workflow: Offboarding Trabajador

Flujo estándar de cierre administrativo al cese de un trabajador. Se dispara
automáticamente cuando una `nominas.LiquidacionLaboral` pasa a `estado='CALCULADA'`
y se cierra (estado `CERRADA`) cuando todas las etapas se completan.

## Diagrama de etapas

```
                ┌──────────────────────────────────────────────┐
                │   LiquidacionLaboral.estado == 'CALCULADA'   │
                │   ─────  (signal post_save dispara)  ─────   │
                └─────────────────────┬────────────────────────┘
                                      │
                                      ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ 1. ENCUESTA DE SALIDA                                       │
   │    Aprobador: USUARIO (trabajador cesado)                   │
   │    Plazo: 72h    Vencimiento: ESPERAR                       │
   │    El trabajador responde encuesta de salida (NPS, motivo). │
   └─────────────────────────────┬───────────────────────────────┘
                                 ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ 2. DEVOLUCIÓN DE ACTIVOS                                    │
   │    Aprobador: JEFE_AREA                                     │
   │    Plazo: 120h   Vencimiento: ESCALAR (a usuario alterno)   │
   │    Requiere comentario (lista de activos devueltos / faltantes)
   └─────────────────────────────┬───────────────────────────────┘
                                 ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ 3. LIQUIDACIÓN PAGADA                                       │
   │    Aprobador: GRUPO_DJANGO "Tesorería"                      │
   │    Plazo: 168h (7 días)   Vencimiento: ESPERAR              │
   │    Requiere comentario (N° de operación bancaria).          │
   └─────────────────────────────┬───────────────────────────────┘
                                 ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ 4. CARTA DE NO ADEUDO                                       │
   │    Aprobador: SUPERUSER (RRHH)                              │
   │    Plazo: 72h    Vencimiento: AUTO_APROBAR                  │
   │    RRHH emite y entrega la carta al ex-trabajador.          │
   └─────────────────────────────┬───────────────────────────────┘
                                 ▼
   ┌─────────────────────────────────────────────────────────────┐
   │ 5. CIERRE ADMINISTRATIVO                                    │
   │    Aprobador: SUPERUSER (RRHH)                              │
   │    Plazo: 48h    Vencimiento: AUTO_APROBAR                  │
   │    Cierra expediente. Notifica al solicitante.              │
   └─────────────────────────────┬───────────────────────────────┘
                                 ▼
                ┌──────────────────────────────────────────────┐
                │   LiquidacionLaboral.estado := 'CERRADA'     │
                │   (vía valor_aprobado del FlujoTrabajo)      │
                └──────────────────────────────────────────────┘
```

Tiempos máximos en cadena (worst case): 72 + 120 + 168 + 72 + 48 = **480 horas
≈ 20 días naturales** desde el cese.

## Integración con `LiquidacionLaboral`

- **Modelo**: `nominas.LiquidacionLaboral` (ya tiene FK opcional
  `instancia_flujo → workflows.InstanciaFlujo`).
- **Trigger**: signal `post_save` en `nominas/signals.py` —
  `disparar_workflow_offboarding`. Se ejecuta cuando:
  - `instance.estado == 'CALCULADA'`
  - `instance.instancia_flujo_id is None` (idempotente)
- **Solicitante** del workflow: primer superuser activo (fallback a primer
  `is_staff` activo). El trabajador cesado es el aprobador de la etapa 1.
- **Cierre**: cuando la última etapa se aprueba, el motor pone
  `LiquidacionLaboral.estado = 'CERRADA'` automáticamente (vía
  `FlujoTrabajo.campo_resultado='estado'` + `valor_aprobado='CERRADA'`).
- **Falla silenciosa**: si el seed aún no corrió y el flujo no existe en BD,
  el signal solo emite un warning en logs (`nominas.signals`), no rompe el
  cálculo de la liquidación.

## Cómo lo personaliza el cliente

Cada cliente puede ajustar el flujo desde el admin Django sin tocar código:

1. **Cambiar tiempos límite** — `/admin/workflows/etapaflujo/` → editar
   `tiempo_limite_horas` por etapa.
2. **Cambiar aprobador** — En la misma pantalla:
   - `tipo_aprobador='SUPERUSER'` → cualquier admin RRHH
   - `tipo_aprobador='USUARIO'` → usuario específico (`aprobador_usuario`)
   - `tipo_aprobador='JEFE_AREA'` → jefe del área del cesado (resuelto en
     runtime vía `Personal.subarea.area.jefe.usuario`)
   - `tipo_aprobador='GRUPO_DJANGO'` → grupo Django (`aprobador_grupo`)
3. **Cambiar acción al vencer** — `accion_vencimiento`:
   `ESPERAR`, `AUTO_APROBAR`, `AUTO_RECHAZAR`, `ESCALAR`. Para `ESCALAR`,
   definir `escalar_a` (User alterno).
4. **Agregar / quitar etapas** — Insertar `EtapaFlujo` con `orden` apropiado
   bajo el mismo `FlujoTrabajo`. El motor las recorrerá en orden.
5. **Desactivar el flujo temporalmente** — `FlujoTrabajo.activo = False`.
   El signal seguirá disparándose pero `crear_instancia` retornará `None`
   con un warning en logs.

## Cómo se siembra

Idempotente por nombre (`Offboarding Trabajador`). Crea el grupo
`Tesorería` si no existe.

```bash
python manage.py seed_offboarding_flow             # crea / no toca
python manage.py seed_offboarding_flow --dry-run   # solo muestra
```

Está integrado en `deploy/reset_demo.sh.enriched` y
`docs/reset_demo.sh.remote`, justo después de `migrate --no-input` y antes
de los seeds de datos (para que las `LiquidacionLaboral` creadas por
`seed_demo_nominas` ya disparen el flujo).

## Logs / auditoría

Toda la trazabilidad queda registrada automáticamente:

| Modelo | Qué registra | Cuándo |
|---|---|---|
| `nominas.signals` (logger) | `[Offboarding] LL #N en CALCULADA …` + vinculación InstanciaFlujo | Al disparar el workflow |
| `workflows.InstanciaFlujo` | Estado actual + etapa actual + `iniciado_en` + `etapa_vence_en` + `metadata` (`liquidacion_id`, `personal_doc`, `fecha_cese`) | Una fila por liquidación |
| `workflows.PasoFlujo` | Inmutable: aprobador, decisión (`APROBADO` / `RECHAZADO` / `DELEGADO` / `AUTO_APROBADO` / `AUTO_RECHAZADO`), comentario, fecha | Una fila por cada decisión |
| `comunicaciones` (notificaciones) | Notifica a aprobadores al avanzar etapa, y al solicitante al cerrar (si `notificar_solicitante_al_decidir=True`) | Cada avance |

Consulta rápida de avance:
```python
from nominas.models import LiquidacionLaboral
liq = LiquidacionLaboral.objects.get(pk=...)
print(liq.instancia_flujo.estado, '—', liq.instancia_flujo.etapa_actual)
for paso in liq.instancia_flujo.pasos.all():
    print(paso.fecha, paso.decision, paso.aprobador, paso.comentario)
```

## Tests

`nominas/tests/test_offboarding_flow.py` (9 tests):

- Seed crea flujo + 5 etapas con aprobadores correctos.
- Seed crea grupo Tesorería.
- Seed idempotente (2x no duplica).
- Seed reutiliza grupo Tesorería preexistente.
- `--dry-run` no persiste nada.
- Signal crea `InstanciaFlujo` al pasar LL a `CALCULADA`.
- Signal idempotente: no duplica si ya hay instancia.
- Signal falla silenciosamente si flujo no existe.
- Signal no dispara si estado != `CALCULADA`.

Correr:
```bash
pytest nominas/tests/test_offboarding_flow.py workflows/ -q
```
