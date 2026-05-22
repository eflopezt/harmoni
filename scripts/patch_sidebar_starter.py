"""
Patch del sidebar (base.html) para ocultar enlaces que no aplican a Plan Starter.

Operaciones:
1. Wrappear sección MI PORTAL completa con {% if not es_plan_starter %}
2. Wrappear sección COMUNICACIONES completa
3. Wrappear sección ANALYTICS completa
4. Wrappear links sueltos: organigrama_erp, roster_matricial, calendario_view,
   contratos_panel, asistencia_solicitudes_he, integraciones_panel
5. Wrappear sub-link mi_portal_disciplinaria

Idempotente: detecta si ya se aplicaron los wrappers y no los duplica.

Uso:
    python scripts/patch_sidebar_starter.py /opt/harmoni-demo/app/templates/base.html
"""
import re
import sys


MARKER_OPEN  = '{# starter-gate-open #}'
MARKER_CLOSE = '{# starter-gate-close #}'


def already_patched(content):
    return MARKER_OPEN in content


def wrap_section(content, section_marker_comment):
    """
    Encuentra `<!-- ══ X ══ -->` seguido del `<div class="nav-section"...>...</div>`
    correspondiente, y envuelve con {% if not es_plan_starter %}...{% endif %}.

    Se basa en que la sección termina antes del próximo `<!-- ══` o el último div.
    """
    # Buscar el comment marker
    idx = content.find(section_marker_comment)
    if idx == -1:
        return content, False

    # Buscar el siguiente comment marker (final del section a wrappear)
    next_marker_idx = content.find('<!-- ══', idx + 1)
    if next_marker_idx == -1:
        return content, False

    # Insertar el {% if %} antes del comment y el {% endif %} antes del próximo
    before     = content[:idx]
    body       = content[idx:next_marker_idx]
    after      = content[next_marker_idx:]
    wrapped    = (
        before
        + '{% if not es_plan_starter %}' + MARKER_OPEN + '\n            '
        + body
        + MARKER_CLOSE + '{% endif %}\n            '
        + after
    )
    return wrapped, True


def wrap_link(content, url_name):
    """
    Envuelve `<a href="{% url 'NAME' %}" ...>...</a>` con {% if not es_plan_starter %}.
    El </a> puede estar varias líneas después del <a>.
    """
    # Pattern: <a href="{% url 'NAME' %}" ... > ... </a>
    # Solo el primer match para evitar tocar links de otros contextos
    pattern = re.compile(
        r"(<a href=\"\{% url '" + re.escape(url_name) + r"' [^>]*?>.*?</a>)",
        re.DOTALL
    )
    match = pattern.search(content)
    if not match:
        return content, False

    # Verificar que no esté ya wrappeado
    snippet_start = max(0, match.start() - 60)
    if MARKER_OPEN in content[snippet_start:match.start()]:
        return content, False

    block = match.group(1)
    wrapped = (
        '{% if not es_plan_starter %}' + MARKER_OPEN
        + block
        + MARKER_CLOSE + '{% endif %}'
    )
    return content[:match.start()] + wrapped + content[match.end():], True


def main(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    if already_patched(content):
        print(f"⚠ {path} ya tiene patches aplicados — abortando para evitar duplicación")
        return

    changes = []

    # Secciones enteras
    for section in (
        '<!-- ══ MI PORTAL ══',
        '<!-- ══ COMUNICACIONES ══',
        '<!-- ══ ANALYTICS ══',
    ):
        content, ok = wrap_section(content, section)
        changes.append((section, ok))

    # Links sueltos
    for url_name in (
        'organigrama_erp',
        'roster_matricial',
        'calendario_view',
        'contratos_panel',
        'asistencia_solicitudes_he',
        'integraciones_panel',
        'mi_portal_disciplinaria',
        'evaluacion_360_dashboard',  # por si existe
    ):
        content, ok = wrap_link(content, url_name)
        changes.append((url_name, ok))

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✓ Patch aplicado a {path}")
    for name, ok in changes:
        marker = '✓' if ok else '✗ (not found, skipped)'
        print(f"  {marker} {name}")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Uso: python patch_sidebar_starter.py <ruta-a-base.html>")
        sys.exit(1)
    main(sys.argv[1])
