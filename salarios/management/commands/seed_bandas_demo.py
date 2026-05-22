"""
Seed de bandas salariales típicas para gastronomía (demo Grupo EDO).

10 cargos comunes de restaurante con rangos min / medio / max alineados al
mercado peruano gastronomía (RMV S/ 1025 — RM CTS 2026).

Uso:
    python manage.py seed_bandas_demo
    python manage.py seed_bandas_demo --reset   # elimina bandas previas
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from salarios.models import BandaSalarial


# Definición de bandas gastronomía
# (cargo, nivel, minimo, medio (auto-calculado si None), maximo)
BANDAS_DEMO = [
    # (cargo, nivel, min, mid, max)
    ('Mesero Junior',     'JUNIOR',      Decimal('1100'), Decimal('1250'), Decimal('1400')),
    ('Mesero Senior',     'SENIOR',      Decimal('1400'), Decimal('1600'), Decimal('1800')),
    ('Cocinero',          'SEMI_SENIOR', Decimal('1500'), Decimal('1850'), Decimal('2200')),
    ('Sous Chef',         'SENIOR',      Decimal('2500'), Decimal('3150'), Decimal('3800')),
    ('Chef Ejecutivo',    'GERENTE',     Decimal('4500'), Decimal('5750'), Decimal('7000')),
    ('Bartender',         'SEMI_SENIOR', Decimal('1400'), Decimal('1800'), Decimal('2200')),
    ('Hostess',           'JUNIOR',      Decimal('1100'), Decimal('1300'), Decimal('1500')),
    ('Cajero',            'JUNIOR',      Decimal('1200'), Decimal('1350'), Decimal('1500')),
    ('Lavaplatos',        'JUNIOR',      Decimal('1025'), Decimal('1162'), Decimal('1300')),
    ('Steward',           'JUNIOR',      Decimal('1100'), Decimal('1300'), Decimal('1500')),
]


class Command(BaseCommand):
    help = 'Crea bandas salariales gastronomía típicas (demo Grupo EDO).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Elimina TODAS las bandas existentes antes de crear las nuevas.',
        )

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts['reset']:
            n = BandaSalarial.objects.all().count()
            BandaSalarial.objects.all().delete()
            self.stdout.write(self.style.WARNING(
                f'[reset] {n} banda(s) previa(s) eliminada(s).'
            ))

        creadas = 0
        omitidas = 0

        for cargo, nivel, minimo, medio, maximo in BANDAS_DEMO:
            banda, created = BandaSalarial.objects.get_or_create(
                cargo=cargo,
                nivel=nivel,
                defaults={
                    'minimo': minimo,
                    'medio': medio,
                    'maximo': maximo,
                    'moneda': 'PEN',
                    'activa': True,
                },
            )
            if created:
                creadas += 1
                self.stdout.write(self.style.SUCCESS(
                    f'  + {cargo} ({nivel}): S/ {minimo} – {medio} – {maximo}'
                ))
            else:
                omitidas += 1
                self.stdout.write(
                    f'  ~ {cargo} ({nivel}): ya existía, omitida'
                )

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Listo. Creadas: {creadas} · Existentes: {omitidas} · '
            f'Total bandas activas: {BandaSalarial.objects.filter(activa=True).count()}'
        ))
