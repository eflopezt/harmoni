"""
Add missing database indexes to vacaciones models.

VentaVacaciones:
- personal: no indexes at all on this model; personal is the primary
  lookup field when showing vacation sale history per employee.

SolicitudPermiso:
- fecha_inicio + fecha_fin: range queries when checking overlapping
  permissions for a given date range.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('vacaciones', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='ventavacaciones',
            index=models.Index(
                fields=['personal'],
                name='ventavac_personal_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='solicitudpermiso',
            index=models.Index(
                fields=['fecha_inicio', 'fecha_fin'],
                name='solicpermiso_fechas_idx',
            ),
        ),
    ]
