"""
Patch del sidebar (base.html) para ocultar enlaces que no aplican a Plan Starter.

Operaciones:
1. Wrappear sección MI PORTAL completa con {% if not es_plan_starter %}
2. Wrappear sección COMUNICACIONES completa
3. Wrappear sección ANALYTICS completa
4. Wrappear sección DISCIPLINARIA completa
5. Wrappear links sueltos: organigrama_erp, roster_matricial, calendario_view,
   contratos_panel, asistencia_solicitudes_he, integraciones_panel
6. Insertar badge "Plan Starter" en sidebar header
7. Insertar banner amarillo arriba del main para users Starter

Idempotente: detecta si ya se aplicaron los wrappers (marker `starter-gate-*`)
y no los duplica.

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


def insert_starter_badge(content):
    """Inserta badge 'Plan Starter' debajo del sidebar-brand-subtitle."""
    if 'starter-plan-badge-marker' in content:
        return content, False
    needle = '{% else %}Sistema RRHH{% endif %}\n                </div>\n            </div>\n        </a>'
    if needle not in content:
        return content, False
    inject = needle + '''
        {% if es_plan_starter %}
        <div class="px-3 mt-2" data-marker="starter-plan-badge-marker">
            <a href="{% url 'upgrade_plan' %}" style="display:inline-flex;align-items:center;gap:5px;background:linear-gradient(135deg,#94a3b8,#64748b);color:#fff;padding:3px 10px;border-radius:10px;font-size:.62rem;font-weight:700;letter-spacing:.05em;text-transform:uppercase;text-decoration:none;">
                <i class="fas fa-circle" style="font-size:.45rem;"></i>
                Plan Starter
                <i class="fas fa-arrow-up" style="font-size:.55rem;opacity:.7;margin-left:2px;"></i>
            </a>
        </div>
        {% endif %}'''
    return content.replace(needle, inject, 1), True


def insert_starter_banner(content):
    """Banner amarillo arriba del <main class='harmoni-content'>."""
    if 'starter-topbar-banner' in content:
        return content, False
    needle = '    <main class="harmoni-content">'
    if needle not in content:
        return content, False
    inject = '''    {% if es_plan_starter %}
    <div data-marker="starter-topbar-banner" style="background:linear-gradient(90deg,#fef3c7,#fde68a);border-bottom:1px solid #fcd34d;padding:8px 16px;display:flex;align-items:center;justify-content:space-between;gap:12px;font-size:.82rem;">
        <div style="color:#78350f;">
            <i class="fas fa-info-circle me-1"></i>
            <strong>Plan Starter</strong> — hasta 30 colaboradores. Algunas funciones avanzadas no están disponibles en este plan.
        </div>
        <a href="{% url 'upgrade_plan' %}" style="background:#0f766e;color:#fff;padding:5px 14px;border-radius:8px;font-weight:600;font-size:.78rem;text-decoration:none;flex-shrink:0;">
            Ver planes superiores →
        </a>
    </div>
    {% endif %}
''' + needle
    return content.replace(needle, inject, 1), True


def main(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    changes = []

    if not already_patched(content):
        # Secciones enteras (solo en primera aplicación)
        for section in (
            '<!-- ══ MI PORTAL ══',
            '<!-- ══ COMUNICACIONES ══',
            '<!-- ══ ANALYTICS ══',
            '<!-- ══ DISCIPLINARIA ══',
        ):
            content, ok = wrap_section(content, section)
            changes.append((section, ok))
    else:
        print(f"⚠ Secciones ya wrappeadas — saltando (idempotente)")

    # Links sueltos (saltar si ya está patched para no duplicar)
    if not already_patched(content):
        pass  # ya patched
    for url_name in (
        'organigrama_erp',
        'roster_matricial',
        'calendario_view',
        'contratos_panel',
        'asistencia_solicitudes_he',
        'integraciones_panel',
        'mi_portal_disciplinaria',
        'evaluacion_360_dashboard',
    ):
        content, ok = wrap_link(content, url_name)
        changes.append((url_name, ok))

    # Badge sidebar + banner topbar (idempotentes individualmente)
    content, ok = insert_starter_badge(content)
    changes.append(('starter-plan-badge', ok))
    content, ok = insert_starter_banner(content)
    changes.append(('starter-topbar-banner', ok))

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
