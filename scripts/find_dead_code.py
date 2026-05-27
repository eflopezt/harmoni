"""Detector heurístico de módulos potencialmente muertos.

Construye un grafo de imports estáticos (ast) y reporta los archivos .py que
NO son importados por ningún otro archivo del proyecto. Ignora migrations,
tests, settings, scripts standalone, y archivos especiales (urls, models, etc.)

Maneja:
- Imports absolutos: `import foo.bar`, `from foo.bar import X`
- Imports relativos: `from . import X`, `from .foo import X`, `from ..bar import X`
- Imports dinámicos: `__import__('foo.bar')`, `importlib.import_module('foo.bar')`

Limitaciones (falsos positivos posibles):
- Middlewares y AUTH_BACKENDS referenciados por string en settings.py
- Templatetags cargados por `{% load X %}` en templates
- Vistas Django referenciadas por string en url patterns (parcialmente cubierto
  con detección de __import__, pero `path(..., 'foo.views.bar')` no se detecta)
- Tareas Celery autodiscovered

Uso:
    python scripts/find_dead_code.py
"""
from __future__ import annotations

import ast
import os
from collections import defaultdict

EXCLUDE_DIRS = {'.venv', '.git', '.claude', '__pycache__', 'snapshots',
                'presentacion', 'node_modules', 'staticfiles', 'media',
                'static',         # JS/CSS/imágenes con .py incrustado son raros
                'formats',        # Django i18n format modules (FORMAT_MODULE_PATH)
                }
EXCLUDE_BASENAMES = {
    '__init__.py', 'manage.py', 'conftest.py', 'wsgi.py', 'asgi.py',
    'urls.py', 'apps.py', 'admin.py', 'models.py', 'forms.py',
    'tasks.py', 'signals.py', 'views.py', 'serializers.py',
    'api_urls.py', 'api_views.py', 'api_serializers.py',
    'celery.py',              # cargado por string en settings
    'context_processors.py',  # cargado por TEMPLATES.OPTIONS.context_processors
}
EXCLUDE_PREFIXES = ('test_', 'tests_', 'fix_', 'populate_', 'rebuild_',
                    'analyze_', 'setup_', 'create_', 'capture_', 'crear_',
                    'import_', 'seed_', 'seed', 'verify_', 'verificar_')


def collect_modules() -> dict[str, str]:
    """mod_name -> file_path"""
    modules: dict[str, str] = {}
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if not f.endswith('.py'):
                continue
            p = os.path.join(root, f).replace('\\', '/').lstrip('./')
            mod = p.replace('/', '.').replace('.py', '')
            modules[mod] = p
    return modules


