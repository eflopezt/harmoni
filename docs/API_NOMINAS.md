# API de Nóminas — Harmoni ERP

Documentación completa de los endpoints de Nóminas para integraciones, monitoreo y mobile.

**Versión:** v1
**Base URL:** `https://harmoni.pe/api/v1/`  (o `https://demo.harmoni.pe/api/v1/` para demo)
**Autenticación:** JWT (excepto endpoints públicos marcados)

---

## Tabla de contenidos

1. [Autenticación](#1-autenticación)
2. [Conceptos Remunerativos](#2-conceptos-remunerativos)
3. [Onboarding Validador](#3-onboarding-validador)
4. [Mi Día Nóminas](#4-mi-día-nóminas)
5. [Calculadora](#5-calculadora)
6. [Health endpoint público](#6-health-endpoint-público)

---

## 1. Autenticación

### Obtener token JWT

```bash
curl -X POST https://harmoni.pe/api/v1/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret"}'
```

**Respuesta:**
```json
{
  "access":  "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
}
```

Incluir en requests posteriores:
```bash
curl -H "Authorization: Bearer <access_token>" ...
```

---

## 2. Conceptos Remunerativos

### Listar conceptos

```bash
GET /api/v1/nominas/conceptos/
GET /api/v1/nominas/conceptos/?tipo=INGRESO&activo=true&q=sueldo
```

**Filtros disponibles:**
- `tipo`: INGRESO / DESCUENTO / APORTE_EMPLEADOR
- `subtipo`: REMUNERATIVO / NO_REMUNERATIVO / PROVISION
- `categoria`: SUELDO / BONIFICACION / etc.
- `activo`: true / false
- `q`: búsqueda full-text en nombre, código, PLAME, descripción

**Respuesta:**
```json
[
  {
    "id": 1,
    "codigo": "sueldo_basico",
    "nombre": "Remuneración o jornal básico",
    "tipo": "INGRESO",
    "subtipo": "REMUNERATIVO",
    "categoria": "SUELDO",
    "afecto_essalud": true,
    "afecto_afp": true,
    "afecto_onp": true,
    "afecto_renta": true,
    "afecto_cts": true,
    "afecto_gratif": true,
    "afecto_vacaciones": true,
    "codigo_plame": "0121",
    "casilla_plame": "",
    "activo": true,
    "es_sistema": true,
    "inconsistencias": [],
    "plame_info": {"codigo": "0121", "casilla": null, "sin_plame": false}
  }
]
```

### Crear concepto

```bash
curl -X POST https://harmoni.pe/api/v1/nominas/conceptos/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "codigo": "vale_canasta",
    "nombre": "Vale de canasta",
    "tipo": "INGRESO",
    "subtipo": "NO_REMUNERATIVO",
    "categoria": "ALIMENTACION",
    "monto_fijo": "200.00",
    "afecto_essalud": false,
    "codigo_plame": "0903"
  }'
```

### Aplicar template

```bash
GET  /api/v1/nominas/conceptos/templates/                       # Lista catálogo
POST /api/v1/nominas/conceptos/templates/vale_canasta/aplicar/  # Crear desde template
```

### Auto-fix

```bash
POST /api/v1/nominas/conceptos/<id>/autofix/
```

### Estadísticas

```bash
GET /api/v1/nominas/conceptos/stats/
```
**Respuesta:**
```json
{
  "total": 65,
  "activos": 60,
  "sistema": 28,
  "custom": 37,
  "con_plame": 33,
  "sin_plame": 27,
  "por_tipo":    {"INGRESO": 40, "DESCUENTO": 15, "APORTE_EMPLEADOR": 10},
  "por_subtipo": {"REMUNERATIVO": 38, "NO_REMUNERATIVO": 14, "PROVISION": 13}
}
```

---

## 3. Onboarding Validador

### Score + checks en JSON

```bash
GET /api/v1/nominas/onboarding/
```

**Respuesta:**
```json
{
  "score": 87,
  "status": "mejorable",
  "status_label": "Configuración mejorable",
  "empresa": {
    "id": 1,
    "ruc": "20612345678",
    "razon_social": "Consorcio Stiler SAC",
    "plan": "PROFESIONAL"
  },
  "totals": { "ok": 18, "warn": 3, "error": 0, "info": 1, "total": 22 },
  "checks": [
    {
      "categoria": "empresa",
      "cat_label": "Empresa",
      "titulo": "RUC válido",
      "descripcion": "RUC 20612345678 registrado.",
      "severidad": "ok",
      "peso": 20
    }
  ],
  "pendientes": [
    {
      "categoria": "conceptos",
      "titulo": "5 conceptos sin PLAME",
      "descripcion": "Estos conceptos no exportarán al archivo SUNAT.",
      "severidad": "warn",
      "link": "/nominas/conceptos/configurar/?activo=1",
      "peso": 40
    }
  ],
  "generated_at": "2026-05-23T15:30:00Z"
}
```

**Casos de uso:**
- CI check: bloquear merge si score < 70
- Status page externo
- Slack notification al exceder umbrales

---

## 4. Mi Día Nóminas

### Dashboard JSON mobile-ready

```bash
GET /api/v1/nominas/mi-dia/
```

**Respuesta:**
```json
{
  "hoy": "2026-05-23",
  "saludo": "¡Buenas tardes",
  "usuario": "Edwin López",
  "periodo": {
    "id": 12,
    "tipo": "REGULAR",
    "anio": 2026,
    "mes": 5,
    "estado": "CALCULADO",
    "descripcion": "Planilla Regular 5/2026"
  },
  "periodo_estado": "actual",
  "kpi": {
    "trabajadores": 119,
    "neto": 285430.50,
    "bruto": 367520.00,
    "descuentos": 82089.50
  },
  "eventos_hoy": [],
  "eventos_semana": [
    {
      "fecha": "2026-05-28",
      "dias": 5,
      "label": "Reunión cierre RR.HH.",
      "severidad": "recordatorio"
    }
  ],
  "acuses_pendientes": 12,
  "inconsistencias": 0,
  "tareas": [
    {
      "icon": "fas fa-check-circle",
      "titulo": "Aprobar planilla mayo 2026",
      "descripcion": "Período calculado. Revisa y aprueba.",
      "link": "/nominas/periodos/12/"
    }
  ]
}
```

---

## 5. Calculadora

### Calculadora API JSON (POST)

```bash
curl -X POST https://harmoni.pe/api/calculadora/ \
  -H "Content-Type: application/json" \
  -d '{
    "sueldo": "3000",
    "regimen": "AFP",
    "afp": "Integra",
    "tiene_eps": true,
    "asig_familiar": true,
    "horas_extra": "0",
    "sctr_tasa": "0"
  }'
```

**Respuesta:**
```json
{
  "sueldo": "3000.00",
  "rem_total": "3113.00",
  "descuentos": {
    "afp_aporte":   {"label": "AFP Integra aporte 10%",        "monto": "311.30"},
    "afp_comision": {"label": "AFP Integra comisión 1.55%",    "monto": "48.25"},
    "afp_seguro":   {"label": "AFP Integra prima seguro 1.74%", "monto": "54.17"}
  },
  "total_descuentos": "413.72",
  "neto": "2699.28",
  "aportes_empleador": {
    "essalud": {"label": "ESSALUD 6.75%", "monto": "210.13"}
  },
  "costo_total": "3323.13",
  "costo_full_loaded": "3997.13",
  "pct_descuentos": "13.29",
  "pct_carga_empleador": "6.75"
}
```

**Sin autenticación** — pública para integraciones de vendedores.

---

## 6. Health endpoint público

### Status global

```bash
GET /api/health/nominas/
```

**Sin autenticación · cache 60s · sin datos sensibles**

**Respuesta:**
```json
{
  "status": "ok",
  "service": "harmoni-nominas",
  "timestamp": "2026-05-23T15:30:00Z",
  "onboarding_score": 87,
  "conceptos": {"activos": 60, "total": 65},
  "cambios_7d": 12
}
```

**Estados:** `ok` / `warn` / `critico`

**Casos de uso:**
- Status page (Uptime, StatusPage.io, BetterStack)
- Monitoreo Datadog/New Relic
- Health check de Kubernetes/Docker

---

## OpenAPI / Swagger UI

Para explorar todos los endpoints interactivamente:
- Swagger UI: `https://harmoni.pe/api/v1/docs/`
- ReDoc:      `https://harmoni.pe/api/v1/redoc/`
- Schema:     `https://harmoni.pe/api/v1/schema/`

---

## Rate limiting

- Endpoints autenticados: **100 req/min/usuario**
- Endpoints públicos: **20 req/min/IP**
- Cache 60s en health endpoint

## Errores

| Código | Significado |
|-------:|-------------|
| 200    | OK |
| 201    | Creado |
| 400    | Datos inválidos en request |
| 401    | Autenticación requerida o token inválido |
| 403    | Permiso denegado (ej: borrar concepto del sistema) |
| 404    | Recurso no encontrado |
| 409    | Conflicto (ej: aplicar template que ya existe) |
| 429    | Rate limit excedido |
| 500    | Error interno (reportar a soporte) |

## Soporte

- Email: api@harmoni.pe
- Issues GitHub: github.com/eflopezt/harmoni/issues
- Docs interactivas: https://harmoni.pe/api/v1/docs/
