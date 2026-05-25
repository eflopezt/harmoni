# Documentación Interna — Harmoni ERP

Carpeta para documentación técnica/operativa **NO comercial**. Tu repo es privado, así que esto solo lo ven colaboradores con acceso.

> ⚠️ **No subas aquí**: contraseñas, claves API, tokens, credenciales SSH/SQL, datos personales reales. Eso va en `harmoni-private/` (repo aparte con git-crypt) o en `.env.production` del VPS.

## Índice

| Doc | Descripción |
|-----|-------------|
| [PLAN_ESTABILIZACION_2026.md](./PLAN_ESTABILIZACION_2026.md) | Hoja de ruta para llevar Harmoni a producción robusta |
| [BUGS_RESUELTOS_2026-Q2.md](./BUGS_RESUELTOS_2026-Q2.md) | Registro de bugs serios detectados y fixes aplicados |
| [DEUDA_TECNICA.md](./DEUDA_TECNICA.md) | Lista priorizada de refactors pendientes |
| [REGLAS_PERUANAS.md](./REGLAS_PERUANAS.md) | Normativa peruana centralizada (RMV, jornada, HE, beneficios, AFP/ONP/EsSalud, IR 5ta, embargo, contratos) |
| [INTEGRACIONES.md](./INTEGRACIONES.md) | Sync Synkro, SUNAT, AFP Net, bancos, Sentry |

## Convenciones

- Archivos en Markdown.
- Cada doc tiene fecha de última revisión arriba.
- Decisiones técnicas se documentan como ADR en `adr/NNN-titulo.md` si afectan arquitectura.
