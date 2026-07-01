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

# codigo: dict de campos de ConceptoRemunerativo
CONCEPTOS_CC = [
    dict(codigo='cc-jornal-basico', nombre='Jornal Básico (Construcción)',
         categoria='SUELDO', tipo='INGRESO', formula='MANUAL', orden=10,
         afecto_essalud=True, afecto_afp=True, afecto_onp=True, afecto_renta=True,
         afecto_cts=True, afecto_gratif=True, afecto_vacaciones=True),
    dict(codigo='cc-dominical', nombre='Dominical (Construcción)',
         categoria='SUELDO', tipo='INGRESO', formula='MANUAL', orden=11,
         afecto_essalud=True, afecto_afp=True, afecto_onp=True, afecto_renta=True,
         afecto_cts=True, afecto_gratif=True),
    dict(codigo='cc-buc', nombre='BUC — Bonificación Unificada de Construcción',
         categoria='BONIFICACION', tipo='INGRESO', formula='MANUAL', orden=12,
         afecto_essalud=True, afecto_afp=True, afecto_onp=True, afecto_renta=True),
    dict(codigo='cc-bae', nombre='BAE — Bonificación por Alta Especialización',
         categoria='BONIFICACION', tipo='INGRESO', formula='MANUAL', orden=13,
         afecto_essalud=True, afecto_afp=True, afecto_onp=True, afecto_renta=True),
    dict(codigo='cc-bono-altura', nombre='Bono por Altura (Construcción)',
         categoria='BONIFICACION', tipo='INGRESO', formula='MANUAL', orden=14,
         afecto_essalud=True, afecto_afp=True, afecto_onp=True, afecto_renta=True),
    dict(codigo='cc-asig-escolar', nombre='Asignación Escolar (Construcción)',
         categoria='FAMILIAR', tipo='INGRESO', formula='MANUAL', orden=15,
         subtipo='NO_REMUNERATIVO'),
    dict(codigo='cc-comp-vacacional', nombre='Compensación Vacacional (Construcción)',
         categoria='SUELDO', tipo='INGRESO', formula='MANUAL', orden=16,
         afecto_essalud=True, afecto_afp=True, afecto_onp=True, afecto_renta=True),
    dict(codigo='cc-conafovicer', nombre='CONAFOVICER (2%)',
         categoria='DESCUENTO', tipo='DESCUENTO', formula='MANUAL', orden=60),
    dict(codigo='cc-prov-gratif', nombre='Provisión Gratificación (Construcción)',
         categoria='PROVISION', tipo='APORTE_EMPLEADOR', subtipo='PROVISION',
         formula='MANUAL', orden=80),
    dict(codigo='cc-prov-cts', nombre='Provisión CTS 15% (Construcción)',
         categoria='PROVISION', tipo='APORTE_EMPLEADOR', subtipo='PROVISION',
         formula='MANUAL', orden=81),
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
