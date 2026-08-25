from django.db import migrations, models
import django.db.models.deletion


def inferir_empresa(apps, schema_editor):
    Vacante = apps.get_model('reclutamiento', 'Vacante')
    Personal = apps.get_model('personal', 'Personal')
    Empresa = apps.get_model('empresas', 'Empresa')

    for vacante in Vacante.objects.filter(empresa__isnull=True).iterator():
        if not vacante.creado_por_id:
            continue
        empresa_ids = list(
            Personal.objects.filter(
                usuario_id=vacante.creado_por_id,
                empresa_id__isnull=False,
            ).values_list('empresa_id', flat=True).distinct()[:2]
        )
        if not empresa_ids:
            empresa_ids = list(
                Empresa.objects.filter(creado_por_id=vacante.creado_por_id)
                .values_list('pk', flat=True)[:2]
            )
        if len(empresa_ids) == 1:
            vacante.empresa_id = empresa_ids[0]
            vacante.save(update_fields=['empresa'])


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0019_empresa_rubro'),
        ('reclutamiento', '0007_alter_vacante_estado'),
    ]

    operations = [
        migrations.AddField(
            model_name='vacante',
            name='empresa',
            field=models.ForeignKey(
                blank=True, null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='vacantes_harmoni',
                to='empresas.empresa',
                verbose_name='Empresa',
                help_text='RUC empleador al que pertenece la requisicion.',
            ),
        ),
        migrations.RunPython(inferir_empresa, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name='vacante',
            index=models.Index(
                fields=['empresa', 'estado'], name='vacante_empresa_estado_idx'),
        ),
    ]
