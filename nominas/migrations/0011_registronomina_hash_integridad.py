# Generated for boleta verification — campo hash_integridad en RegistroNomina.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nominas', '0010_periodonomina_snapshots'),
    ]

    operations = [
        migrations.AddField(
            model_name='registronomina',
            name='hash_integridad',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text=(
                    'SHA-256 truncado de los datos críticos de la boleta '
                    '(neto, fecha, DNI, periodo).'
                ),
                max_length=16,
            ),
        ),
    ]
