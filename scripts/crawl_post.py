"""Prueba endpoints POST con datos vacíos, envuelto en rollback.
Un form sano responde 200/400/302 con errores de validación; un 500 = bug
(view asume datos presentes, falta manejo de entrada inválida)."""
import re
import traceback
from django.test import Client
from django.urls import get_resolver, reverse, NoReverseMatch
from django.contrib.auth import get_user_model
from django.db import transaction

U = get_user_model()
admin = U.objects.filter(is_superuser=True).first()


def collect(resolver, prefix=''):
    out = []
    for p in resolver.url_patterns:
        if hasattr(p, 'url_patterns'):
            out += collect(p, prefix + str(p.pattern))
        else:
            out.append((prefix + str(p.pattern), p.name, p.callback))
    return out


PARAM_RE = re.compile(r'<(?:(?P<conv>[^:>]+):)?(?P<name>[^>]+)>')

# Pool de pks reales
import django.apps
ints = set()
for app in django.apps.apps.get_app_configs():
    for model in app.get_models():
        try:
            v = model.objects.values_list('pk', flat=True).first()
            if isinstance(v, int):
                ints.add(v)
        except Exception:
            pass
ints = sorted(ints)[:20] or [1]

patterns = collect(get_resolver())
c = Client()
c.force_login(admin)

errors = []
tested = 0
for pat, name, cb in patterns:
    if not name:
        continue
    if any(x in pat for x in ['admin/', 'api/', '__debug__', 'logout', 'media/', 'static/', 'login', 'eliminar', 'delete', 'borrar', 'cancelar', 'aprobar', 'rechazar', 'enviar', 'notificar', 'reset', 'import']):
        continue
    params = list(PARAM_RE.finditer(pat))
    kinds = [m.group('conv') or 'str' for m in params]
    if any(k not in ('int', 'slug', 'str', 'pk') for k in kinds):
        continue
    # construir url
    built = None
    for iv in ints:
        kwargs = {}
        for m in params:
            pn, conv = m.group('name'), m.group('conv')
            kwargs[pn] = 'x' if (conv in ('slug', 'str') and pn != 'pk') else iv
        try:
            built = reverse(name, kwargs=kwargs)
            break
        except NoReverseMatch:
            try:
                built = reverse(name, args=[iv] * len(params)); break
            except NoReverseMatch:
                built = None
    if not built:
        continue
    # ¿acepta POST? probamos; si GET ya da 405 sabemos que es POST-only
    try:
        g = c.get(built)
        if g.status_code != 405:
            continue  # no es POST-only; ya cubierto por crawl GET
    except Exception:
        continue
    tested += 1
    try:
        with transaction.atomic():
            r = c.post(built, data={}, follow=False)
            transaction.set_rollback(True)
        if r.status_code >= 500:
            errors.append((built, r.status_code, name, ''))
    except Exception as e:
        tb = traceback.format_exc().strip().splitlines()
        errors.append((built, 'EXC', name, tb[-1][:150]))

lines = [f'=== POST CRAWL (empty data): {tested} post-only endpoints | FAIL(500/EXC): {len(errors)} ===']
for url, sc, name, detail in errors:
    lines.append(f'  [{sc}] {url}  ({name})  {detail}')
open('scripts/_post_result.txt', 'w', encoding='utf-8').write('\n'.join(lines))
print('\n'.join(lines))
