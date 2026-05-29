"""Smoke de análisis estático — guardarraíles contra regresiones de UI.

Estos tests son deterministas (no necesitan DB ni seeds) y blindan las clases
de bug encontradas en la estabilización 2026-05-29:
  - templates faltantes / con error de sintaxis (página 500 al abrir)
  - {% url 'name' %} a nombres inexistentes (botón muerto → NoReverseMatch)
  - {% static 'x' %} a archivos que no existen (imagen/CSS/JS rota)

Solo escanean templates del proyecto (no los de site-packages/.venv).
"""
import os
import re

from django.conf import settings
from django.contrib.staticfiles import finders
from django.template import TemplateSyntaxError
from django.template.loader import get_template
from django.urls import NoReverseMatch, reverse
import django.apps

URL_TAG_RE = re.compile(r"""{%\s*url\s+['"]([a-zA-Z0-9_:\-]+)['"]""")
STATIC_TAG_RE = re.compile(r"""{%\s*static\s+['"]([^'"{}]+)['"]""")
COMMENT_RE = re.compile(r'{%\s*comment.*?%}.*?{%\s*endcomment\s*%}|{#.*?#}', re.DOTALL)


def _strip_comments(txt):
    """Quita bloques {% comment %} y {# #} — su contenido no se renderiza."""
    return COMMENT_RE.sub('', txt)


def _project_template_roots():
    """Dirs de templates del proyecto, excluyendo .venv/site-packages."""
    roots = [str(d) for d in settings.TEMPLATES[0]['DIRS']]
    for app in django.apps.apps.get_app_configs():
        p = os.path.join(app.path, 'templates')
        if os.path.isdir(p):
            roots.append(p)
    base = str(settings.BASE_DIR)
    out = []
    for r in roots:
        if 'site-packages' in r or '.venv' in r:
            continue
        if os.path.commonpath([base, r]) == base:
            out.append(r)
    return out


def _iter_templates():
    seen = set()
    for root in _project_template_roots():
        for dirpath, _, files in os.walk(root):
            for fn in files:
                if not fn.endswith('.html'):
                    continue
                rel = os.path.relpath(os.path.join(dirpath, fn), root).replace('\\', '/')
                if rel in seen:
                    continue
                seen.add(rel)
                yield rel, os.path.join(dirpath, fn)


def test_all_templates_compile():
    """Los templates del proyecto compilan sin TemplateSyntaxError."""
    errors = []
    count = 0
    for rel, full in _iter_templates():
        count += 1
        try:
            get_template(rel)
        except TemplateSyntaxError as e:
            errors.append(f'{rel}: {e}')
        except Exception as e:
            if 'TemplateDoesNotExist' not in type(e).__name__:
                errors.append(f'{rel}: {type(e).__name__}: {e}')
    assert count > 0, 'No se encontraron templates — revisar roots'
    assert not errors, 'Templates con error de compilación:\n' + '\n'.join(errors)


def test_all_url_tags_resolve():
    """Cada {% url 'name' %} apunta a un nombre de URL existente."""
    bad = {}
    for rel, full in _iter_templates():
        try:
            txt = _strip_comments(open(full, encoding='utf-8').read())
        except Exception:
            continue
        for m in URL_TAG_RE.finditer(txt):
            name = m.group(1)
            try:
                reverse(name)
            except NoReverseMatch as e:
                # NoReverseMatch por falta de args es OK (la URL existe, solo
                # necesita parámetros). Solo marcamos nombres inexistentes.
                if 'not a valid view function or pattern name' in str(e):
                    bad.setdefault(name, set()).add(rel)
    assert not bad, 'Referencias {% url %} a nombres inexistentes:\n' + '\n'.join(
        f"  '{name}' usado en: {', '.join(sorted(files))}" for name, files in sorted(bad.items())
    )


def test_all_static_refs_exist():
    """Cada {% static 'x' %} (literal) apunta a un archivo existente."""
    missing = {}
    for rel, full in _iter_templates():
        try:
            txt = _strip_comments(open(full, encoding='utf-8').read())
        except Exception:
            continue
        for m in STATIC_TAG_RE.finditer(txt):
            ref = m.group(1)
            if finders.find(ref) is None:
                missing.setdefault(ref, set()).add(rel)
    assert not missing, 'Referencias {% static %} a archivos inexistentes:\n' + '\n'.join(
        f"  '{ref}' usado en: {', '.join(sorted(files))}" for ref, files in sorted(missing.items())
    )
