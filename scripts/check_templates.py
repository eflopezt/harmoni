"""Compila todos los templates del proyecto para detectar TemplateSyntaxError
(errores que solo se manifiestan al renderizar la página)."""
import os
from django.template.loader import get_template
from django.template import TemplateSyntaxError
from django.conf import settings
import django.apps

roots = [str(d) for d in settings.TEMPLATES[0]['DIRS']]
for app in django.apps.apps.get_app_configs():
    p = os.path.join(app.path, 'templates')
    if os.path.isdir(p):
        roots.append(p)

seen = set()
errors = []
checked = 0
for root in roots:
    for dirpath, _, files in os.walk(root):
        for fn in files:
            if not fn.endswith('.html'):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), root).replace('\\', '/')
            if rel in seen:
                continue
            seen.add(rel)
            checked += 1
            try:
                get_template(rel)
            except TemplateSyntaxError as e:
                errors.append((rel, str(e)[:160]))
            except Exception as e:
                # plantillas que solo se cargan por path absoluto, ignorar import-side
                if 'TemplateDoesNotExist' not in type(e).__name__:
                    errors.append((rel, f'{type(e).__name__}: {str(e)[:120]}'))

lines = [f'=== TEMPLATE COMPILE: {checked} templates | ERRORS: {len(errors)} ===']
for rel, msg in errors:
    lines.append(f'  [{rel}]  {msg}')
print('\n'.join(lines))
