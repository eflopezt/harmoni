"""Detector heurístico de módulos potencialmente muertos.

Construye un grafo de imports estáticos (ast) y reporta los archivos .py que
NO son importados por ningún otro archivo del proyecto. Ignora migrations,
tests, settings, scripts standalone, y archivos especiales (urls, models, etc.)

Heurística — puede tener falsos positivos:
- Módulos cargados dinámicamente (importlib, __import__) no se ven
- Comandos de management se cargan por convención, no por import explícito
- Tareas de Celery registradas vía decorator se cargan al iniciar workers

Uso:
    python scripts/find_dead_code.py
"""
from __future__ import annotations

import ast
import os
from collections import defaultdict

EXCLUDE_DIRS = {'.venv', '.git', '.claude', '__pycache__', 'snapshots',
                'presentacion', 'node_modules', 'staticfiles', 'media'}
EXCLUDE_BASENAMES = {
    '__init__.py', 'manage.py', 'conftest.py', 'wsgi.py', 'asgi.py',
    'urls.py', 'apps.py', 'admin.py', 'models.py', 'forms.py',
    'tasks.py', 'signals.py', 'views.py', 'serializers.py',
    'api_urls.py', 'api_views.py', 'api_serializers.py',
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
    """Set de todos los módulos referenciados por algún import."""
    referenced: set[str] = set()
    for mod, p in modules.items():
        try:
            with open(p, encoding='utf-8', errors='ignore') as fh:
                tree = ast.parse(fh.read())
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                _add_module_chain(referenced, node.module)
            elif isinstance(node, ast.Import):
                for n in node.names:
                    _add_module_chain(referenced, n.name)
    return referenced


def _add_module_chain(referenced: set[str], dotted: str) -> None:
    """`foo.bar.baz` → agrega foo, foo.bar, foo.bar.baz."""
    parts = dotted.split('.')
    for i in range(1, len(parts) + 1):
        referenced.add('.'.join(parts[:i]))
    # También leaf solo (común con `from x import y`)
    referenced.add(parts[-1])


def _has_main_block(path: str) -> bool:
    """Verifica si el archivo tiene `if __name__ == '__main__':` (script standalone)."""
    try:
        with open(path, encoding='utf-8', errors='ignore') as fh:
            return "__name__" in fh.read() and "__main__" in open(path, encoding='utf-8', errors='ignore').read()
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
        if p.startswith('docs/') or p.startswith('scripts/'):
            continue
        if _has_main_block(p):
            continue
        # ¿Es importado por alguien?
        leaf = mod.rsplit('.', 1)[-1]
        if mod in referenced or leaf in referenced:
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
