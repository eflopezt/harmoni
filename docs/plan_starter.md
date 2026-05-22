# Plan Starter — Arquitectura y referencia técnica

> Documentación del feature **Plan Starter** (S/149/mes, hasta 30 colaboradores)
> implementado en Harmoni ERP. Para devs nuevos, sales o cualquiera que necesite
> entender cómo funciona el gating + onboarding del tier económico.

## Tabla de contenidos

1. [Visión general](#visión-general)
2. [Arquitectura](#arquitectura)
3. [URLs y endpoints](#urls-y-endpoints)
4. [Modelo de datos](#modelo-de-datos)
5. [Middleware y context processors](#middleware-y-context-processors)
6. [Signals](#signals)
7. [Sidebar gating](#sidebar-gating)
8. [Comandos CLI](#comandos-cli)
9. [Auto-login para demos](#auto-login-para-demos)
10. [Wizard de onboarding](#wizard-de-onboarding)
11. [Dashboard "Mi cuenta"](#dashboard-mi-cuenta)
12. [Cron protection](#cron-protection)
13. [Activar un cliente real](#activar-un-cliente-real)
14. [Troubleshooting](#troubleshooting)

---

## Visión general

El **Plan Starter** es el tier comercial más económico de Harmoni:
- **Precio:** S/ 149 + IGV / mes
- **Capacidad:** hasta 30 colaboradores activos
- **Empresas:** 1 RUC
- **Alcance:** lo mínimo necesario para correr planilla

### Decisión de diseño

El cliente del Plan Starter es típicamente una **PYME pequeña** (hasta 30 personas,
1 RUC). Necesita planilla mensual, boletas PDF, asistencia y papeletas. No necesita
portal del trabajador, reclutamiento con IA ni features enterprise.

El feature gating se aplica en **3 capas**:
1. **URL middleware** (`PlanStarterMiddleware`) — 32 patterns bloqueados con redirect a `/upgrade/`
2. **Context processor** — flags `oculta_*` para que los templates puedan hidear UI
3. **Sidebar HTML** — wrappers `{% if not es_plan_starter %}` para limpieza visual

---

## Arquitectura

```
┌────────────────────────────────────────────────────────────────┐
│  REQUEST                                                       │
│     │                                                          │
│     ▼                                                          │
│  PlanStarterMiddleware                                         │
│     │ is_starter_user(request.user)?                           │
│     │   1. Personal.empresa.plan == 'STARTER'  (producción)    │
│     │   2. user.username in STARTER_USERNAMES  (fallback demo) │
│     │                                                          │
│     ├─ si es Starter Y url bloqueada → 302 /upgrade/           │
│     └─ sino → continúa al view                                 │
│                                                                │
│  CONTEXT PROCESSOR                                             │
│     Inyecta: es_plan_starter, oculta_*, plan_actual            │
│     Inyecta: mod_* (overrideado a False si es Starter)         │
│                                                                │
│  TEMPLATE base.html                                            │
│     {% if not es_plan_starter %}sidebar item enterprise{% endif%}│
│     Badge sidebar + banner topbar si es Starter                │
│                                                                │
│  RESPONSE                                                      │
└────────────────────────────────────────────────────────────────┘
```

---

## URLs y endpoints

### Públicas (sin autenticación)

| URL | Vista | Descripción |
|---|---|---|
| `/d/<slug>/` | `views_demo_autologin.demo_autologin` | Auto-login demo (rate-limit 10/min) |
| `/demo/`, `/demo2/` | `demo_landing` | Landing page comercial |
| `/onboarding/starter/` | `views_onboarding_starter.step1` | Wizard paso 1 |
| `/onboarding/starter/admin/` | `step2` | Wizard paso 2 |
| `/onboarding/starter/listo/` | `step3` | Wizard paso 3 |

### Autenticadas

| URL | Vista | Descripción |
|---|---|---|
| `/upgrade/` | `views_upgrade.upgrade_plan` | Página de upgrade con 4 planes |
| `/cuenta/plan/` | `views_mi_cuenta.mi_cuenta_plan` | Dashboard con KPIs del plan |
| `/api/v1/me/plan/` | `api_plan.api_me_plan` | API JSON con info del plan |

### Auto-login slugs

```python
DEMO_AUTOLOGIN_USERS = {
    'starter':    'demo2',
    'enterprise': 'demo',
    's':          'demo2',  # alias
    'e':          'demo',
    'pixelmotion': 'demo2',
    'edo':         'demo',
}
```

URLs:
- `https://demo.harmoni.pe/d/starter/` → login como `demo2`
- `https://demo.harmoni.pe/d/enterprise/` → login como `demo`

---

## Modelo de datos

### `Empresa.plan`

Campo `CharField` con choices STARTER / PROFESIONAL / BUSINESS / ENTERPRISE.

```python
class Empresa(models.Model):
    PLAN_CHOICES = [
        ('STARTER',     'Starter — S/ 149/mes (hasta 30 colaboradores)'),
        ('PROFESIONAL', 'Profesional — S/ 399/mes (hasta 100 colaboradores)'),
        ('BUSINESS',    'Business — S/ 799/mes (hasta 300 colaboradores)'),
        ('ENTERPRISE',  'Enterprise — Personalizado (300+ colaboradores)'),
    ]
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='PROFESIONAL')
```

**Migration:** `empresas/migrations/0010_empresa_plan.py`

### Hard cap por plan

| Plan | Trabajadores |
|---|---:|
| STARTER | 30 |
| PROFESIONAL | 100 |
| BUSINESS | 300 |
| ENTERPRISE | sin tope |

Aplicado en:
- `Personal.clean()` — validación en `model.full_clean()`
- `signals_plan_starter.enforce_plan_worker_cap` — `pre_save` (captura `bulk_create`)

---

## Middleware y context processors

### `core/middleware_plan_starter.py`

```python
STARTER_BLOCKED_PATTERNS = [
    r'^/reclutamiento/',
    r'^/capacitaciones/',
    r'^/evaluaciones/',
    # ... 32 patrones total
    r'^/portal/',  r'^/mi-portal/',
    r'^/nominas/boletas/\d+/notificar/',
    # etc.
]
```

`PlanStarterMiddleware` aplica:
- **Whitelist:** `/admin/`, `/logout/`, `/static/`, `/media/`, `/upgrade/`, `/login/`, `/cuenta/`
- **Bypass:** users anónimos y users no-Starter
- **Bloqueo:** Starter users en URLs del patterns → redirect a `/upgrade/`

### `core/context_processors.py`

Inyecta en cada template:
- `es_plan_starter` (bool)
- `plan_actual` (str)
- 16 flags `oculta_*` (portal, pdf, capacitaciones, ...)

### `personal/context_processors.py`

Override de `mod_*` para Starter — fuerza a False las features enterprise
aunque el user sea `is_superuser`.

---

## Signals

### `core/signals_plan_starter.py`

#### `pre_save` Personal — hard cap

Bloquea altas (no edición) que superen el tope del plan.

#### `post_save` Personal — upsell alert

Al alcanzar **93% del cap** (28/30 en Starter), envía email a `ventas@harmoni.pe`
con detalle del cliente para upsell proactivo.

Anti-flood: max 1 alerta por día por empresa (via Django cache).

---

## Sidebar gating

`templates/base.html` — wrappers manualmente:

```django
{% if not es_plan_starter %}{# starter-gate-open #}
<!-- ══ RECLUTAMIENTO ══ -->
<div class="nav-section">...</div>
{# starter-gate-close #}{% endif %}
```

`templates/home.html` — tiles del home también gateados.

**Script idempotente** para re-aplicar: `scripts/patch_sidebar_starter.py <ruta-base.html>`

### Badge + banner

Para Starter:
- **Badge** en sidebar (pill gris con CTA a /upgrade/)
- **Banner** amarillo arriba del main con "Plan Starter — hasta 30 colaboradores"

---

## Comandos CLI

### `set_empresa_plan`

```bash
# Activar plan
python manage.py set_empresa_plan <RUC> STARTER

# Listar todos
python manage.py set_empresa_plan --list
```

### `seed_demo_audiovisual`

Crea Pixel Motion Design SAC (25 workers, plan=STARTER).

```bash
python manage.py seed_demo_audiovisual
```

---

## Auto-login para demos

`core/views_demo_autologin.py`

### Seguridad

- Solo en hosts `demo.*` (configurable en `_is_demo_host()`)
- Solo slugs en whitelist `DEMO_AUTOLOGIN_USERS`
- Rate-limit 10 hits / IP / 60s (Django cache)
- Log de cada acceso

### Uso

Comparte con prospectos por WhatsApp/email:
```
https://demo.harmoni.pe/d/starter/    → Pixel Motion (Starter)
https://demo.harmoni.pe/d/enterprise/ → Grupo EDO (Enterprise)
```

---

## Wizard de onboarding

`/onboarding/starter/` — 3 pasos:

1. **Empresa** — RUC, razón social, contacto
2. **Admin user** — username, password, nombres
3. **Confirmación** — resumen + activación

Crea automáticamente:
- `Empresa(plan='STARTER', activa=True)`
- `User(is_staff=True)` con auto-login

Datos parciales viven en `request.session['onboarding_starter']`.

---

## Dashboard "Mi cuenta"

`/cuenta/plan/` — 4 KPIs:
- Workers activos / cap (barra de progreso color-coded)
- Períodos generados
- Boletas emitidas + storage estimado
- Próximo pago (si hay Suscripcion)

**Cache:** KPIs cacheados 5 min por empresa.

**CTA contextual:**
- `≥80%` workers → 🚨 "Estás cerca del límite"
- sino → 💡 "¿Necesitas más funcionalidades?"

---

## Cron protection

`/opt/harmoni-demo/reset_demo.sh` — cron 3 AM diario en el demo.

Después del reset agrega:
```bash
docker exec ... python manage.py seed_demo_audiovisual
docker exec ... python manage.py set_empresa_plan 20612345678 STARTER
docker exec ... python -c "Empresa.objects.exclude(ruc=PM).update(plan='ENTERPRISE')"
```

Garantiza que cada noche Pixel Motion vuelve a STARTER y las EDO a ENTERPRISE.

---

## Activar un cliente real

### Opción A — Onboarding self-service

Cliente entra a `/onboarding/starter/` y se registra solo. Sistema crea
Empresa + User + activa Plan Starter automáticamente.

### Opción B — Manual (admin)

```bash
# 1. Crear empresa desde admin Django o shell
docker exec harmoni-web python manage.py shell -c "
from empresas.models import Empresa
e = Empresa.objects.create(
    ruc='20XXXXXXXXX',
    razon_social='Cliente SAC',
    plan='STARTER',
)
"

# 2. O bien activar plan de empresa existente
docker exec harmoni-web python manage.py set_empresa_plan 20XXXXXXXXX STARTER

# 3. Crear admin user
docker exec -it harmoni-web python manage.py createsuperuser

# 4. Vincular User → Personal → Empresa (desde admin Django)
```

### Opción C — Container aislado (producción)

```bash
cd /opt/harmoni-starter/
./spinup_starter.sh <client_slug> <port>
# Crea: DB postgres dedicada, container con HARMONI_PLAN=STARTER,
# media/static/logs separados.
```

Ver `deploy/spinup_starter.sh` y `deploy/docker-compose.starter.yml`.

---

## Troubleshooting

### El user no ve el sidebar limpio aunque es Starter

1. Verificar que `Personal.empresa.plan == 'STARTER'`
2. Verificar que `personal/context_processors.py` está en `TEMPLATES` settings
3. Limpiar cache: `docker exec harmoni-web python -c "from django.core.cache import cache; cache.clear()"`

### El middleware bloquea URLs core (falso positivo)

1. Verificar regex en `STARTER_BLOCKED_PATTERNS`
2. Verificar `ALWAYS_ALLOW` en el middleware
3. Correr tests: `pytest core/tests/test_plan_starter_middleware.py`

### Hard cap no funciona

1. Verificar que `core` está en `INSTALLED_APPS`
2. Verificar que `core/apps.py` importa `core.signals_plan_starter` en `ready()`
3. Probar manualmente:
   ```python
   from personal.models import Personal
   Personal.objects.create(empresa=emp_starter, ...)  # debe ValidationError
   ```

### Auto-login no funciona en demo

1. Verificar host: `print(request.get_host())` debe empezar con `demo.`
2. Verificar slug en `DEMO_AUTOLOGIN_USERS`
3. Verificar que el User existe en DB
4. Si rate-limited (429), esperar 60s

---

## Tests

```bash
# Tests unitarios del middleware
pytest core/tests/test_plan_starter_middleware.py -v

# Tests E2E (wizard + API + auto-login + dashboard)
pytest core/tests/test_plan_starter_e2e.py -v
```

---

## Referencias

- Vault session: `Vault/Harmoni/sesion_2026-05-22_plan_starter_complete.md`
- Templates de venta: `Cotizaciones/Harmoni/templates_followup_starter.md`
- Cotización ejemplo: `Cotizaciones/Harmoni/salida/Cotizacion_STARTER_Pixel_Motion_2026-05-22.pdf`
- Manual usuario sección 20.5: `MANUAL_USUARIO.md`
