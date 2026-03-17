"""
Add missing database indexes to Personal model for frequently filtered fields.

Fields indexed:
- fecha_alta: filtered in vacaciones saldo generation, analytics tenure buckets,
  and contract-related queries across multiple views.
- apellidos_nombres: used in ORDER BY on virtually every Personal queryset
  (ordering = ['apellidos_nombres'] in Meta, plus explicit .order_by() calls).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('personal', '0020_add_cond_trabajo_alimentacion'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='personal',
            index=models.Index(
                fields=['fecha_alta'],
                name='personal_fecha_alta_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='personal',
            index=models.Index(
                fields=['apellidos_nombres'],
                name='personal_apellidos_idx',
            ),
        ),
    ]
