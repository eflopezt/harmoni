# Generated for hardening — snapshots de RMV/UIT en PeriodoNomina
from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nominas', '0009_merge_20260413_2353'),
    ]

    operations = [
        migrations.AddField(
            model_name='periodonomina',
            name='rmv_snapshot',
            field=models.DecimalField(
                max_digits=8,
                decimal_places=2,
                default=Decimal('1130.00'),
                verbose_name='RMV congelada al período',
                help_text=(
                    'RMV vigente al generar el período. Usada en asignación familiar '
                    'y otros cálculos derivados de la RMV.'
                ),
            ),
        ),
        migrations.AddField(
            model_name='periodonomina',
            name='uit_snapshot',
            field=models.DecimalField(
                max_digits=10,
                decimal_places=2,
                default=Decimal('5500.00'),
                verbose_name='UIT congelada al período',
                help_text=(
                    'UIT vigente al generar el período. Usada en IR 5ta categoría.'
                ),
            ),
        ),
    ]
