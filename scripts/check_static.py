"""Verifica que cada {% static 'x' %} en templates apunte a un archivo real
en STATICFILES (referencias rotas = imágenes/CSS/JS que no cargan en práctica)."""
import os
import re
from django.conf import settings
from django.contrib.staticfiles import finders
import django.apps

STATIC_RE = re.compile(r"""{%\s*static\s+['"]([^'"]+)['"]""")

roots = [str(d) for d in settings.TEMPLATES[0]['DIRS']]
for app in django.apps.apps.get_app_configs():
    p = os.path.join(app.path, 'templates')
    if os.path.isdir(p):
        roots.append(p)

seen_files = set()
missing = {}  # ref -> [templates]
checked_refs = 0
for root in roots:
    for dirpath, _, files in os.walk(root):
        for fn in files:
            if not fn.endswith('.html'):
                continue
            full = os.path.join(dirpath, fn)
            try:
                txt = open(full, encoding='utf-8').read()
            except Exception:
                continue
            for m in STATIC_RE.finditer(txt):
                ref = m.group(1)
                if '{' in ref or '}' in ref:  # interpolado dinámico, saltar
                    continue
                checked_refs += 1
                if ref in seen_files:
                    continue
                if finders.find(ref) is None:
                    rel = os.path.relpath(full, root).replace('\\', '/')
                    missing.setdefault(ref, []).append(rel)
                else:
                    seen_files.add(ref)

lines = [f'=== STATIC CHECK: {checked_refs} refs revisadas | FALTANTES: {len(missing)} ===']
for ref, tpls in sorted(missing.items()):
    lines.append(f'  [{ref}]  usado en: {tpls[0]}' + (f' (+{len(tpls)-1})' if len(tpls) > 1 else ''))
open('scripts/_static_result.txt', 'w', encoding='utf-8').write('\n'.join(lines))
print('\n'.join(lines))
