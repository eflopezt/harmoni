from decimal import Decimal
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('asistencia', '0025_whatsapp_provider_openclaw'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuracionsistema',
            name='jornada_sabado_horas',
            field=models.DecimalField(
                decimal_places=1,
                default=Decimal('5.5'),
                help_text='Ej: 5.5 para personal LOCAL sábados 07:30–13:00 (sin descuento almuerzo)',
                max_digits=4,
                verbose_name='Jornada Local Sábado (h/día)',
            ),
        ),
    ]