def collect_imports(modules: dict[str, str]) -> set[str]:
    """Set de todos los módulos referenciados por algún import.

    Maneja:
    - Imports absolutos: `import foo.bar`, `from foo.bar import X`
    - Imports relativos: `from . import X`, `from .foo import X`, `from ..bar import X`
    - Imports dinámicos: `__import__('foo.bar')`, `importlib.import_module('foo.bar')`
    """
    referenced: set[str] = set()
    for mod, p in modules.items():
        try:
            with open(p, encoding='utf-8', errors='ignore') as fh:
                tree = ast.parse(fh.read())
        except Exception:
            continue

        # Paquete del archivo actual: para resolver imports relativos.
        # `foo/bar/baz.py` → paquete = 'foo.bar'
        pkg = mod.rsplit('.', 1)[0] if '.' in mod else ''
        pkg_parts = pkg.split('.') if pkg else []

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                level = node.level or 0
                if level == 0 and node.module:
                    # Absoluto: from foo.bar import X
                    _add_module_chain(referenced, node.module)
                    for n in node.names:
                        _add_module_chain(referenced, f'{node.module}.{n.name}')
                elif level >= 1 and pkg_parts:
                    # Relativo: from .foo import X / from . import X / from ..bar
                    cut = len(pkg_parts) - level + 1
                    if cut < 0:
                        continue
                    base = '.'.join(pkg_parts[:cut])
                    if node.module:
                        target = f'{base}.{node.module}' if base else node.module
                        _add_module_chain(referenced, target)
                        for n in node.names:
                            _add_module_chain(referenced, f'{target}.{n.name}')
                    else:
                        # from . import X → X es módulo dentro del paquete actual
                        for n in node.names:
                            full = f'{base}.{n.name}' if base else n.name
                            _add_module_chain(referenced, full)
            elif isinstance(node, ast.Import):
                for n in node.names:
                    _add_module_chain(referenced, n.name)
            elif isinstance(node, ast.Call):
                # Imports dinámicos: __import__('foo.bar', fromlist=[...])
                # e importlib.import_module('foo.bar')
                func_name = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                if func_name in ('__import__', 'import_module') and node.args:
                    first = node.args[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        _add_module_chain(referenced, first.value)
    return referenced


def _add_module_chain(referenced: set[str], dotted: str) -> None:
    """`foo.bar.baz` → agrega foo, foo.bar, foo.bar.baz.

    Nota: NO agregamos el leaf solo (`baz`). Eso generaba falsos negativos:
    `from django.views.decorators.http import require_GET` ponía `decorators`
    en el set, y luego un módulo no-relacionado `personal.decorators.py` se
    consideraba referenciado por coincidencia de leaf.
    """
    parts = dotted.split('.')
    for i in range(1, len(parts) + 1):
        referenced.add('.'.join(parts[:i]))


def _has_main_block(path: str) -> bool:
    """Verifica si el archivo tiene `if __name__ == '__main__':` (script standalone)."""
    try:
        with open(path, encoding='utf-8', errors='ignore') as fh:
            src = fh.read()
        return 'if __name__' in src and '__main__' in src
    except Exception:
        return False


def find_dead(modules: dict[str, str], referenced: set[str]) -> list[tuple[int, str, str]]:
    """Lista de (LOC, mod_name, path) potencialmente muertos."""
    dead: list[tuple[int, str, str]] = []
    for mod, p in modules.items():
        bn = os.path.basename(p)
        if bn in EXCLUDE_BASENAMES:
            continue
        if '/migrations/' in p or '/tests/' in p or '/settings/' in p or '/management/commands/' in p:
            continue
        if bn.startswith(EXCLUDE_PREFIXES):
            continue
        # Vistas Django: se cargan vía urls.py con __import__ dinámico, no aparece
        # en el grafo de imports estáticos. Falsos positivos garantizados.
        if bn.startswith('views_') or bn == 'views.py':
            continue
        # Scripts standalone — entry points manuales, no se importan
        if p.startswith(('docs/', 'scripts/', 'deploy/')):
            continue
        if _has_main_block(p):
            continue
        # Middlewares: cargados por string en `MIDDLEWARE` setting.
        if bn.startswith('middleware') or bn == 'middleware.py':
            continue
        # Templatetags: cargados por `{% load X %}` en templates.
        if '/templatetags/' in p:
            continue
        # URL configs adicionales: cargados por `include('foo.urls_bar')` en config/urls.py
        if bn.startswith('urls_') or bn == 'urls.py':
            continue
        # Context processors adicionales (algunos proyectos los nombran *_ctx).
        if 'context_processor' in bn:
            continue
        # ¿Es importado por alguien? Solo full path — leaf solo es ambiguo.
        if mod in referenced:
            continue
        try:
            with open(p, encoding='utf-8', errors='ignore') as fh:
                n = sum(1 for _ in fh)
        except Exception:
            n = 0
        dead.append((n, mod, p))
    dead.sort(reverse=True)
    return dead


def main() -> None:
    modules = collect_modules()
    referenced = collect_imports(modules)
    dead = find_dead(modules, referenced)
    print(f'Módulos no importados por nadie: {len(dead)}')
    print('Top 25 por LOC:')
    for n, mod, p in dead[:25]:
        print(f'  {n:>5}  {p}')


if __name__ == '__main__':
    main()
