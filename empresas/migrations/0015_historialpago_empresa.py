from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0014_empresa_suscripcion'),
    ]

    operations = [
        migrations.AddField(
            model_name='historialpago',
            name='empresa',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='pagos_suscripcion', to='empresas.empresa',
            ),
        ),
        migrations.AlterField(
            model_name='historialpago',
            name='suscripcion',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='pagos', to='empresas.suscripcion',
            ),
        ),
    ]
