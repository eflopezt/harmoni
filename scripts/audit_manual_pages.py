"""Audita la 'riqueza de datos' de cada página del manual.
Para cada URL reporta: estados vacíos ('No hay'/'Sin datos'), nº de KPIs en 0,
y nº de filas de tabla. Sirve para detectar pantallas flacas antes de capturar.

Uso: .venv/Scripts/python.exe scripts/audit_manual_pages.py <SESSION_KEY> [all]
  'all' como 2º arg → fija empresa consolidada antes de auditar.
"""
import sys
import re
import asyncio
from playwright.async_api import async_playwright

SK = sys.argv[1] if len(sys.argv) > 1 else ''
CONSOLIDADO = len(sys.argv) > 2 and sys.argv[2] == 'all'
BASE = 'http://localhost:8001'

# (etiqueta, url) — mismas páginas que el manual
PAGES = [
    ('inicio', '/'),
    ('personal_lista', '/personal/'), ('personal_detalle', '/personal/212/'),
    ('contratar_express', '/personal/express/'), ('contratos', '/contratos/'),
    ('organigrama', '/organigrama/'), ('roster', '/roster/matricial/'),
    ('reportes_rrhh', '/reportes/'),
    ('asis_dashboard', '/asistencia/'), ('asis_kpis', '/asistencia/kpis/'),
    ('asis_matricial', '/asistencia/calendario/'), ('asis_papeletas', '/asistencia/papeletas/'),
    ('asis_banco_horas', '/asistencia/banco-horas/'), ('asis_briefing', '/asistencia/briefing/'),
    ('asis_export', '/asistencia/exportar/'), ('asis_import', '/asistencia/importar/'),
    ('nom_periodos', '/nominas/'), ('nom_nuevo', '/nominas/periodos/nuevo/'),
    ('nom_detalle', '/nominas/periodos/4/'), ('nom_boleta', '/nominas/registros/46/'),
    ('nom_emision', '/nominas/boletas/'), ('nom_workflow', '/nominas/workflow-mes/'),
    ('nom_agente', '/nominas/agente/'), ('nom_conceptos', '/nominas/conceptos/'),
    ('nom_calc', '/nominas/calculadora/'), ('nom_calc_cts', '/nominas/calculadora/cts/'),
    ('nom_calc_liq', '/nominas/calculadora/liquidacion/'), ('nom_ir5ta', '/nominas/ir5ta/'),
    ('nom_flujo', '/nominas/flujo-caja/'), ('nom_comparativo', '/nominas/comparativo/'),
    ('vac_panel', '/vacaciones/'), ('vac_nueva', '/vacaciones/nueva/'),
    ('vac_permisos', '/vacaciones/permisos/'), ('vac_saldos', '/vacaciones/saldos/'),
    ('pre_panel', '/prestamos/'), ('pre_nuevo', '/prestamos/nuevo/'), ('viaticos', '/viaticos/'),
    ('doc_legajo', '/documentos/'), ('doc_faltantes', '/documentos/faltantes/'),
    ('doc_constancias', '/documentos/constancias/'), ('doc_firma', '/documentos/firma/'),
    ('doc_cese', '/documentos/cese/'),
    ('rec_vacantes', '/reclutamiento/'), ('rec_pipeline', '/reclutamiento/pipeline/'),
    ('rec_funnel', '/reclutamiento/funnel/'), ('rec_banco', '/reclutamiento/banco-talento/'),
    ('rec_cv', '/reclutamiento/cv/express/'),
    ('onb_dashboard', '/onboarding/dashboard/'), ('onb_onboarding', '/onboarding/'),
    ('onb_offboarding', '/onboarding/offboarding/'),
    ('eval_dashboard', '/evaluaciones/dashboard/'), ('eval_ninebox', '/evaluaciones/ninebox/'),
    ('eval_comparativa', '/evaluaciones/comparativa/'), ('eval_okrs', '/evaluaciones/okrs/'),
    ('cap_panel', '/capacitaciones/'), ('cap_gastro', '/capacitaciones/gastro/'),
    ('dis_dashboard', '/disciplinaria/dashboard/'), ('dis_medidas', '/disciplinaria/'),
    ('dis_nueva', '/disciplinaria/nueva/'),
    ('enc_panel', '/encuestas/'),
    ('com_notif', '/comunicaciones/'), ('com_comunicados', '/comunicaciones/comunicados/'),
    ('sal_bandas', '/salarios/bandas/'), ('sal_grafico', '/salarios/bandas/grafico/'),
    ('an_ejecutivo', '/sistema/dashboard/ejecutivo/'), ('an_analytics', '/analytics/'),
    ('an_predictivo', '/analytics/predictive/'), ('an_pulse', '/empresas/pulse/'),
]

EMPTY_RE = re.compile(r'no hay|sin datos|sin registros|vac[íi]o|a[úu]n no|0 resultados|no se encontr', re.I)


async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(channel='chrome', headless=True)
        c = await b.new_context(viewport={'width': 1440, 'height': 1000})
        await c.add_cookies([{'name': 'sessionid', 'value': SK, 'domain': 'localhost', 'path': '/'}])
        pg = await c.new_page()
        if False and CONSOLIDADO:
            # fijar empresa consolidada
            await pg.goto(BASE + '/empresas/seleccionar/?empresa_id=all', wait_until='networkidle', timeout=15000)
        flacos = []
        for label, url in PAGES:
            try:
                await pg.goto(BASE + url, wait_until='networkidle', timeout=25000)
                await pg.wait_for_timeout(400)
                text = (await pg.inner_text('body'))
                empties = len(EMPTY_RE.findall(text))
                # KPIs en 0: números aislados '0' en cards de stat
                zeros = len(re.findall(r'(?<![\d.,])0(?![\d.,%])', text))
                rows = await pg.eval_on_selector_all('table tbody tr', 'els => els.length')
                thin = empties >= 2 or (rows == 0 and 'form' not in url and 'nuevo' not in url and 'crear' not in url)
                mark = 'FLACO' if thin else 'ok'
                line = f'  [{mark:5}] {label:20} empties={empties} zeros={zeros} rows={rows}'
                if thin:
                    flacos.append(line)
                print(line)
            except Exception as e:
                print(f'  [ERR  ] {label:20} {type(e).__name__}: {str(e)[:50]}')
        await b.close()
        print(f'\n=== FLACOS: {len(flacos)} ===')
        for f in flacos:
            print(f)


asyncio.run(main())
