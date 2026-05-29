"""Captura screenshots del ERP (autenticado) para el manual de usuario.

Usa el Chrome del sistema vía Playwright async (channel='chrome', sin descargas;
la API async evita greenlet, que no compila en Python 3.14).
Requiere el dev server en localhost:8001 y una session key válida.

Uso:
    .venv/Scripts/python.exe scripts/capture_manual.py <SESSION_KEY>
"""
import sys
import os
import asyncio
from playwright.async_api import async_playwright

SK = sys.argv[1] if len(sys.argv) > 1 else ''
BASE = 'http://localhost:8001'
OUT = os.path.join('docs', 'manual', 'img')
os.makedirs(OUT, exist_ok=True)

PAGES = [
    ('01_dashboard',          '/',                                   'body', False),
    ('02_nominas_panel',      '/nominas/',                           'body', True),
    ('03_nomina_nuevo',       '/nominas/periodos/nuevo/',            'form', True),
    ('04_nomina_detalle',     '/nominas/periodos/4/',                'body', True),
    ('05_nomina_registro',    '/nominas/registros/46/',              'body', True),
    ('06_emision_boletas',    '/nominas/boletas/',                   'body', True),
    ('07_asistencia',         '/asistencia/',                        'body', True),
    ('08_asistencia_matriz',  '/asistencia/calendario/',             'body', False),
    ('09_personal_lista',     '/personal/',                          'body', True),
    ('10_personal_detalle',   '/personal/212/',                      'body', True),
    ('11_vacaciones',         '/vacaciones/',                        'body', True),
    ('12_vacaciones_nueva',   '/vacaciones/nueva/',                  'form', True),
    ('13_prestamos',          '/prestamos/',                         'body', True),
    ('14_prestamos_nuevo',    '/prestamos/nuevo/',                   'form', True),
    ('15_reclutamiento_pipe', '/reclutamiento/pipeline/',            'body', False),
    ('16_dashboard_ejec',     '/sistema/dashboard/ejecutivo/',       'body', True),
    ('17_disciplinaria',      '/disciplinaria/',                     'body', True),
    ('18_evaluaciones',       '/evaluaciones/',                      'body', True),
]


async def main():
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel='chrome', headless=True)
        ctx = await browser.new_context(viewport={'width': 1440, 'height': 900})
        await ctx.add_cookies([{'name': 'sessionid', 'value': SK,
                                'domain': 'localhost', 'path': '/'}])
        page = await ctx.new_page()
        for slug, url, sel, full in PAGES:
            try:
                await page.goto(BASE + url, wait_until='networkidle', timeout=20000)
                if sel:
                    try:
                        await page.wait_for_selector(sel, timeout=4000)
                    except Exception:
                        pass
                await page.wait_for_timeout(700)
                path = os.path.join(OUT, slug + '.png')
                await page.screenshot(path=path, full_page=full)
                title = await page.title()
                results.append(f'  OK  {slug:24} {url:38} "{title[:40]}"')
            except Exception as e:
                results.append(f'  ERR {slug:24} {url:38} {type(e).__name__}: {str(e)[:60]}')
        await browser.close()
    print('\n'.join(results))
    ok = len([r for r in results if r.strip().startswith('OK')])
    print(f'\n{ok}/{len(PAGES)} capturas en {OUT}/')


asyncio.run(main())
