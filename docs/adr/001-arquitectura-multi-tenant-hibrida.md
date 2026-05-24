# ADR-001: Arquitectura híbrida multi-tenant + Docker dedicado por plan

**Status:** Aceptado
**Date:** 2026-05-23
**Decisión por:** Edwin López (CEO/Gerente Operaciones, Harmoni)
**Implementación owner:** Harmoni dev team

---

## Contexto

Harmoni ERP atiende clientes de tamaños muy distintos:

- **Pixel Motion** (Starter, agencia audiovisual): 25 trabajadores, S/149/mes
- **Consorcio Stiler** (Profesional, productor): ~50 trabajadores, S/399/mes
- **EDO Premium** (Enterprise prospect): 800 trabajadores, 24 RUCs

Hoy todos comparten **una sola instancia Docker** (`harmoni-demo-web` y `harmoni-web` en prod) con aislamiento por `empresa_id` row-level. Esto funciona ahora pero plantea preguntas:

1. ¿Qué pasa cuando EDO cierre? Sus datos sensibles (planilla 800 trabajadores) compartirían DB con otros clientes.
2. ¿Cómo personalizar engine/conceptos para un cliente sin afectar otros?
3. ¿Cómo escalar a 50+ clientes sin que el costo de infra explote?

## Alternativas evaluadas

### A. Status quo: multi-tenant row-level en 1 instancia
- ✅ Costo infra mínimo (1 VPS Contabo ~S/40/mes maneja todo)
- ✅ Deploys instantáneos (1 contenedor)
- ✅ Features cross-empresa (Centro de Comando, Audit Log, Mi Día) funcionan natural
- ❌ Sin aislamiento de datos a nivel DB (vulnerable a bug en query → leakage)
- ❌ No vendible como "instancia dedicada" para enterprise
- ❌ Personalización deep imposible (1 cliente requiere fork del código)

### B. Docker por cliente (uniforme, propuesta inicial)
- ✅ Aislamiento total
- ✅ Vendible como premium
- ✅ Personalización deep
- ❌ Costo lineal (20 clientes × S/40/mes = S/800/mes mínimo)
- ❌ Deploys 20× más lentos (necesita Ansible/Terraform)
- ❌ Pérdida features cross-empresa
- ❌ No vale para Starter/Profesional (sensibles a precio)
- ❌ Operativamente caro sin equipo DevOps

### C. **Híbrido escalonado por plan** (decisión adoptada)

| Plan | Precio | Trabajadores | Arquitectura |
|---|---:|---:|---|
| **Starter** | S/149/mes | ≤30 | Multi-tenant 1 instancia + row-level |
| **Profesional** | S/399/mes | ≤100 | Multi-tenant 1 instancia + row-level |
| **Business** | S/799/mes | ≤300 | Multi-tenant 1 instancia + **DB schema separado** |
| **Enterprise** | Custom | 300+ | **Docker dedicado** + DB dedicada + subdominio propio |

## Decisión

**Adoptamos la opción C (híbrida por plan).**

Justificación:
- Los clientes pequeños no le importa "instancia dedicada", les importa precio
- Los clientes enterprise SÍ exigen aislamiento y lo pueden pagar (paga el costo operativo)
- Mantenemos features cross-empresa (Centro de Comando, Audit Log, Validador Onboarding, Mi Día) para el grueso de clientes
- Casos reales: EDO (24 RUCs, 800 trabajadores) → Docker dedicado se justifica. Pixel Motion (25 trab) → no

## Consecuencias

### Positivas
- Costos de infra crecen sub-linealmente (3-4 instancias prod manejan 50+ clientes Starter/Profesional)
- Vendible: "Plan Enterprise incluye instancia dedicada y dominio propio"
- Justificable: cliente paga > S/2000/mes → tiene su propio servidor
- Las features ya construidas (Audit, Mi Día, Validador, Calculadoras, Workflow del Mes) siguen funcionando sin cambios

### Negativas / a manejar
- Hay que mantener 2 modos de deploy (compartido + dedicado)
- Docker template enterprise debe ser robusto y bien documentado
- Si un cliente Profesional crece a >100 trab, debe migrar a Business → migración de DB schema
- Diferencias entre planes pueden generar bugs sutiles si no se testean

### Acciones derivadas (siguientes pasos)

1. ✅ Filtrar `ConceptoAuditLog` por empresa (FK + UI filtro) — task #371
2. ✅ Health endpoint con `?empresa=X` — task #372
3. ✅ Docker template + docker-compose.enterprise.yml — task #373
4. ✅ Comando `provision_enterprise_client` — task #374
5. ✅ Tests aislamiento cross-empresa — task #375
6. ⏳ Postponer migración a `django-tenants` (schema separado) hasta tener 5+ clientes Business
7. ⏳ Plan EDO: cuando firme → deployar Docker dedicado siguiendo este ADR

## Casos de uso por plan

### Cliente Starter (Pixel Motion)
- Login en `harmoni.pe` o `pixelmotion.harmoni.pe` (CNAME)
- Sus 25 trabajadores y data ven `empresa_id` filtrado vía middleware
- Comparten Docker + DB con otros Starter
- Backup: incluido en backup global, restaurable solo lo de su empresa

### Cliente Enterprise (EDO Premium)
- Login en `edo.harmoni.pe` (subdominio dedicado)
- Su propio Docker container en VPS dedicado
- Su propio Postgres
- Su propio cron de reset/backup
- Branding: logo EDO en topbar via `Empresa.logo`
- Performance: no comparte CPU/RAM con otros

### Migración Profesional → Business (futura)
- Trigger: cliente supera 100 trabajadores
- Acción: crear schema dedicado en mismo Postgres, mover sus tablas vía script
- Downtime: < 5 minutos
- Sin cambios en código (Postgres schemas transparentes para Django)

## Referencias

- Patrón inspirado en: Salesforce Tiers, HubSpot, Notion (Free vs Plus vs Enterprise)
- Stack actual: Django 5.1 + PostgreSQL 16 + Docker en Contabo
- Plan starter docs: `docs/plan_starter.md`
- Multi-tenancy library considerada: `django-tenants` (NO adoptada todavía, ver punto 6)
