# Plan de trabajo: siguientes pasos (handoff Fable 5 → Opus)

**Fecha:** 2026-07-03 · **Autor del plan:** Claude Fable 5 · **Ejecutor:** Claude Opus
**Estado de partida:** TODO el análisis de flujo de Harmoni (tramos 1-4) + fases 1-3 están en producción (harmoni.pe, suite 2416 OK). NexoTalent main (59 commits) desplegado en prod (nexotalent.pe, health verde, suite 2015 OK). Ver detalles en `docs/ANALISIS_FLUJO_COMPLETO_2026-07-02.md` del repo Harmoni y en la memoria del proyecto NexoTalent.

---

## WS1 · RBAC roles reales en Harmoni (proyecto principal)

> **PROGRESO 2026-07-04 (sesión Opus):** fundación construida y 6 módulos
> migrados. Hecho:
> - `core/permisos.py`: `tiene_modulo(user, modulo)`, `puede_aprobar(user)`,
>   `perfil_de(user)`, decorador `requiere_modulo(modulo)`, alias
>   `solo_superuser`. Enlace real User→`personal_data`→`perfil_acceso`.
> - `_puede_ver_admin` corregido (usaba getattrs obsoletos).
> - Migrados al patrón "1 línea" (redefinir el `solo_admin` local a
>   `requiere_modulo('<mod>')`): **reclutamiento, capacitaciones, encuestas,
>   disciplinaria, onboarding, evaluaciones**. Cada superuser sigue entrando;
>   un perfil con el `mod_<x>` opera; sin él, redirect. `landing` permite
>   Mi Día Reclutamiento a quien tenga el módulo.
> - Tests: `core/tests/test_permisos.py` (8, matriz de roles sobre vista
>   real) + suites de los 6 módulos verdes.
>
> **PENDIENTE (próxima sesión):** migrar los módulos restantes con el mismo
> patrón donde sea seguro. Clasificación:
> - **Talento/operación, seguros de migrar 1-línea:** documentos (5 archivos,
>   mixto: `views_cese.py` es sensible → revisar por-vista), analytics
>   (`mod_analytics`, read-only), calendario (ya `mod_calendario`).
> - **Dinero/sensibles, DEJAR superuser (usar `solo_superuser` explícito para
>   documentar la intención):** nóminas (no tiene `mod_`), préstamos,
>   salarios, cierre, viáticos, integraciones (PLAME/SUNAT), workflows.
> - **Mixtos, tratamiento POR-VISTA (no blanket):** asistencia (94 vistas:
>   ver tareo = operación, pero cálculo HE alimenta planilla), personal (49:
>   incluye cese que dispara liquidación), empresas, comunicaciones.
> - Falta: seed asigna perfil pero el usuario debe ser `is_staff=True` para
>   que `tiene_modulo` lo deje pasar — documentar en el flujo de alta de
>   usuarios / o revisar si el perfil debería implicar staff.

**Objetivo:** que un usuario pueda operar Reclutamiento o Nóminas sin ser
superuser. Hoy casi todas las vistas de gestión usan `@solo_admin`
(is_superuser), así que "reclutador" y "analista de nóminas" no existen
como roles reales; incluso el landing por rol (PreferenciaUsuario.landing_default)
bloquea esos destinos a no-superusers por esto.

**Contexto técnico (verificado):**
- `core/models.py` → `PerfilAcceso` ya existe: booleanos `mod_personal`,
  `mod_reclutamiento`, `mod_salarios`, etc. y roles predefinidos
  (ADMIN_RRHH, JEFE_AREA, CONSULTOR, EMPLEADO, PERSONALIZADO). Se asigna
  vía `Personal.perfil_acceso`.
- `core/context_processors.py` → `_puede_ver_admin()` ya considera
  PerfilAcceso (`es_responsable` o `puede_aprobar`).
- El decorador `solo_admin` está definido por-app (ej.
  `asistencia/views/_common.py`, `reclutamiento/views.py:~41`); hay
  MUCHAS copias. Inventariar con:
  `git grep -n "def solo_admin\|@solo_admin" -- "*.py"`

