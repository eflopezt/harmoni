# Módulos archivados

Módulos experimentales retirados del árbol activo (P17 del análisis de
flujo 2026-07-02) para reducir superficie de mantenimiento. Recuperables
con `git mv` inverso.

- `mobile/` — app React Native (2 commits, TODOs). No era app Django.
- `wa_marketing/` — marketing por WhatsApp (2 commits). Era app Django:
  al restaurar, re-registrar en `config/settings/base.py` (INSTALLED_APPS)
  y `config/urls.py`, y mover `wa_marketing_templates/` de vuelta a
  `templates/wa_marketing/`. Sus tablas siguen en la BD (las migraciones
  aplicadas no se revierten).
