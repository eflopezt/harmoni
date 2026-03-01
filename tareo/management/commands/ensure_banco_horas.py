"""
Management command: ensure_banco_horas

Crea registros BancoHoras con saldo 0 para todos los STAFF activos
que no tengan registro en el período indicado.

Uso:
    python manage.py ensure_banco_horas --anio 2026 --mes 2
    python manage.py ensure_banco_horas --anio 2026 --mes 1 --mes 2

Opciones:
    --anio   Año del período (requerido)
    --mes    Mes(es) del período, 1-12. Se puede repetir para varios meses.
    --dry-run  Solo muestra qué haría sin crear nada
"""
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError

from personal.models import Personal
from tareo.models import BancoHoras

CERO = Decimal('0.00')


class Command(BaseCommand):
    help = (
        'Crea registros BancoHoras vacíos (saldo 0) para todos los STAFF activos '
        'que no tengan entrada en el período indicado.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--anio',
            type=int,
            required=True,
            help='Año del período (ej. 2026)',
        )
        parser.add_argument(
            '--mes',
            type=int,
            action='append',
            dest='meses',
            required=True,
            metavar='MES',
            help='Mes del período 1-12. Repetir para varios meses (ej. --mes 1 --mes 2)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            default=False,
            help='Solo muestra qué haría, sin crear registros',
        )

    def handle(self, *args, **options):
        anio = options['anio']
        meses = sorted(set(options['meses']))
        dry_run = options['dry_run']

        # Validaciones
        if anio < 2020 or anio > 2099:
            raise CommandError(f'Año inválido: {anio}')
        for mes in meses:
            if mes < 1 or mes > 12:
                raise CommandError(f'Mes inválido: {mes}. Debe estar entre 1 y 12.')

        staff_activo = Personal.objects.filter(
            grupo_tareo='STAFF',
            estado='Activo',
        ).order_by('apellidos_nombres')

        total_staff = staff_activo.count()
        self.stdout.write(
            f'STAFF activos encontrados: {total_staff}'
        )

        if dry_run:
            self.stdout.write(self.style.WARNING('--- DRY RUN: no se crearán registros ---'))

        total_creados = 0
        total_existentes = 0

        for mes in meses:
            MESES_ES = ['Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
            mes_nombre = MESES_ES[mes - 1]
            self.stdout.write(f'\nProcesando {mes_nombre} {anio}...')

            # IDs que ya tienen BancoHoras para este período
            existentes_ids = set(
                BancoHoras.objects.filter(
                    periodo_anio=anio,
                    periodo_mes=mes,
                ).values_list('personal_id', flat=True)
            )

            creados_mes = 0
            existentes_mes = len(existentes_ids)

            for p in staff_activo:
                if p.id in existentes_ids:
                    continue  # ya tiene registro

                if not dry_run:
                    BancoHoras.objects.create(
                        personal=p,
                        periodo_anio=anio,
                        periodo_mes=mes,
                        he_25_acumuladas=CERO,
                        he_35_acumuladas=CERO,
                        he_100_acumuladas=CERO,
                        he_compensadas=CERO,
                        saldo_horas=CERO,
                        observaciones='Creado automáticamente por ensure_banco_horas (sin HE en período)',
                    )
                creados_mes += 1

            total_creados += creados_mes
            total_existentes += existentes_mes

            if dry_run:
                self.stdout.write(
                    f'  Existentes: {existentes_mes} | '
                    f'Se crearían: {creados_mes}'
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  Existentes: {existentes_mes} | '
                        f'Creados: {creados_mes}'
                    )
                )

        # Resumen final
        self.stdout.write('')
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'DRY RUN completado — se crearían {total_creados} registros '
                    f'({total_existentes} ya existían).'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Completado: {total_creados} registros creados, '
                    f'{total_existentes} ya existían.'
                )
            )
