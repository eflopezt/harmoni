"""
Smoke test integral del Plan Starter + features Harmoni clave.

Diseñado para correr post-deploy o post-reset_demo nightly.
Devuelve exit code 0 si todo OK, 1 si hay errores críticos.

Uso:
    docker exec -i -e DJANGO_SETTINGS_MODULE=config.settings.production \
        harmoni-demo-web python manage.py shell < scripts/smoke_test_starter.py
"""
import sys
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client


User = get_user_model()


def banner(text):
    line = '═' * 70
    print(f'\n{line}\n  {text}\n{line}')


def check(label, ok, detail=''):
    marker = '✓' if ok else '✗'
    status = 'PASS' if ok else 'FAIL'
    print(f'  [{marker}] {label:48} {status}  {detail}')
    return ok


banner('SMOKE TEST — Plan Starter + Harmoni core')

errors = []

# ── 1. Modelos / DB ────────────────────────────────────────────────────
banner('1. Modelos / DB')
try:
    from empresas.models import Empresa
    total_empresas = Empresa.objects.count()
    starters       = Empresa.objects.filter(plan='STARTER').count()
    enterprises    = Empresa.objects.filter(plan='ENTERPRISE').count()
    if not check('Empresa.plan field exists', True, f'{total_empresas} empresas'):
        errors.append('Empresa.plan')
    if not check('Pixel Motion = STARTER', starters >= 1, f'{starters} empresa(s) STARTER'):
        errors.append('Pixel Motion no marcado STARTER')
    if not check('EDO = ENTERPRISE', enterprises >= 5, f'{enterprises} empresa(s) ENTERPRISE'):
        errors.append('Empresas EDO no marcadas ENTERPRISE')
except Exception as e:
    check('Empresa model', False, str(e))
    errors.append('Empresa model broken')

# ── 2. Users demo ──────────────────────────────────────────────────────
banner('2. Users demo')
for username in ('demo', 'demo2'):
    exists = User.objects.filter(username=username).exists()
    if not check(f'User {username} existe', exists):
        errors.append(f'User {username} missing')

# ── 3. Middleware ──────────────────────────────────────────────────────
banner('3. Middleware Plan Starter')
try:
    from core.middleware_plan_starter import (
        is_starter_user, is_blocked_path, STARTER_BLOCKED_RE
    )
    check('Patterns compilados', len(STARTER_BLOCKED_RE) >= 30,
          f'{len(STARTER_BLOCKED_RE)} regex patterns')
    check('is_blocked_path("/reclutamiento/")', is_blocked_path('/reclutamiento/'))
    check('is_blocked_path("/personal/")', not is_blocked_path('/personal/'),
          'personal NO debe bloquearse')
except Exception as e:
    check('Middleware', False, str(e))
    errors.append('Middleware broken')

# ── 4. URLs core accesibles para Starter ───────────────────────────────
banner('4. URLs accesibles para Starter')
cache.clear()
demo2 = User.objects.filter(username='demo2').first()
if demo2:
    c = Client(HTTP_HOST='demo.harmoni.pe', SERVER_NAME='demo.harmoni.pe')
    c.force_login(demo2)
    for url in ['/', '/personal/', '/asistencia/', '/asistencia/papeletas/', '/nominas/', '/vacaciones/', '/upgrade/', '/cuenta/plan/']:
        r = c.get(url, secure=True, follow=False)
        ok = r.status_code in (200, 301, 302) and '/upgrade/' not in r.get('Location', '')
        if not check(f'GET {url}', ok, f'status {r.status_code}'):
            errors.append(f'{url} {r.status_code}')

# ── 5. URLs bloqueadas para Starter ────────────────────────────────────
banner('5. URLs bloqueadas para Starter')
if demo2:
    for url in ['/reclutamiento/', '/capacitaciones/', '/evaluaciones/', '/portal/', '/mi-portal/', '/comunicaciones/', '/analytics/', '/integraciones/']:
        r = c.get(url, secure=True, follow=False)
        ok = r.status_code == 302 and '/upgrade/' in r.get('Location', '')
        if not check(f'GET {url} → /upgrade/', ok, f'status {r.status_code}'):
            errors.append(f'{url} not blocked')

# ── 6. Endpoints nuevos ────────────────────────────────────────────────
banner('6. Endpoints nuevos (auto-login, wizard, API)')
cache.clear()  # reset rate-limit
c_anon = Client(HTTP_HOST='demo.harmoni.pe', SERVER_NAME='demo.harmoni.pe')
for url, expected_status in [('/d/starter/', 302), ('/d/enterprise/', 302), ('/d/inexistente/', 404), ('/onboarding/starter/', 200)]:
    r = c_anon.get(url, secure=True, follow=False)
    if not check(f'GET {url}', r.status_code == expected_status,
                 f'expected {expected_status}, got {r.status_code}'):
        errors.append(f'{url} unexpected status')

if demo2:
    c.force_login(demo2)
    r = c.get('/api/v1/me/plan/', secure=True)
    check('GET /api/v1/me/plan/', r.status_code == 200, f'status {r.status_code}')
    if r.status_code == 200:
        import json
        data = json.loads(r.content)
        check('API plan = STARTER', data.get('plan') == 'STARTER', f"plan={data.get('plan')}")

# ── 7. Sidebar gating ──────────────────────────────────────────────────
banner('7. Sidebar gating')
if demo2:
    c.force_login(demo2)
    html = c.get('/', secure=True).content.decode('utf-8', errors='ignore')
    hidden_items = ['Reclutamiento', 'Capacitaciones', 'Evaluaciones', 'Disciplinaria', 'Salarios', 'Préstamos', 'Viáticos', 'Analytics', 'Comunicaciones', 'Calendario', 'Contratos', 'Organigrama', 'Integraciones']
    hidden_count = sum(1 for t in hidden_items if html.count(f'>{t}<') == 0)
    if not check(f'{hidden_count}/{len(hidden_items)} items ocultos', hidden_count == len(hidden_items)):
        errors.append('sidebar items not all hidden')
    check('Badge "Plan Starter" visible', 'starter-plan-badge-marker' in html)
    check('Banner topbar visible', 'starter-topbar-banner' in html)

# ── 8. Comandos CLI ────────────────────────────────────────────────────
banner('8. Comandos CLI registrados')
from django.core.management import get_commands
cmds = get_commands()
for cmd_name in ('set_empresa_plan', 'seed_demo_audiovisual'):
    check(f'Comando {cmd_name} registrado', cmd_name in cmds)

# ── 9. Resumen ─────────────────────────────────────────────────────────
banner('RESUMEN')
total_errors = len(errors)
if total_errors == 0:
    print('  ✓ TODOS LOS CHECKS PASARON — Demo Starter saludable\n')
    sys.exit(0)
else:
    print(f'  ✗ {total_errors} ERRORES ENCONTRADOS:')
    for e in errors:
        print(f'    - {e}')
    sys.exit(1)
