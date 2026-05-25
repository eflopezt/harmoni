from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Agrega RegistroNomina.conceptos_manuales (JSONField) para permitir
    importar/exportar Excel con conceptos por trabajador (propinas, bonifs).

    Estructura: {"CODIGO_CONCEPTO": "monto_decimal_str", ...}
    Ejemplo:    {"PROPINAS": "150.00", "BONIF_PROD": "200.00"}

    El engine `calcular_registro` lee este dict y genera LineaNomina por cada
    par (codigo → monto), preservando el detalle por concepto en la boleta.
    """

    dependencies = [
        ('nominas', '0023_horastrabajadaspropinas_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='registronomina',
            name='conceptos_manuales',
            field=models.JSONField(default=dict, blank=True),
        ),
    ]
