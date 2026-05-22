"""
Test rápido de bloqueos Plan Starter — corre dentro del contenedor demo.

Uso (desde dentro del contenedor con DJANGO_SETTINGS_MODULE configurado):
    docker exec harmoni-demo-web python manage.py shell < scripts/test_starter_blocks.py
"""
from django.test import Client
from django.contrib.auth import get_user_model

U = get_user_model()
u = U.objects.get(username='demo2')
c = Client(HTTP_HOST='demo.harmoni.pe', SERVER_NAME='demo.harmoni.pe')
c.force_login(u)

# URLs que DEBEN bloquear (302 → /upgrade/)
test_urls_block = [
    '/personal/organigrama/',
    '/personal/contratos/',
    '/personal/roster/matricial/',
    '/calendario/',
    '/capacitaciones/',
    '/disciplinaria/',
    '/asistencia/banco-horas/',
    '/reportes/planilla/pdf/',
    '/reportes/asistencia/pdf/',
    '/reclutamiento/',
    '/sistema/dashboard/ejecutivo/',
    '/workflows/',
    '/salarios/',
    '/prestamos/',
]

print('=' * 70)
print('URLs que DEBEN redirigir a /upgrade/')
print('=' * 70)
ok_block = 0
for url in test_urls_block:
    try:
        r = c.get(url, follow=False, secure=True)
        loc = r.get('Location', '')
        is_blocked = r.status_code == 302 and '/upgrade/' in loc
        marker = 'BLOCKED OK' if is_blocked else 'NOT BLOCKED'
        if is_blocked:
            ok_block += 1
        print(f'  {marker:12} [{r.status_code}] {url:42} -> {loc[:45]}')
    except Exception as e:
        print(f'  ERROR        {url:42} {type(e).__name__}: {str(e)[:40]}')

print()
print('=' * 70)
print('URLs que NO deben bloquear (accesibles)')
print('=' * 70)
test_urls_allow = [
    '/',
    '/personal/',
    '/asistencia/',
    '/nominas/',
    '/vacaciones/',
    '/upgrade/',
    '/demo2/',
]
ok_allow = 0
for url in test_urls_allow:
    try:
        r = c.get(url, follow=False, secure=True)
        is_ok = r.status_code in (200, 301) or (r.status_code == 302 and '/upgrade/' not in r.get('Location', ''))
        marker = 'OK' if is_ok else 'BLOCKED!!'
        if is_ok:
            ok_allow += 1
        print(f'  {marker:12} [{r.status_code}] {url:42} -> {r.get("Location", "(rendered)")[:45]}')
    except Exception as e:
        print(f'  ERROR        {url:42} {type(e).__name__}: {str(e)[:40]}')

print()
print('=' * 70)
print(f'RESUMEN: bloqueados {ok_block}/{len(test_urls_block)}, permitidos {ok_allow}/{len(test_urls_allow)}')
print('=' * 70)
