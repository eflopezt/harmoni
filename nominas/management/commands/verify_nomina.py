"""
Management command: verificar consistencia de datos de nomina.

Checks:
1. sueldo_base in RegistroNomina matches Personal.sueldo_base
2. RegistroNomina references valid Personal records
3. PeriodoNomina totals are correct
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Sum

from nominas.models import PeriodoNomina, RegistroNomina
from personal.models import Personal


class Command(BaseCommand):
    help = 'Verifica consistencia de datos de nomina'

    def add_arguments(self, parser):
        parser.add_argument('--fix', action='store_true', help='Corregir totales de PeriodoNomina')

    def handle(self, *args, **options):
        fix = options['fix']

        # 1. Check sueldo_base mismatches
        self.stdout.write(self.style.MIGRATE_HEADING('\n1. Sueldo base mismatches (RegistroNomina vs Personal)'))
        mismatches = 0
        for rn in RegistroNomina.objects.select_related('personal', 'periodo').all():
            p = rn.personal
            if p and p.sueldo_base and rn.sueldo_base != p.sueldo_base:
                # Only flag if the personal record has a different current sueldo
                # (snapshot at calc time is expected to differ if sueldo changed later)
                self.stdout.write(
                    f'  {rn.periodo} | {p.nro_doc} {p.apellidos_nombres}: '
                    f'nomina={rn.sueldo_base} vs personal={p.sueldo_base}'
                )
                mismatches += 1
        if mismatches == 0:
            self.stdout.write(self.style.SUCCESS('  No mismatches found (or all are expected snapshots)'))
        else:
            self.stdout.write(f'  Total mismatches: {mismatches} (may be expected if sueldo changed after calc)')

        # 2. Orphaned RegistroNomina (personal deleted/missing)
        self.stdout.write(self.style.MIGRATE_HEADING('\n2. RegistroNomina with invalid Personal references'))
        orphaned = RegistroNomina.objects.filter(personal__isnull=True).count()
        if orphaned:
            self.stdout.write(self.style.WARNING(f'  {orphaned} registros without personal'))
        else:
            self.stdout.write(self.style.SUCCESS('  All registros reference valid Personal records'))

        # 3. PeriodoNomina totals verification
        self.stdout.write(self.style.MIGRATE_HEADING('\n3. PeriodoNomina totals verification'))
        for periodo in PeriodoNomina.objects.all().order_by('-anio', '-mes'):
            registros = periodo.registros.all()
            count = registros.count()
            agg = registros.aggregate(
                calc_bruto=Sum('total_ingresos'),
                calc_desc=Sum('total_descuentos'),
                calc_neto=Sum('neto_a_pagar'),
            )
            calc_bruto = agg['calc_bruto'] or Decimal('0')
            calc_desc = agg['calc_desc'] or Decimal('0')
            calc_neto = agg['calc_neto'] or Decimal('0')

            issues = []
            if periodo.total_trabajadores != count:
                issues.append(f'trabajadores: stored={periodo.total_trabajadores} calc={count}')
            if periodo.total_bruto != calc_bruto:
                issues.append(f'bruto: stored={periodo.total_bruto} calc={calc_bruto}')
            if periodo.total_descuentos != calc_desc:
                issues.append(f'descuentos: stored={periodo.total_descuentos} calc={calc_desc}')
            if periodo.total_neto != calc_neto:
                issues.append(f'neto: stored={periodo.total_neto} calc={calc_neto}')

            if issues:
                self.stdout.write(self.style.WARNING(f'  {periodo}: {"; ".join(issues)}'))
                if fix:
                    periodo.total_trabajadores = count
                    periodo.total_bruto = calc_bruto
                    periodo.total_descuentos = calc_desc
                    periodo.total_neto = calc_neto
                    periodo.save(update_fields=[
                        'total_trabajadores', 'total_bruto',
                        'total_descuentos', 'total_neto',
                    ])
                    self.stdout.write(self.style.SUCCESS(f'    -> Fixed'))
            else:
                self.stdout.write(self.style.SUCCESS(f'  {periodo}: OK ({count} registros)'))

        self.stdout.write(self.style.SUCCESS('\nVerification complete.'))
