"""Crawler de URLs parametrizadas: prueba PKs/slugs reales para exponer 500s
en páginas de detalle/edición (bugs de template que el crawl simple no ve)."""
import re
import traceback
from django.test import Client
from django.urls import get_resolver
from django.contrib.auth import get_user_model
import django.apps

U = get_user_model()
admin = U.objects.filter(is_superuser=True).first()

# Pool de PKs reales (primer pk de cada modelo) y slugs reales
candidate_ints = set()
candidate_slugs = set()
for app in django.apps.apps.get_app_configs():
    for model in app.get_models():
        try:
            first = model.objects.values_list('pk', flat=True).first()
            if isinstance(first, int):
                candidate_ints.add(first)
            slug_fields = [f.name for f in model._meta.fields
                           if f.get_internal_type() == 'SlugField' or f.name == 'slug']
            for sf in slug_fields:
                val = model.objects.exclude(**{sf: ''}).values_list(sf, flat=True).first()
                if val:
                    candidate_slugs.add(val)
        except Exception:
            pass
candidate_ints = sorted(candidate_ints)[:40]
candidate_slugs = list(candidate_slugs)[:40]


def collect(resolver, prefix=''):
    out = []
    for p in resolver.url_patterns:
        if hasattr(p, 'url_patterns'):
            out += collect(p, prefix + str(p.pattern))
        else:
            out.append((prefix + str(p.pattern), p.name))
    return out


PARAM_RE = re.compile(r'<(?:(?P<conv>[^:>]+):)?(?P<name>[^>]+)>')

patterns = collect(get_resolver())
param_urls = []
for pat, name in patterns:
    if not name:
        continue
    params = list(PARAM_RE.finditer(pat))
    if not params:
        continue
    # Solo manejamos int/slug/str/pk; saltamos otros conversores raros
    kinds = [m.group('conv') or 'str' for m in params]
    if any(k not in ('int', 'slug', 'str', None, 'pk') for k in kinds):
        continue
    if any(x in pat for x in ['admin/', 'api/', '__debug__', 'logout', 'media/', 'static/']):
        continue
    param_urls.append((name, params, pat))

from django.urls import reverse, NoReverseMatch

c = Client()
c.force_login(admin)

errors = []
tested = 0
skipped = 0
non404 = 0
status_hist = {}
for name, params, pat in param_urls:
    # construir combinaciones de candidatos: probamos hasta encontrar un non-404
    int_idx = [m.group('name') for m in params if (m.group('conv') in ('int', None) or m.group('name') == 'pk')]
    slug_idx = [m.group('name') for m in params if m.group('conv') in ('slug', 'str') and m.group('name') != 'pk']
    found_non404 = False
    last_status = None
    tries = 0
    for iv in (candidate_ints or [1]):
        kwargs = {}
        for m in params:
            pn = m.group('name')
            conv = m.group('conv')
            if conv in ('slug', 'str') and pn != 'pk':
                kwargs[pn] = candidate_slugs[0] if candidate_slugs else 'x'
            else:
                kwargs[pn] = iv
        try:
            url = reverse(name, kwargs=kwargs)
        except NoReverseMatch:
            try:
                url = reverse(name, args=[iv] * len(params))
            except NoReverseMatch:
                skipped += 1
                break
        tries += 1
        try:
            r = c.get(url, follow=False)
            last_status = r.status_code
            if r.status_code != 404:
                found_non404 = True
                non404 += 1
                status_hist[r.status_code] = status_hist.get(r.status_code, 0) + 1
                if r.status_code >= 500:
                    errors.append((url, r.status_code, name, ''))
                break
        except Exception:
            tb = traceback.format_exc().strip().splitlines()
            errors.append((url, 'EXC', name, tb[-1][:140]))
            found_non404 = True
            break
        if tries >= 15:
            break
    tested += 1

lines = [f'=== DETAIL CRAWL: {tested} param-urls | non-404 reached={non404} | hist={dict(sorted(status_hist.items()))} | FAIL: {len(errors)} ===']
for url, sc, name, detail in errors:
    lines.append(f'  [{sc}] {url}  ({name})  {detail}')
open('scripts/_detail_result.txt', 'w', encoding='utf-8').write('\n'.join(lines))
print('\n'.join(lines))
