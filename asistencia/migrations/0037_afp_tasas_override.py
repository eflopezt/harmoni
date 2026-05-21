"""Override de tasas AFP en ConfiguracionSistema (sin redeploy)."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tareo', '0036_usar_metodo_sunat_ir5ta'),
    ]

    operations = [
        migrations.AddField(
            model_name='configuracionsistema',
            name='afp_tasas_override',
            field=models.JSONField(
                null=True, blank=True,
                verbose_name='Override de tasas AFP (SBS)',
                help_text=(
                    'JSON con tasas por AFP. Formato: '
                    '{"Habitat": {"comision_flujo": "1.47", "seguro": "1.74"}, ...}. '
                    'Si está vacío, usa valores predeterminados del engine.'
                ),
            ),
        ),
        migrations.AddField(
            model_name='configuracionsistema',
            name='afp_tope_rma',
            field=models.DecimalField(
                max_digits=10, decimal_places=2, null=True, blank=True,
                verbose_name='Tope RMA AFP — Prima Seguro (S/)',
                help_text=(
                    'Remuneración Máxima Asegurable para cálculo de prima de '
                    'seguro AFP. Si está vacío, usa S/ 12,131.49 (Q2 2026). '
                    'SBS lo actualiza cuatrimestralmente.'
                ),
            ),
        ),
        migrations.AddField(
            model_name='configuracionsistema',
            name='afp_tasas_vigencia',
            field=models.CharField(
                max_length=20, blank=True, default='',
                verbose_name='Vigencia tasas AFP',
                help_text='Cuatrimestre de vigencia (ej. "Q2-2026" o "2026-04 a 2026-07").',
            ),
        ),
    ]
