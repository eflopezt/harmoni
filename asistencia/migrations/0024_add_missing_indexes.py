"""
Add missing database indexes to asistencia models.

RegistroTareo:
- codigo_dia: filtered when counting specific attendance codes (e.g. 'A', 'F', 'DL')
  across tareo reports and analytics.
- fecha + codigo_dia: compound lookup used when generating daily attendance
  summaries grouped by code type.

RegistroPapeleta:
- fecha_inicio + fecha_fin: range queries when checking overlapping papeletas
  and when applying overrides to RegistroTareo.
- estado: filtered standalone in approval workflows (e.g. filter(estado='PENDIENTE')).

TareoImportacion:
- estado: filtered in dashboard and processing views to show pending/failed imports.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('asistencia', '0023_add_uit_rmv_to_config'),
    ]

    operations = [
        # RegistroTareo
        migrations.AddIndex(
            model_name='registrotareo',
            index=models.Index(
                fields=['codigo_dia'],
                name='tareo_codigo_dia_idx',
            ),
        ),
        # RegistroPapeleta
        migrations.AddIndex(
            model_name='registropapeleta',
            index=models.Index(
                fields=['fecha_inicio', 'fecha_fin'],
                name='papeleta_fechas_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='registropapeleta',
            index=models.Index(
                fields=['estado'],
                name='papeleta_estado_idx',
            ),
        ),
        # TareoImportacion
        migrations.AddIndex(
            model_name='tareoimportacion',
            index=models.Index(
                fields=['estado'],
                name='importacion_estado_idx',
            ),
        ),
    ]
