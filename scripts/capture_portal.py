"""Captura el Portal del Trabajador (sesión de empleado) para el manual."""
import sys
import os
import asyncio
from playwright.async_api import async_playwright

SK = sys.argv[1] if len(sys.argv) > 1 else ''
BASE = 'http://localhost:8001'

PAGES = [
    ('01_home',           '/mi-portal/'),
    ('02_perfil',         '/mi-portal/perfil/'),
    ('03_asistencia',     '/mi-portal/asistencia/'),
    ('04_nomina',         '/mi-portal/mi-nomina/'),
    ('05_vacaciones',     '/mi-portal/mis-vacaciones/'),
    ('06_papeletas',      '/mi-portal/papeletas/'),
    ('07_roster',         '/mi-portal/roster/'),
    ('08_documentos',     '/mi-portal/documentos/'),
    ('09_evaluaciones',   '/mi-portal/mis-evaluaciones/'),
    ('10_capacitaciones', '/mi-portal/mis-capacitaciones/'),
    ('11_timeline',       '/mi-portal/timeline/'),
    ('12_directorio',     '/mi-portal/directorio/'),
    ('13_calendario',     '/mi-portal/mi-calendario/'),
    ('14_banco_horas',    '/mi-portal/banco-horas/'),
]


async def main():
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel='chrome', headless=True)
        ctx = await browser.new_context(viewport={'width': 1440, 'height': 1000})
        await ctx.add_cookies([{'name': 'sessionid', 'value': SK,
                                'domain': 'localhost', 'path': '/'}])
        page = await ctx.new_page()
        for slug, url in PAGES:
            path = os.path.join('docs', 'manual', 'img', '17_portal', slug + '.png')
            os.makedirs(os.path.dirname(path), exist_ok=True)
            try:
                await page.goto(BASE + url, wait_until='networkidle', timeout=25000)
                await page.wait_for_timeout(800)
                await page.screenshot(path=path, full_page=False)
                title = await page.title()
                results.append(f'  OK  {slug:18} {url:34} "{title[:36]}"')
            except Exception as e:
                results.append(f'  ERR {slug:18} {url:34} {type(e).__name__}: {str(e)[:45]}')
        await browser.close()
    print('\n'.join(results))


asyncio.run(main())
