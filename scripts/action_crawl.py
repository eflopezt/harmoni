"""Prueba endpoints POST de TRANSICIÓN de estado (aprobar/completar/resolver/
mover/generar/anular/confirmar/validar...) con pk real y rollback.
Estos los excluía crawl_post por seguridad; aquí van con transaction.set_rollback.
Excluye verbos de efecto EXTERNO (enviar/notificar/email/whatsapp/sms) y delete.
"""
import re
import traceback
from django.test import Client
from django.urls import get_resolver, reverse, NoReverseMatch
from django.contrib.auth import get_user_model
from django.db import transaction
import django.apps

U = get_user_model()
admin = U.objects.filter(is_superuser=True).first()

VERBS = ['aprobar', 'rechazar', 'completar', 'resolver', 'mover', 'generar',
         'cerrar', 'anular', 'finalizar', 'activar', 'desactivar', 'procesar',
         'confirmar', 'asignar', 'validar', 'cancelar', 'reabrir', 'revisar',
         'evaluar', 'iniciar', 'descargo', 'recalcular', 'marcar']
EXCLUDE = ['enviar', 'notificar', 'email', 'whatsapp', 'sms', 'delete', 'eliminar',
           'borrar', 'reset', 'sync', 'import', 'sidecar', 'reenviar', 'admin/', 'api/']


def collect(resolver, prefix=''):
    out = []
    for p in resolver.url_patterns:
        if hasattr(p, 'url_patterns'):
            out += collect(p, prefix + str(p.pattern))
        else:
            out.append((prefix + str(p.pattern), p.name))
    return out


PARAM_RE = re.compile(r'<(?:(?P<conv>[^:>]+):)?(?P<name>[^>]+)>')

ints = set()
for app in django.apps.apps.get_app_configs():
    for model in app.get_models():
        try:
            for v in model.objects.values_list('pk', flat=True)[:3]:
                if isinstance(v, int):
                    ints.add(v)
        except Exception:
            pass
ints = sorted(ints)[:30] or [1]

c = Client()
c.force_login(admin)

patterns = collect(get_resolver())
errors = []
tested = 0
for pat, name in patterns:
    if not name:
        continue
    low = pat.lower()
    if any(x in low for x in EXCLUDE):
        continue
    if not any(v in low for v in VERBS):
        continue
    params = list(PARAM_RE.finditer(pat))
    if any((m.group('conv') or 'str') not in ('int', 'slug', 'str', 'pk') for m in params):
        continue
    # construir url con pk real (probar varios hasta non-404 en GET o aceptar)
    built = None
    for iv in ints:
        kwargs = {m.group('name'): ('x' if (m.group('conv') in ('slug', 'str') and m.group('name') != 'pk') else iv) for m in params}
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
    # confirmar POST-only
    try:
        if c.get(built).status_code != 405:
            pass  # algunos aceptan GET; igual probamos POST
    except Exception:
        pass
    # buscar un pk que NO devuelva 404 al POST (objeto existe)
    chosen_url = built
    for iv in ints:
        kwargs = {m.group('name'): ('x' if (m.group('conv') in ('slug', 'str') and m.group('name') != 'pk') else iv) for m in params}
        try:
            u = reverse(name, kwargs=kwargs)
        except NoReverseMatch:
            try:
                u = reverse(name, args=[iv] * len(params))
            except NoReverseMatch:
                continue
        try:
            with transaction.atomic():
                r = c.post(u, data={}, follow=False)
                transaction.set_rollback(True)
        except Exception:
            tb = traceback.format_exc().strip().splitlines()
            errors.append((u, 'EXC', name, tb[-1][:150]))
            break
        if r.status_code == 404:
            continue
        chosen_url = u
        tested += 1
        if r.status_code >= 500:
            errors.append((u, r.status_code, name, ''))
        break

lines = [f'=== ACTION CRAWL: {tested} endpoints con objeto real | FAIL: {len(errors)} ===']
for url, sc, name, detail in errors:
    lines.append(f'  [{sc}] {url}  ({name})  {detail}')
open('scripts/_action_result.txt', 'w', encoding='utf-8').write('\n'.join(lines))
print('\n'.join(lines))
