"""
seed_periodos_historicos.py
Crea 5 PeriodoNomina REGULAR históricos (Nov 2025 → Mar 2026) con totales
plausibles para que el comparativo mensual luzca con data evolutiva en demos.

NO crea RegistroNomina ni LineaNomina (sería innecesariamente pesado).
El comparativo solo lee los totales del período → suficiente para visual.

Diseño: variación natural mes-a-mes (±5% en montos, ±2 trabajadores)
para simular crecimiento orgánico. Estados:
  Nov 2025 → CERRADO
  Dic 2025 → CERRADO  (con gratificación implícita en costo)
  Ene 2026 → CERRADO
  Feb 2026 → CERRADO
  Mar 2026 → CERRADO

Idempotente: usa update_or_create por (tipo, anio, mes).
"""
import calendar
import random
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand

from nominas.models import PeriodoNomina


# Base mes-base (Mar 2026 cercano al actual): aprox 65 trabajadores, S/ 138k neto
HISTORICO = [
    # (anio, mes, trabajadores, factor_variacion, estado, descripcion)
    (2025, 11, 60, 0.92,  'CERRADO',  'Planilla Noviembre 2025'),
    (2025, 12, 62, 1.18,  'CERRADO',  'Planilla Diciembre 2025 (con gratif. Navidad)'),
    (2026,  1, 63, 0.96,  'CERRADO',  'Planilla Enero 2026'),
    (2026,  2, 64, 0.97,  'CERRADO',  'Planilla Febrero 2026'),
    (2026,  3, 66, 1.00,  'CERRADO',  'Planilla Marzo 2026'),
]

# Promedio por trabajador (Q1 2026 realista para gastronomía Perú):
# Bruto S/ 2,500 · descuentos 15% · neto S/ 2,125
# Costo empresa adicional al bruto: EsSalud 9% + SCTR 1.5% + Senati 0.75% +
# provisiones (1/12 gratif + 1/12 CTS + vacaciones) ≈ 30% sobre bruto.
BRUTO_PROMEDIO = Decimal('2500.00')
DESCUENTOS_PCT = Decimal('0.15')
APORTE_EMPRESA_PCT = Decimal('0.30')  # EsSalud + SCTR + Senati + provisiones


def _last_day(year: int, month: int) -> int:
    return calendar.monthrange(year, month)[1]


class Command(BaseCommand):
    help = 'Crea 5 períodos REGULAR históricos para enriquecer el comparativo mensual.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset', action='store_true',
            help='Borra y vuelve a crear los períodos históricos.',
        )
        parser.add_argument(
            '--seed', type=int, default=42,
            help='Semilla aleatoria para variaciones reproducibles (default 42).',
        )

    def handle(self, *args, **options):
        self.stdout.write('\n=== SEED PERÍODOS HISTÓRICOS ===')
        rng = random.Random(options['seed'])

        if options['reset']:
            for anio, mes, *_ in HISTORICO:
                PeriodoNomina.objects.filter(
                    tipo='REGULAR', anio=anio, mes=mes
                ).delete()
            self.stdout.write('  [reset] Períodos históricos borrados.')

        creados = 0
        for anio, mes, trabajadores, factor, estado, descr in HISTORICO:
            # Variación ±2% aleatoria sobre el factor base
            jitter = Decimal(str(rng.uniform(-0.02, 0.02)))
            ajuste = Decimal(str(factor)) + jitter

            bruto_total = (BRUTO_PROMEDIO * trabajadores * ajuste).quantize(Decimal('0.01'))
            descuentos = (bruto_total * DESCUENTOS_PCT).quantize(Decimal('0.01'))
            neto = (bruto_total - descuentos).quantize(Decimal('0.01'))
            aporte_emp = (bruto_total * APORTE_EMPRESA_PCT).quantize(Decimal('0.01'))
            costo_total = (bruto_total + aporte_emp).quantize(Decimal('0.01'))

            fecha_inicio = date(anio, mes, 1)
            fecha_fin = date(anio, mes, _last_day(anio, mes))
            # Pago: día 5 del mes siguiente
            mes_pago = mes + 1
            anio_pago = anio
            if mes_pago > 12:
                mes_pago = 1
                anio_pago += 1
            fecha_pago = date(anio_pago, mes_pago, 5)

            periodo, created = PeriodoNomina.objects.update_or_create(
                tipo='REGULAR', anio=anio, mes=mes,
                defaults={
                    'descripcion': descr,
                    'fecha_inicio': fecha_inicio,
                    'fecha_fin': fecha_fin,
                    'fecha_pago': fecha_pago,
                    'estado': estado,
                    'total_trabajadores': trabajadores,
                    'total_bruto': bruto_total,
                    'total_descuentos': descuentos,
                    'total_neto': neto,
                    'total_costo_empresa': costo_total,
                },
            )
            tag = 'creado' if created else 'actualizado'
            creados += 1 if created else 0
            self.stdout.write(
                f'  [{tag}] {anio}-{mes:02d} · {trabajadores} trab · '
                f'neto S/ {neto:,.0f} · costo S/ {costo_total:,.0f}'
            )

        self.stdout.write(
            f'\n  [OK] {creados} períodos creados, '
            f'{len(HISTORICO) - creados} actualizados.\n'
        )
