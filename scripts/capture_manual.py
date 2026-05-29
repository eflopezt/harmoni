"""Captura screenshots del ERP (autenticado) para el MANUAL DE USUARIO completo.

Chrome del sistema vía Playwright async (channel='chrome'; la API async evita
greenlet/sync issues en Python 3.14). Requiere dev server en localhost:8001.

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

# (archivo_relativo, url, full_page).  full_page=False para tablas largas.
PAGES = [
    # ── Inicio / Portal ──
    ('00_inicio/01_dashboard',          '/',                              False),
    ('00_inicio/02_buscador',           '/',                              False),
    # ── Personal ──
    ('01_personal/01_lista',            '/personal/',                     False),
    ('01_personal/02_detalle',          '/personal/212/',                 True),
    ('01_personal/03_contratar_express','/personal/express/',             True),
    ('01_personal/04_contratos',        '/contratos/',                    False),
    ('01_personal/05_organigrama',      '/organigrama/',                  False),
    ('01_personal/06_roster',           '/roster/matricial/',             False),
    ('01_personal/07_reportes',         '/reportes/',                     True),
    # ── Asistencia ──
    ('02_asistencia/01_dashboard',      '/asistencia/',                   True),
    ('02_asistencia/02_kpis',           '/asistencia/kpis/',              True),
    ('02_asistencia/03_matricial',      '/asistencia/calendario/',        False),
    ('02_asistencia/04_papeletas',      '/asistencia/papeletas/',         False),
    ('02_asistencia/05_banco_horas',    '/asistencia/banco-horas/',       False),
    ('02_asistencia/06_briefing',       '/asistencia/briefing/',          True),
    ('02_asistencia/07_exportaciones',  '/asistencia/exportar/',          True),
    ('02_asistencia/08_importaciones',  '/asistencia/importar/',          True),
    # ── Nóminas ──
    ('03_nominas/01_periodos',          '/nominas/',                      False),
    ('03_nominas/02_nuevo_periodo',     '/nominas/periodos/nuevo/',       True),
    ('03_nominas/03_detalle',           '/nominas/periodos/4/',           False),
    ('03_nominas/04_boleta',            '/nominas/registros/46/',         True),
    ('03_nominas/05_emision_boletas',   '/nominas/boletas/',              True),
    ('03_nominas/06_workflow_mes',      '/nominas/workflow-mes/',         True),
    ('03_nominas/07_agente_ia',         '/nominas/agente/',               True),
    ('03_nominas/08_conceptos',         '/nominas/conceptos/',            False),
    ('03_nominas/09_calculadora',       '/nominas/calculadora/',          True),
    ('03_nominas/10_calc_cts',          '/nominas/calculadora/cts/',      True),
    ('03_nominas/11_calc_liquidacion',  '/nominas/calculadora/liquidacion/', True),
    ('03_nominas/12_ir5ta',             '/nominas/ir5ta/',                True),
    ('03_nominas/13_flujo_caja',        '/nominas/flujo-caja/',           True),
    ('03_nominas/14_comparativo',       '/nominas/comparativo/',          True),
    # ── Vacaciones ──
    ('04_vacaciones/01_panel',          '/vacaciones/',                   True),
    ('04_vacaciones/02_nueva',          '/vacaciones/nueva/',             True),
    ('04_vacaciones/03_permisos',       '/vacaciones/permisos/',          False),
    ('04_vacaciones/04_saldos',         '/vacaciones/saldos/',            False),
    # ── Préstamos / Viáticos ──
    ('05_prestamos/01_panel',           '/prestamos/',                    False),
    ('05_prestamos/02_nuevo',           '/prestamos/nuevo/',              True),
    ('05_prestamos/03_viaticos',        '/viaticos/',                     True),
    # ── Documentos ──
    ('06_documentos/01_legajo',         '/documentos/',                   True),
    ('06_documentos/02_faltantes',      '/documentos/faltantes/',         True),
    ('06_documentos/03_constancias',    '/documentos/constancias/',       True),
    ('06_documentos/04_firma',          '/documentos/firma/',             True),
    ('06_documentos/05_cese',           '/documentos/cese/',              True),
    # ── Reclutamiento ──
    ('07_reclutamiento/01_vacantes',    '/reclutamiento/',                True),
    ('07_reclutamiento/02_pipeline',    '/reclutamiento/pipeline/',       False),
    ('07_reclutamiento/03_funnel',      '/reclutamiento/funnel/',         True),
    ('07_reclutamiento/04_banco',       '/reclutamiento/banco-talento/',  True),
    ('07_reclutamiento/05_cv_express',  '/reclutamiento/cv/express/',     True),
    # ── Onboarding ──
    ('08_onboarding/01_dashboard',      '/onboarding/dashboard/',         True),
    ('08_onboarding/02_onboarding',     '/onboarding/',                   True),
    ('08_onboarding/03_offboarding',    '/onboarding/offboarding/',       True),
    # ── Evaluaciones ──
    ('09_evaluaciones/01_dashboard',    '/evaluaciones/dashboard/',       True),
    ('09_evaluaciones/02_ninebox',      '/evaluaciones/ninebox/',         True),
    ('09_evaluaciones/03_comparativa',  '/evaluaciones/comparativa/',     True),
    ('09_evaluaciones/04_okrs',         '/evaluaciones/okrs/',            True),
    # ── Capacitaciones ──
    ('10_capacitaciones/01_panel',      '/capacitaciones/',               True),
    ('10_capacitaciones/02_gastro',     '/capacitaciones/gastro/',        True),
    # ── Disciplinaria ──
    ('11_disciplinaria/01_dashboard',   '/disciplinaria/dashboard/',      True),
    ('11_disciplinaria/02_medidas',     '/disciplinaria/',               False),
    ('11_disciplinaria/03_nueva',       '/disciplinaria/nueva/',          True),
    # ── Encuestas ──
    ('12_encuestas/01_panel',           '/encuestas/',                    True),
    # ── Comunicaciones ──
    ('13_comunicaciones/01_notif',      '/comunicaciones/',               True),
    ('13_comunicaciones/02_comunicados','/comunicaciones/comunicados/',   True),
    # ── Salarios ──
    ('14_salarios/01_bandas',           '/salarios/bandas/',              True),
    ('14_salarios/02_grafico',          '/salarios/bandas/grafico/',      True),
    # ── Analytics / Ejecutivo ──
    ('15_analytics/01_ejecutivo',       '/sistema/dashboard/ejecutivo/',  True),
    ('15_analytics/02_analytics',       '/analytics/',                    True),
    ('15_analytics/03_predictivo',      '/analytics/predictive/',         True),
    ('15_analytics/04_grupo_pulse',     '/empresas/pulse/',               True),
]


async def main():
    results = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(channel='chrome', headless=True)
        ctx = await browser.new_context(viewport={'width': 1440, 'height': 1000})
        await ctx.add_cookies([{'name': 'sessionid', 'value': SK,
                                'domain': 'localhost', 'path': '/'}])
        page = await ctx.new_page()
        for rel, url, full in PAGES:
            path = os.path.join(OUT, rel + '.png')
            os.makedirs(os.path.dirname(path), exist_ok=True)
            try:
                await page.goto(BASE + url, wait_until='networkidle', timeout=25000)
                await page.wait_for_timeout(800)
                # Viewport fijo (above-the-fold): capturas uniformes y limpias
                # para el manual. full_page produce imágenes gigantes en páginas
                # con tablas/grids largos.
                await page.screenshot(path=path, full_page=False)
                results.append(f'  OK  {rel:40} {url}')
            except Exception as e:
                results.append(f'  ERR {rel:40} {url}  {type(e).__name__}: {str(e)[:50]}')
        await browser.close()
    print('\n'.join(results))
    ok = len([r for r in results if r.strip().startswith('OK')])
    print(f'\n{ok}/{len(PAGES)} capturas en {OUT}/')


asyncio.run(main())