**Pasos:**
1. Inventario: tabla vista→módulo→es-lectura/escritura/dinero, por app
   (reclutamiento, nominas, asistencia, vacaciones, prestamos, cierre).
2. Diseñar UN decorador central en core (propuesta:
   `core/permisos.py::requiere_modulo('reclutamiento', escritura=False)`):
   permite si `is_superuser` O (`user.personal.perfil_acceso` tiene el
   mod_* correspondiente Y, para escritura, un flag tipo `puede_aprobar`
   o nivel de perfil). Definir la matriz ANTES de tocar vistas y
   validarla con Edwin (1 pregunta con la tabla).
3. Migrar módulo por módulo, empezando por **reclutamiento** (no toca
   dinero): reemplazar `@solo_admin` por el decorador nuevo, vista por
   vista, con test de matriz de roles por vista (usuario con perfil
   RECLUTADOR puede; EMPLEADO recibe 403/redirect; superuser sigue
   pudiendo todo).
4. Luego **nóminas solo-lectura** (dashboards, comparativos, boletas
   view). Las vistas de DINERO (aprobar préstamos, generar/aprobar
   períodos, engine, cierre) QUEDAN superuser-only en esta fase; anotar
   como fase 2 del RBAC.
5. Ajustar `_landing_preferido()` en `personal/views/home.py` para
   permitir mi_dia_reclutador/mi_dia_nominas a quien tenga el módulo
   (hoy exige superuser).
6. Crear perfiles seed RECLUTADOR y NOMINAS en el comando de seed de
   perfiles si existe (buscar seed de PerfilAcceso).

**Aceptación:** usuario staff sin superuser con perfil RECLUTADOR opera
el pipeline completo (kanban, mover, entrevistas, CV express) y aterriza
en Mi Día Reclutamiento; suite completa verde; ninguna vista de dinero
accesible sin superuser (test negativo explícito).

**Riesgo alto:** es seguridad. No hacer barrido masivo con sed; migrar
vista por vista con tests. Presupuesto: 2-3 sesiones.

---

## WS2 · Mi Portal 30→~20 items (necesita decisión de Edwin)

**Objetivo:** segunda pasada del menú del trabajador. Ya se quitaron 3
duplicados (Constancias, Organigrama, Timeline, commit `96ee01e`).

**Propuesta pendiente de OK** (del inventario 2026-07-03): quitar del
menú, dejando su acceso en las quick actions de Mi Resumen:
`mi_roster`, `mis_justificaciones`, `mis_prestamos`, `mis_permisos`,
`mis_encuestas` (ojo: perdería el badge), y fusionar subheaders
"Solicitudes"+"Mis Documentos" y "Desarrollo"+"Mi Empresa".

**Pasos:** preguntar a Edwin con la lista exacta (multiselect); aplicar
solo lo aprobado en `templates/base.html` sección miportal; compilar
template + smoke `pytest portal/tests core/tests/test_landing_por_rol.py`.

---

## WS3 · deploy.sh de Harmoni a git-based (robustez)

**Objetivo:** el `deploy/deploy.sh` actual empaqueta el working tree en
tarball y lo sube por scp: tarda >1h por el repo en iCloud, sube basura
(outputs/, tmp/, PDFs no excluidos) y el ssh remoto murió una vez por
connection reset dejando el deploy a medias (2026-07-03).

