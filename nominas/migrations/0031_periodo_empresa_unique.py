from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nominas', '0030_jornalconstruccion'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='periodonomina',
            name='nominas_periodo_unique_no_liquidacion',
        ),
        migrations.AddConstraint(
            model_name='periodonomina',
            constraint=models.UniqueConstraint(
                fields=('empresa', 'tipo', 'anio', 'mes'),
                condition=~models.Q(tipo='LIQUIDACION'),
                name='nominas_periodo_empresa_unique_no_liq',
            ),
        ),
    ]
