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


# Tablas de jornales por vigencia. Fuente: CAPECO-FTCCP.
# categoria: (jornal_diario, buc_pct, bono_altura_pct)
# TABLAS: (vigencia_desde, vigencia_hasta, fuente, {categoria: (...)})
VIGENCIA_2026 = date(2026, 1, 1)  # usado por el default de jornal_vigente
TABLAS_JORNAL = [
    # Vigente 01.01.2026 – 31.12.2026 (CAPECO-FTCCP 2026)
    (date(2026, 1, 1), date(2026, 12, 31), 'CAPECO-FTCCP 2026', {
        'OPERARIO': (Decimal('89.30'), Decimal('32'), Decimal('8')),
        'OFICIAL':  (Decimal('69.75'), Decimal('30'), Decimal('8')),
        'PEON':     (Decimal('62.80'), Decimal('30'), Decimal('8')),
    }),
    # Vigente 2024-2025 (R.M. 139-2024-TR)
    (date(2024, 6, 1), date(2025, 12, 31), 'CAPECO-FTCCP 2024-2025 (R.M. 139-2024-TR)', {
        'OPERARIO': (Decimal('87.30'), Decimal('32'), Decimal('8')),
        'OFICIAL':  (Decimal('68.50'), Decimal('30'), Decimal('8')),
        'PEON':     (Decimal('61.65'), Decimal('30'), Decimal('8')),
    }),
]

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
            desdes = [t[0] for t in TABLAS_JORNAL]
            n = JornalConstruccion.objects.filter(vigencia_desde__in=desdes).delete()[0]
            self.stdout.write(self.style.WARNING(f'Borrados {n} jornales.'))

        # Jornales (múltiples vigencias)
        jn = 0
        for desde, hasta, fuente, cats in TABLAS_JORNAL:
            for categoria, (jornal, buc, altura) in cats.items():
                JornalConstruccion.objects.update_or_create(
                    categoria=categoria, vigencia_desde=desde,
                    defaults=dict(jornal_diario=jornal, buc_pct=buc,
                                  bono_altura_pct=altura, vigencia_hasta=hasta, fuente=fuente),
                )
                jn += 1
        self.stdout.write(self.style.SUCCESS(f'Jornales: {jn} filas ({len(TABLAS_JORNAL)} vigencias).'))

        # Conceptos
        cn = 0
        for c in CONCEPTOS_CC:
            defaults = {k: v for k, v in c.items() if k != 'codigo'}
            defaults['es_sistema'] = True
            defaults['activo'] = True
            ConceptoRemunerativo.objects.update_or_create(codigo=c['codigo'], defaults=defaults)
            cn += 1
        self.stdout.write(self.style.SUCCESS(f'Conceptos construcción: {cn}.'))
