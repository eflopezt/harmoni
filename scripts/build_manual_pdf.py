"""Convierte docs/manual/MANUAL.md a un PDF con portada y estilos de impresión.
Markdown -> HTML -> PDF (Playwright + Chrome del sistema).

Uso: .venv/Scripts/python.exe scripts/build_manual_pdf.py
"""
import os
import asyncio
import markdown
from playwright.async_api import async_playwright

ROOT = os.path.join('docs', 'manual')
MD = os.path.join(ROOT, 'MANUAL.md')
HTML = os.path.join(ROOT, 'MANUAL.html')
PDF = os.path.join(ROOT, 'MANUAL.pdf')

CSS = """
@page { size: A4; margin: 18mm 16mm; }
* { box-sizing: border-box; }
body { font-family: -apple-system, 'Segoe UI', Roboto, Arial, sans-serif;
       color: #1f2937; line-height: 1.5; font-size: 11pt; }
.cover { text-align: center; padding-top: 28vh; page-break-after: always; }
.cover h1 { font-size: 30pt; color: #0f766e; margin: 0 0 8px; }
.cover .sub { font-size: 13pt; color: #6b7280; }
.cover .meta { margin-top: 40px; font-size: 10pt; color: #9ca3af; }
h1 { color: #0f766e; font-size: 20pt; }
h2 { color: #0f766e; font-size: 16pt; border-bottom: 2px solid #0f766e;
     padding-bottom: 4px; margin-top: 22px; page-break-before: always; }
h3 { color: #115e59; font-size: 12.5pt; margin-top: 16px; }
h2 + p, h3 + p { margin-top: 4px; }
img { max-width: 100%; height: auto; border: 1px solid #e5e7eb; border-radius: 6px;
      margin: 8px 0 14px; box-shadow: 0 1px 4px rgba(0,0,0,.08);
      page-break-inside: avoid; }
table { border-collapse: collapse; width: 100%; font-size: 10pt; }
th, td { border: 1px solid #e5e7eb; padding: 5px 8px; text-align: left; }
th { background: #f0fdfa; }
code { background: #f3f4f6; padding: 1px 5px; border-radius: 4px; font-size: 9.5pt; }
blockquote { border-left: 4px solid #0f766e; background: #f0fdfa; margin: 12px 0;
             padding: 8px 14px; color: #374151; }
a { color: #0f766e; text-decoration: none; }
hr { display: none; }
/* el primer h1 (título del doc) lo ocultamos: usamos portada propia */
"""


def build_html():
    md_text = open(MD, encoding='utf-8').read()
    body = markdown.markdown(md_text, extensions=['tables', 'toc', 'fenced_code', 'sane_lists'])
    cover = (
        '<div class="cover">'
        '<h1>Manual de Usuario</h1>'
        '<div class="sub">Harmoni ERP — Gestión de RR.HH. y Planillas</div>'
        '<div class="meta">Perú · D.Leg. 728 / 727 · Versión 2026-05-29</div>'
        '</div>'
    )
    html = (
        f'<!doctype html><html lang="es"><head><meta charset="utf-8">'
        f'<style>{CSS}</style></head><body>{cover}{body}</body></html>'
    )
    open(HTML, 'w', encoding='utf-8').write(html)
    return os.path.abspath(HTML)


async def to_pdf(html_path):
    async with async_playwright() as p:
        b = await p.chromium.launch(channel='chrome', headless=True)
        pg = await (await b.new_context()).new_page()
        await pg.goto('file:///' + html_path.replace('\\', '/'), wait_until='networkidle')
        await pg.pdf(path=PDF, format='A4', print_background=True,
                     margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'})
        await b.close()


html_path = build_html()
asyncio.run(to_pdf(html_path))
size = os.path.getsize(PDF) / 1024 / 1024
print(f'PDF generado: {PDF}  ({size:.1f} MB)')
