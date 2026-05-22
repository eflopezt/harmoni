# Harmoni — API REST Documentation

> API REST DRF (Django REST Framework) para integraciones externas y apps mobile.
> Base URL: `https://demo.harmoni.pe/api/v1/` (demo) o `https://harmoni.pe/api/v1/` (prod).

## Tabla de contenidos

1. [Autenticación](#autenticación)
2. [Schema OpenAPI / Swagger](#schema-openapi--swagger)
3. [Reclutamiento](#reclutamiento)
4. [Postulaciones — Custom Actions](#postulaciones--custom-actions)
5. [Errores comunes](#errores-comunes)
6. [Rate limiting](#rate-limiting)
7. [Postman collection](#postman-collection)

---

## Autenticación

Harmoni soporta dos métodos:

### 1. SessionAuthentication (browser, cookies)
Para apps que ya usan login de Django.

### 2. JWT (recomendado para mobile)

**Obtener token:**
```bash
curl -X POST https://demo.harmoni.pe/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "demo"}'
```

Respuesta:
```json
{
  "access":  "eyJ0eXAi...",
  "refresh": "eyJ0eXAi..."
}
```

**Usar el token en headers:**
```bash
curl https://demo.harmoni.pe/api/v1/reclutamiento/postulaciones/ \
  -H "Authorization: Bearer eyJ0eXAi..."
```

**Refrescar token:**
```bash
curl -X POST https://demo.harmoni.pe/api/token/refresh/ \
  -H "Content-Type: application/json" \
  -d '{"refresh": "eyJ0eXAi..."}'
```

---

## Schema OpenAPI / Swagger

- **OpenAPI 3.0 schema:** `GET /api/schema/`
- **Swagger UI interactiva:** `GET /api/schema/swagger-ui/`
- **ReDoc UI:** `GET /api/schema/redoc/`

---

## Reclutamiento

### Vacantes (read-only)

**Listar vacantes activas:**
```bash
curl https://demo.harmoni.pe/api/v1/reclutamiento/vacantes/ \
  -H "Authorization: Bearer $TOKEN"
```

Filtros disponibles:
- `?area=X` — área Django pk
- `?estado=PUBLICADA|EN_PROCESO|CERRADA`
- `?prioridad=ALTA|MEDIA|BAJA`
- `?tipo_contrato=PLAZO_FIJO|INDEFINIDO|HONORARIOS`
- `?publica=true|false` — solo publicadas externamente
- `?search=cocinero` — busca en titulo/descripcion/requisitos
- `?ordering=-fecha_publicacion`

**Detalle de vacante:**
```bash
curl https://demo.harmoni.pe/api/v1/reclutamiento/vacantes/42/ \
  -H "Authorization: Bearer $TOKEN"
```

### Etapas del Pipeline (read-only)

```bash
curl https://demo.harmoni.pe/api/v1/reclutamiento/etapas/ \
  -H "Authorization: Bearer $TOKEN"
```

Respuesta:
```json
[
  {"id": 1, "nombre": "Recibido",   "codigo": "recibido",   "orden": 1, "color": "#0f766e", "activa": true},
  {"id": 2, "nombre": "Screening",  "codigo": "screening",  "orden": 2, "color": "#3b82f6", "activa": true},
  ...
]
```

### Postulaciones (CRUD + custom actions)

**Listar:**
```bash
curl https://demo.harmoni.pe/api/v1/reclutamiento/postulaciones/ \
  -H "Authorization: Bearer $TOKEN"
```

Filtros: `?vacante=X&etapa=Y&estado=ACTIVA&fuente=LINKEDIN`

**Crear postulación:**
```bash
curl -X POST https://demo.harmoni.pe/api/v1/reclutamiento/postulaciones/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "vacante": 42,
    "etapa": 1,
    "nombre_completo": "Edwin López",
    "email": "edwin@ejemplo.com",
    "telefono": "987654321",
    "experiencia_anos": 5,
    "fuente": "LINKEDIN"
  }'
```

**Actualizar (patch parcial):**
```bash
curl -X PATCH https://demo.harmoni.pe/api/v1/reclutamiento/postulaciones/100/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"notas": "Excelente candidato, programar segunda entrevista"}'
```

---

## Postulaciones — Custom Actions

### `POST /<pk>/mover-etapa/`

Mueve la postulación a otra etapa. Dispara email al candidato + notif in-app a reclutadores.

```bash
curl -X POST https://demo.harmoni.pe/api/v1/reclutamiento/postulaciones/100/mover-etapa/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "etapa_id": 3,
    "comentario": "Pasa a entrevista técnica"
  }'
```

Respuesta:
```json
{
  "id": 100,
  "nombre_completo": "Edwin López",
  "etapa": 3,
  "etapa_nombre": "Entrevista",
  "etapa_color": "#a855f7",
  ...
}
```

Errores:
- `400` si la postulación no está ACTIVA
- `404` si la etapa_id no existe o está inactiva

### `POST /<pk>/descartar/`

```bash
curl -X POST https://demo.harmoni.pe/api/v1/reclutamiento/postulaciones/100/descartar/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"motivo": "No cumple requisitos de experiencia mínima"}'
```

Descarta la postulación (estado=DESCARTADA), dispara email cortés + notif in-app, y queda disponible en el Banco de Talento.

### `POST /<pk>/toggle-tag/`

```bash
curl -X POST https://demo.harmoni.pe/api/v1/reclutamiento/postulaciones/100/toggle-tag/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tag": "top_talent"}'
```

Tags válidos: `top_talent`, `prioritario`, `referido`, `no_show`, `reubicar`, `en_espera`, `seguimiento`.

Respuesta:
```json
{
  "ok": true,
  "tags": ["top_talent", "prioritario"],
  "has_tag": true
}
```

### `POST /bulk/`

Acciones masivas sobre múltiples postulaciones (max 200 por request).

**Bulk mover:**
```bash
curl -X POST https://demo.harmoni.pe/api/v1/reclutamiento/postulaciones/bulk/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "ids": [100, 101, 102, 103],
    "accion": "mover",
    "etapa_id": 3
  }'
```

**Bulk descartar:**
```bash
curl -X POST https://demo.harmoni.pe/api/v1/reclutamiento/postulaciones/bulk/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "ids": [100, 101],
    "accion": "descartar",
    "motivo": "Posición congelada"
  }'
```

**Bulk tag:**
```bash
curl -X POST https://demo.harmoni.pe/api/v1/reclutamiento/postulaciones/bulk/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "ids": [100, 101, 102],
    "accion": "tag_add",
    "tag": "seguimiento"
  }'
```

**Bulk nota:**
```bash
curl -X POST https://demo.harmoni.pe/api/v1/reclutamiento/postulaciones/bulk/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "ids": [100, 101],
    "accion": "nota",
    "texto": "Coordinar entrevistas grupales el viernes"
  }'
```

### `GET /funnel-stats/`

Stats agregadas por etapa, útil para dashboards mobile.

```bash
curl https://demo.harmoni.pe/api/v1/reclutamiento/postulaciones/funnel-stats/ \
  -H "Authorization: Bearer $TOKEN"
```

Respuesta:
```json
[
  {"etapa_id": 1, "etapa_nombre": "Recibido",   "count": 12, "color": "#0f766e"},
  {"etapa_id": 2, "etapa_nombre": "Screening",  "count": 8,  "color": "#3b82f6"},
  {"etapa_id": 3, "etapa_nombre": "Entrevista", "count": 5,  "color": "#a855f7"},
  {"etapa_id": 4, "etapa_nombre": "Oferta",     "count": 2,  "color": "#10b981"},
  {"etapa_id": 5, "etapa_nombre": "Contratado", "count": 1,  "color": "#15803d"}
]
```

---

## Errores comunes

| HTTP | Significado |
|------|-------------|
| 200  | OK |
| 201  | Creado |
| 400  | Bad request — datos invalidos (ver body) |
| 401  | No autenticado |
| 403  | Sin permisos |
| 404  | Recurso no encontrado |
| 405  | Method not allowed |
| 429  | Rate limit excedido |

Body de error:
```json
{
  "error": "Solo postulaciones activas pueden moverse."
}
```

Validation errors:
```json
{
  "etapa_id": ["Este campo es requerido."]
}
```

---

## Rate limiting

- Anónimos: 100 req/hora
- Autenticados: 1000 req/hora
- Bulk action: 200 items max por request

---

## Postman collection

Importa [`postman_collection.json`](./postman_collection.json) en Postman.

Variables que debes configurar:
- `base_url`: `https://demo.harmoni.pe/api/v1`
- `token`: tu access token JWT

---

## Soporte

- Issues: contacta a ventas@harmoni.pe
- Demo en vivo: [demo.harmoni.pe](https://demo.harmoni.pe) — login `admin/demo`
