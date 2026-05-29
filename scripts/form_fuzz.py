"""Llena formularios de creación con datos plausibles y hace POST (rollback).
Replica a un usuario completando el form; marca solo respuestas 500 (bug en
la lógica de guardado: signals, denormalización, generación PDF, etc.)."""
import re
import traceback
from html.parser import HTMLParser
from django.test import Client
from django.urls import get_resolver, reverse, NoReverseMatch
from django.contrib.auth import get_user_model
from django.db import transaction
import django.apps

U = get_user_model()
admin = U.objects.filter(is_superuser=True).first()


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_form = False
        self.in_select = False
        self.cur_select = None
        self.first_opt = {}
        self.fields = {}  # name -> dict(tag, type, value)
        self._select_has_value = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'form':
            self.in_form = True
        if not self.in_form:
            return
        if tag == 'input':
            name = a.get('name')
            if name and a.get('type') not in ('submit', 'button', 'reset'):
                self.fields[name] = {'tag': 'input', 'type': a.get('type', 'text'),
                                     'value': a.get('value', '')}
        elif tag == 'textarea':
            name = a.get('name')
            if name:
                self.fields[name] = {'tag': 'textarea', 'type': 'text', 'value': ''}
        elif tag == 'select':
            self.in_select = True
            self.cur_select = a.get('name')
            self._select_has_value = False
            if self.cur_select:
                self.fields[self.cur_select] = {'tag': 'select', 'type': 'select', 'value': ''}
        elif tag == 'option' and self.in_select and self.cur_select:
            val = a.get('value', '')
            # primer option con value no vacío
            if val and not self._select_has_value:
                self.fields[self.cur_select]['value'] = val
                self._select_has_value = True

    def handle_endtag(self, tag):
        if tag == 'select':
            self.in_select = False
            self.cur_select = None
        if tag == 'form':
            self.in_form = False


def fill_value(name, meta):
    t = (meta['type'] or '').lower()
    n = name.lower()
    if meta['tag'] == 'select':
        return meta['value']
    if name == 'csrfmiddlewaretoken' or t == 'hidden':
        return meta['value']
    if t == 'checkbox':
        return 'on'
    if t in ('date',):
        return '2026-05-29'
    if t in ('datetime-local',):
        return '2026-05-29T08:00'
    if t == 'time':
        return '08:00'
    if t == 'number':
        return '1'
    if t == 'email' or 'email' in n or 'correo' in n:
        return 'prueba@harmoni.pe'
    if 'dni' in n or 'documento' in n:
        return '70000001'
    if 'ruc' in n:
        return '20123456789'
    if 'telefono' in n or 'celular' in n or 'phone' in n:
        return '999000111'
    if 'monto' in n or 'sueldo' in n or 'importe' in n or 'salario' in n:
        return '1500'
    return 'Prueba QA'


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
            v = model.objects.values_list('pk', flat=True).first()
            if isinstance(v, int):
                ints.add(v)
        except Exception:
            pass
ints = sorted(ints)[:20] or [1]

c = Client()
c.force_login(admin)

patterns = collect(get_resolver())
targets = []
for pat, name in patterns:
    if not name:
        continue
    if not re.search(r'(crear|nuev[oa]|/add/|registrar)/?$', pat):
        continue
    if any(x in pat for x in ['admin/', 'api/', '__debug__']):
        continue
    params = list(PARAM_RE.finditer(pat))
    if any((m.group('conv') or 'str') not in ('int', 'slug', 'str', 'pk') for m in params):
        continue
    built = None
    for iv in ints:
        kwargs = {m.group('name'): ('x' if (m.group('conv') in ('slug', 'str') and m.group('name') != 'pk') else iv) for m in params}
        try:
            built = reverse(name, kwargs=kwargs); break
        except NoReverseMatch:
            try:
                built = reverse(name, args=[iv] * len(params)); break
            except NoReverseMatch:
                built = None
    if built:
        targets.append((name, built))

errors = []
filled = 0
for name, url in targets:
    try:
        g = c.get(url)
    except Exception:
        continue
    if g.status_code != 200 or b'<form' not in g.content.lower():
        continue
    fp = FormParser()
    try:
        fp.feed(g.content.decode('utf-8', 'replace'))
    except Exception:
        continue
    if not fp.fields:
        continue
    payload = {n: fill_value(n, m) for n, m in fp.fields.items()}
    filled += 1
    try:
        with transaction.atomic():
            r = c.post(url, data=payload, follow=False)
            transaction.set_rollback(True)
        if r.status_code >= 500:
            errors.append((url, r.status_code, name, ''))
    except Exception:
        tb = traceback.format_exc().strip().splitlines()
        errors.append((url, 'EXC', name, tb[-1][:150]))

lines = [f'=== FORM FUZZ: {len(targets)} create-urls | forms llenados={filled} | FAIL(500/EXC): {len(errors)} ===']
for url, sc, name, detail in errors:
    lines.append(f'  [{sc}] {url}  ({name})  {detail}')
open('scripts/_fuzz_result.txt', 'w', encoding='utf-8').write('\n'.join(lines))
print('\n'.join(lines))
