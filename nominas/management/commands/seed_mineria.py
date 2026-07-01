"""
Management command: seed_mineria

Siembra (idempotente) los conceptos del régimen minero:
  - FCJMMS (descuento 0.5% del trabajador, Ley 29741)
  - Nivelación Ingreso Mínimo Minero (RMV+25%, D.S. 030-89-TR)
  - Bonos de convenio: altitud, socavón/subsuelo, profundidad, riesgo
    (remunerativos / afectos)
  - Alimentación, hospedaje, movilidad (condición de trabajo / no remunerativos)

Uso: python manage.py seed_mineria

NOTA: los `codigo_plame` quedan en blanco — mapear contra la tabla SUNAT/PLAME.
"""
from django.core.management.base import BaseCommand


def _c(codigo, nombre, categoria, tipo, orden, *, subtipo='REMUNERATIVO',
       computable=False, cts=False, gratif=False):
    return dict(
        codigo=codigo, nombre=nombre, categoria=categoria, tipo=tipo, orden=orden,
        subtipo=subtipo, formula='MANUAL',
        afecto_essalud=computable, afecto_afp=computable, afecto_onp=computable,
        afecto_renta=computable, afecto_cts=cts, afecto_gratif=gratif,
    )


CONCEPTOS_MIN = [
    # ── Afectos (base computable) ──
    _c('min-imm-nivelacion', 'Nivelación Ingreso Mínimo Minero', 'SUELDO', 'INGRESO', 10,
       computable=True, cts=True, gratif=True),
    _c('min-bono-altitud', 'Bonificación por Altitud (minería)', 'BONIFICACION', 'INGRESO', 20,
       computable=True),
    _c('min-bono-socavon', 'Bonificación por Trabajo en Socavón/Subsuelo', 'BONIFICACION', 'INGRESO', 21,
       computable=True),
    _c('min-bono-profundidad', 'Bonificación por Profundidad', 'BONIFICACION', 'INGRESO', 22,
       computable=True),
    _c('min-bono-riesgo', 'Bonificación por Riesgo (minería)', 'BONIFICACION', 'INGRESO', 23,
       computable=True),
    # ── No remunerativos (condición de trabajo, D.S. 014-92-EM) ──
    _c('min-alimentacion', 'Alimentación (condición de trabajo)', 'ALIMENTACION', 'INGRESO', 30,
       subtipo='NO_REMUNERATIVO'),
    _c('min-hospedaje', 'Vivienda / Hospedaje (condición de trabajo)', 'OTROS_ING', 'INGRESO', 31,
       subtipo='NO_REMUNERATIVO'),
    _c('min-movilidad', 'Movilidad (minería)', 'MOVILIDAD', 'INGRESO', 32,
       subtipo='NO_REMUNERATIVO'),
    # ── Descuento ──
    _c('min-fcjmms', 'FCJMMS — Aporte trabajador 0.5% (Ley 29741)', 'DESCUENTO', 'DESCUENTO', 60),
]


class Command(BaseCommand):
    help = 'Siembra los conceptos del régimen minero (idempotente).'

    def handle(self, *args, **opts):
        from nominas.models import ConceptoRemunerativo
        n = 0
        for c in CONCEPTOS_MIN:
            defaults = {k: v for k, v in c.items() if k != 'codigo'}
            defaults['es_sistema'] = True
            defaults['activo'] = True
            ConceptoRemunerativo.objects.update_or_create(codigo=c['codigo'], defaults=defaults)
            n += 1
        self.stdout.write(self.style.SUCCESS(f'Conceptos minería: {n}.'))
