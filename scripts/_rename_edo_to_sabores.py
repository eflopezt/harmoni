"""Rename EDO → Sabores del Sur en todo el repo (text-only, safe).

Reglas:
- Reemplazos largos primero (para no chocar con los cortos).
- Solo strings visibles + docstrings + comentarios + nombres comerciales.
- NO toca nombres de archivos, módulos Python, funciones, clases ni URLs internas
  (esos quedan con "edo" para no romper imports/rutas).
- NO toca rangos como "Toledo", "estado", "Modelo" (uso word boundaries en regex final).

Uso:
    python scripts/_rename_edo_to_sabores.py --dry-run
    python scripts/_rename_edo_to_sabores.py            # aplica
"""
import argparse
import re
import sys
from pathlib import Path

# Orden importa: del más largo al más corto.
REPLACEMENTS = [
    # Dominios/correos primero
    ('edosushi.pe', 'saboresdelsur.pe'),
    ('edopremium.pe', 'saboresdelsur.pe'),
    ('edoexpress.pe', 'saboresdelsur.pe'),
    ('edosushibar.pe', 'saboresdelsur.pe'),
    # Razones sociales / nombres comerciales (más largos primero)
    ('EDO Sushi Bar SAC', 'Sabores del Sur SAC'),
    ('EDO Sushi Bar', 'Sabores del Sur'),
    ('EDO Premium Miraflores', 'Sabores del Sur Premium Miraflores'),
    ('EDO Premium SAC', 'Sabores del Sur Premium SAC'),
    ('EDO Premium', 'Sabores del Sur Premium'),
    ('EDO Express (Dark Kitchen)', 'Sabores del Sur Express (Dark Kitchen)'),
    ('EDO Express SAC', 'Sabores del Sur Express SAC'),
    ('EDO Express', 'Sabores del Sur Express'),
    # Grupo
    ('Grupo EDO Premium', 'Grupo Sabores Premium'),
    ('Grupo EDO', 'Grupo Sabores'),
    ('grupo edo', 'grupo sabores'),
    # Marca corta (cuidado: word boundary para no tocar 'edo' en 'Toledo' etc.)
    # Solo cuando 'EDO' aparece como token visible en strings (mayúsculas).
]

# Reemplazo final de "EDO" como palabra completa (word boundary). Esto cubre
# textos sueltos tipo "demo de EDO" que quedaron. Cuidadoso: solo MAYÚSCULAS y
# limitado a contextos no-código (no aplica a EDO si está dentro de identificador).
WORD_EDO_PATTERN = re.compile(r'\bEDO\b')

EXCLUDE_DIRS = {'.git', '.venv', 'venv', '.claude', 'node_modules', '__pycache__',
                'staticfiles', 'media', 'htmlcov', '.pytest_cache'}

# Archivos a SALTAR completamente (binarios o el propio script).
SKIP_FILES = {
    'static/images/membrete/logo_14.b64',  # binario base64
    'scripts/_rename_edo_to_sabores.py',   # el propio script (no auto-modificar)
}

# Solo procesar estas extensiones.
INCLUDE_EXT = {'.py', '.html', '.md', '.txt', '.json', '.sh', '.yml', '.yaml',
               '.cfg', '.ini', '.conf', '.css', '.js'}


def should_process(p: Path, root: Path) -> bool:
    rel = p.relative_to(root).as_posix()
    if any(part in EXCLUDE_DIRS for part in p.parts):
        return False
    if rel in SKIP_FILES:
        return False
    if p.suffix.lower() not in INCLUDE_EXT:
        return False
    return True


def process_file(p: Path, dry_run: bool) -> tuple[int, int]:
    """Returns (replacements_done, file_modified_bool_as_int)."""
    try:
        original = p.read_text(encoding='utf-8')
    except (UnicodeDecodeError, PermissionError):
        return (0, 0)

    new = original
    total = 0
    for old, repl in REPLACEMENTS:
        cnt = new.count(old)
        if cnt:
            new = new.replace(old, repl)
            total += cnt

    # Word-boundary EDO → Sabores. Solo aplica si NO toca un nombre de archivo
    # ni un identificador snake_case (ej: 'seed_grupo_edo_premium').
    # Como ya hicimos los reemplazos arriba con frase, lo que queda son
    # menciones aisladas "EDO" en texto. Aplicamos solo en strings y docs.
    def _word_repl(match):
        return 'Sabores del Sur'

    new2, n_word = WORD_EDO_PATTERN.subn(_word_repl, new)
    new = new2
    total += n_word

    if new != original:
        if not dry_run:
            p.write_text(new, encoding='utf-8', newline='')
        return (total, 1)
    return (0, 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    files_changed = 0
    total_repls = 0

    for p in root.rglob('*'):
        if not p.is_file():
            continue
        if not should_process(p, root):
            continue
        n, modified = process_file(p, args.dry_run)
        if modified:
            files_changed += 1
            total_repls += n
            rel = p.relative_to(root)
            tag = '[DRY]' if args.dry_run else '[OK]'
            print(f'{tag} {rel} — {n} reemplazos')

    print(f'\n{"DRY-RUN — no se escribió" if args.dry_run else "Aplicado"}: '
          f'{files_changed} archivos, {total_repls} reemplazos.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
