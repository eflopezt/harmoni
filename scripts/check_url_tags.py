"""Valida que cada {% url 'name' %} en templates resuelva a una URL existente."""
import re
import os
from django.urls import reverse, NoReverseMatch
from django.template.loader import get_template  # noqa

URL_RE = re.compile(r"{%\s*url\s+['\"]([a-zA-Z0-9_:\-]+)['\"]")

roots = []
from django.conf import settings
for d in settings.TEMPLATES[0]['DIRS']:
    roots.append(str(d))
# app templates
import django.apps
for app in django.apps.apps.get_app_configs():
    p = os.path.join(app.path, 'templates')
    if os.path.isdir(p):
        roots.append(p)

names = set()
for root in roots:
    for dirpath, _, files in os.walk(root):
        for fn in files:
            if fn.endswith('.html'):
                names.add(os.path.join(dirpath, fn))

bad = {}
for path in sorted(names):
    try:
        txt = open(path, encoding='utf-8').read()
    except Exception:
        continue
    for m in URL_RE.finditer(txt):
        name = m.group(1)
        try:
            reverse(name)
        except NoReverseMatch as e:
            # NoReverseMatch with args is fine (needs params); only flag truly-unknown names
            if 'not a valid view function or pattern name' in str(e):
                bad.setdefault(name, []).append(os.path.relpath(path))

lines = [f'=== URL TAG CHECK: {len(bad)} unknown url names ===']
for name, files in sorted(bad.items()):
    lines.append(f'  [{name}]  used in {len(files)} file(s): {files[0]}')
open('scripts/_urltag_result.txt', 'w', encoding='utf-8').write('\n'.join(lines))
print('\n'.join(lines))
