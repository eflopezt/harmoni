# Generated for hardening — flag para método SUNAT IR 5ta
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tareo', '0035_add_historial_emails_config_area'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuracionsistema',
            name='usar_metodo_sunat_ir5ta',
            field=models.BooleanField(
                default=False,
                verbose_name='IR 5ta: usar método SUNAT (retención mensual acumulada)',
                help_text=(
                    'Si está activo, IR 5ta usa el método oficial SUNAT con proyección '
                    'mes-a-mes (remuneración fija proyectada + variables percibidas). '
                    'Recomendado para evitar sobre-estimación en empleados con HE/bonos '
                    'variables o cese a mitad de año. Default: False (método legacy '
                    'proyección × 14).'
                ),
            ),
        ),
    ]
