from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0013_empresa_fecha_fin_prueba'),
    ]

    operations = [
        migrations.AddField(
            model_name='empresa',
            name='suscripcion_hasta',
            field=models.DateField(
                blank=True, null=True,
                verbose_name='Suscripción pagada hasta',
                help_text='Fecha hasta la que está pagada la suscripción (gestión manual). '
                          'Vacío = sin suscripción de pago registrada.',
            ),
        ),
        migrations.AddField(
            model_name='empresa',
            name='suscripcion_nota',
            field=models.CharField(
                blank=True, default='', max_length=200,
                verbose_name='Nota de facturación',
                help_text='Referencia interna: medio de pago, comprobante, etc.',
            ),
        ),
    ]