**Patrón probado que lo reemplaza** (usado 3 veces con éxito esta semana):
```bash
ssh root@212.56.34.166 "cd /opt/harmoni/app && git fetch origin && \
  git reset --hard origin/main && chown -R deploy:deploy . && \
  rm -f /tmp/harmoni-redeploy.log && nohup bash -c 'set -e; \
  cd /opt/harmoni/app; export COMPOSE_PROJECT_NAME=harmoni; \
  docker compose -f deploy/docker-compose.prod.yml build web && \
  docker compose -f deploy/docker-compose.prod.yml run --rm web python manage.py migrate --noinput && \
  docker compose -f deploy/docker-compose.prod.yml run --rm -v /opt/harmoni/staticfiles:/app/staticfiles web python manage.py collectstatic --noinput && \
  docker compose -f deploy/docker-compose.prod.yml up -d --force-recreate && \
  echo DEPLOY_OK' > /tmp/harmoni-redeploy.log 2>&1 &"
# luego poll: grep DEPLOY_OK|Traceback /tmp/harmoni-redeploy.log
# verificar: docker ps healthy + curl https://harmoni.pe/ == 200
```
**Pasos:** reescribir `deploy/deploy.sh` con este flujo (requiere que
main esté pusheado; el script debe abortar si `git status` local tiene
cambios sin push), conservar el viejo como `deploy/deploy_tarball.sh`
para emergencias sin GitHub. Probar en el VPS. `deploy/.env.production`
es gitignored y sobrevive al reset (verificado).

---

## WS4 · Limpieza de ramas y docs (rápido)

1. **NexoTalent:** `tmp-fix-estado` y `merge-main-into-tmp` quedaron
   absorbidas por main (desplegado). Borrarlas local y remoto tras
   confirmar `git branch --merged main`. Revisar ramas `claude/*`
   viejas (varias behind main) y proponer borrado a Edwin.
2. **NexoTalent CLAUDE.md desactualizado:** dice correr tests desde
   `D:\NexoTalent` con `D:\NexoTalent\venv`, pero el repo vive en
   `C:\Users\edwii\iCloudDrive\CSRT\D\NexoTalent` y el venv es `.\venv`.
   Actualizar rutas y el snapshot de tests (hoy: 2015 tests OK tras el
   merge; prod corre main).
3. **Harmoni:** actualizar el RAG del agente de nóminas
   (`nominas/agente_ia/rag.py` o knowledge) con lo nuevo: bandeja
   unificada 8 fuentes, checklist TI, disponibilidad, IR SUNAT activo.

---

## Guardrails para el ejecutor (léelos antes de tocar código)

- **Tests Harmoni:** `cd C:\Users\edwii\iCloudDrive\CSRT\D\Harmoni` y
  `.venv\Scripts\python.exe -m pytest -q` (pytest.ini ya configura
  settings; suite completa ~8 min, 2416 OK al partir).
- **Tests NexoTalent:** desde la raíz del repo,
  `.\venv\Scripts\python.exe manage.py test apps --settings=config.settings.development`
  (LENTA: ~96 min; usar apps específicas para iterar).
- **Deploy NexoTalent:** SIEMPRE
  `cd /opt/nexotalent/app/docker && docker compose -f docker-compose.prod.yml up -d --build`
  (el compose default TUMBA prod). El checkout de prod es `main`.
- **Gotchas Harmoni ya mordidos esta semana:**
  - `ConfiguracionSistema.get()` cachea en Django cache: en tests que
    la modifican, limpiar `cache.delete('harmoni_config_v1')` (hay
    fixture ejemplo en `nominas/tests/test_snapshot_tasas.py`).
  - `{# #}` de Django NO es multilínea: un ejemplo de include dentro de
    un comentario se EJECUTA (recursión infinita). Usar `{% comment %}`.
  - Papeletas espejo de vacaciones llevan
    `detalle='Auto: SolicitudVacacion #...'`: excluirlas al agregar
    conteos para no duplicar.
  - `papeletas_sync._get_or_create_imp` y el thread-local de auditoría
    de NexoTalent ya están corregidos; no reintroducir caches de
    instancia sin validación contra BD.
- **Commits:** mensajes vía `git commit -F -` con heredoc en Bash (los
  here-strings de PowerShell fallan con el sandbox).
- **El repo está en iCloud:** operaciones git/pytest son más lentas de
  lo normal; no asumir cuelgue antes de ~2 min.

**Orden recomendado:** WS4 (calienta motores, 1h) → WS3 (media sesión)
→ WS2 (tras respuesta de Edwin) → WS1 (el plato fuerte, empezar por el
inventario y la matriz de permisos).
