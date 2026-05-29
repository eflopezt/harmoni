"""Crawler: enumera todas las URLs sin args y las visita como admin. Reporta 500/errores."""
import traceback
from django.test import Client
from django.urls import get_resolver
from django.contrib.auth import get_user_model

U = get_user_model()
admin = U.objects.filter(is_superuser=True).first()


def collect(resolver, prefix=''):
    out = []
    for p in resolver.url_patterns:
        if hasattr(p, 'url_patterns'):
            out += collect(p, prefix + str(p.pattern))
        else:
            pat = prefix + str(p.pattern)
            out.append((pat, p.name))
    return out


patterns = collect(get_resolver())
# Solo GET-eables: sin grupos de captura
gettable = []
for pat, name in patterns:
    if '<' in pat or '(?P' in pat or '(' in pat:
        continue
    url = '/' + pat.lstrip('^').rstrip('$')
    if not url.endswith('/') and '.' not in url.split('/')[-1]:
        url += '/'
    if any(x in url for x in ['admin/', 'api/', 'logout', '__debug__', 'media/', 'static/', '.json', 'jsi18n']):
        continue
    gettable.append(url)

gettable = sorted(set(gettable))
c = Client()
c.force_login(admin)

errors = []
ok = 0
for url in gettable:
    try:
        r = c.get(url, follow=False)
        sc = r.status_code
        if sc >= 500:
            errors.append((url, sc, ''))
        else:
            ok += 1
    except Exception as e:
        tb = traceback.format_exc().strip().splitlines()
        errors.append((url, 'EXC', tb[-1][:160]))

lines = [f'=== CRAWL: {len(gettable)} urls | OK<500: {ok} | FAIL: {len(errors)} ===']
for url, sc, detail in errors:
    lines.append(f'  [{sc}] {url}  {detail}')
open('scripts/_crawl_result.txt', 'w', encoding='utf-8').write('\n'.join(lines))
print('\n'.join(lines))
