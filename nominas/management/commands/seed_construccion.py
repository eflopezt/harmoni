"""
Management command: seed_construccion

Siembra (idempotente) los datos del régimen de construcción civil:
  - JornalConstruccion: jornales básicos + BUC + bono altura por categoría
    (CAPECO-FTCCP 2026, R.M. 197-2025-TR), vigencia desde 2026-06-01.
  - ConceptoRemunerativo: conceptos propios del régimen (jornal, dominical,
    BUC, BAE, altura, CTS-CC, gratificación-CC, asignación escolar,
    compensación vacacional, CONAFOVICER).

Uso:
  python manage.py seed_construccion
  python manage.py seed_construccion --reset   # recrea los jornales 2026

NOTA: los `codigo_plame` quedan en blanco a propósito — deben mapearse contra la
tabla oficial SUNAT/PLAME antes de exportar la planilla.
"""
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand


# categoria: (jornal_diario, buc_pct, bono_altura_pct)
JORNALES_2026 = {
    'OPERARIO': (Decimal('87.30'), Decimal('32'), Decimal('8')),
    'OFICIAL':  (Decimal('68.50'), Decimal('30'), Decimal('8')),
    'PEON':     (Decimal('61.65'), Decimal('30'), Decimal('8')),
}
VIGENCIA_2026 = date(2026, 6, 1)  # convención CAPECO-FTCCP 2026 (jun 2026–may 2027)

# Afectaciones (verificadas contra boleta real + CAPECO-FTCCP; ver
# nominas/construccion.py::CODIGOS_COMPUTABLES).
#   computable = afecto a ESSALUD / AFP / ONP / SCTR (entra a la base computable)
#   cts / gratif = afecto a CTS / gratificación
#   renta = afecto a IR 5ta (sin ser computable para aportes)
def _c(codigo, nombre, categoria, tipo, orden, *, subtipo='REMUNERATIVO',
       computable=False, cts=False, gratif=False, renta=False):
    return dict(
        codigo=codigo, nombre=nombre, categoria=categoria, tipo=tipo, orden=orden,
        subtipo=subtipo, formula='MANUAL',
        afecto_essalud=computable, afecto_afp=computable, afecto_onp=computable,
        afecto_renta=(computable or renta), afecto_cts=cts, afecto_gratif=gratif,
    )


CONCEPTOS_CC = [
    # ── Afectos a la base computable (ESSALUD/AFP/ONP/SCTR) ──
    _c('cc-jornal-basico', 'Jornal Básico (Construcción)', 'SUELDO', 'INGRESO', 10,
       computable=True, cts=True, gratif=True),
    _c('cc-dominical', 'Dominical (Construcción)', 'SUELDO', 'INGRESO', 11,
       computable=True),
    _c('cc-hhee-60', 'Horas Extra 60% (Construcción)', 'SUELDO', 'INGRESO', 20,
       computable=True),
    _c('cc-hhee-100', 'Horas Extra 100% (Construcción)', 'SUELDO', 'INGRESO', 21,
       computable=True),
    _c('cc-hhee-100-dom', 'Horas Extra 100% Dominical (Construcción)', 'SUELDO', 'INGRESO', 22,
       computable=True),
    _c('cc-buc', 'BUC — Bonificación Unificada de Construcción', 'BONIFICACION', 'INGRESO', 12,
       computable=True),
    _c('cc-bae', 'BAE — Bonificación por Alta Especialización', 'BONIFICACION', 'INGRESO', 13,
       computable=True),
    _c('cc-bono-altura', 'Bono por Altura (Construcción)', 'BONIFICACION', 'INGRESO', 14,
       computable=True),
    _c('cc-bono-altitud', 'Bonificación por Altitud', 'BONIFICACION', 'INGRESO', 15,
       computable=True),
    _c('cc-comp-vacacional', 'Compensación Vacacional (Construcción)', 'SUELDO', 'INGRESO', 16,
       computable=True),
    # ── NO computables ──
    _c('cc-movilidad', 'Movilidad Acumulada (Construcción)', 'MOVILIDAD', 'INGRESO', 30,
       subtipo='NO_REMUNERATIVO'),
    _c('cc-gratif-julio', 'Gratificación (Construcción)', 'GRATIFICACION', 'INGRESO', 40,
       renta=True),                              # inafecta a ESSALUD/AFP/ONP (Ley 29351)
    _c('cc-bonif-extraord', 'Bonif. Extraordinaria Ley 29351 (9%)', 'BONIFICACION', 'INGRESO', 41,
       renta=True),
    _c('cc-cts', 'CTS 15% (Construcción)', 'PROVISION', 'INGRESO', 50,
       subtipo='PROVISION'),                     # beneficio social, inafecto a todo
    _c('cc-asig-escolar', 'Asignación Escolar (Construcción)', 'FAMILIAR', 'INGRESO', 17,
       subtipo='NO_REMUNERATIVO'),
    # ── Descuento ──
    _c('cc-conafovicer', 'CONAFOVICER (2%)', 'DESCUENTO', 'DESCUENTO', 60),
]


class Command(BaseCommand):
    help = 'Siembra jornales CAPECO 2026 y conceptos del régimen de construcción civil.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Borra y recrea los jornales de la vigencia 2026.')

    def handle(self, *args, **opts):
        from nominas.models import JornalConstruccion, ConceptoRemunerativo

        if opts['reset']:
            n = JornalConstruccion.objects.filter(vigencia_desde=VIGENCIA_2026).delete()[0]
            self.stdout.write(self.style.WARNING(f'Borrados {n} jornales de {VIGENCIA_2026}.'))

        # Jornales
        jn = 0
        for categoria, (jornal, buc, altura) in JORNALES_2026.items():
            _, created = JornalConstruccion.objects.update_or_create(
                categoria=categoria, vigencia_desde=VIGENCIA_2026,
                defaults=dict(jornal_diario=jornal, buc_pct=buc,
                              bono_altura_pct=altura, fuente='CAPECO-FTCCP 2026 (R.M. 197-2025-TR)'),
            )
            jn += 1
        self.stdout.write(self.style.SUCCESS(f'Jornales 2026: {jn} categorías.'))

        # Conceptos
        cn = 0
        for c in CONCEPTOS_CC:
            defaults = {k: v for k, v in c.items() if k != 'codigo'}
            defaults['es_sistema'] = True
            defaults['activo'] = True
            ConceptoRemunerativo.objects.update_or_create(codigo=c['codigo'], defaults=defaults)
            cn += 1
        self.stdout.write(self.style.SUCCESS(f'Conceptos construcción: {cn}.'))
