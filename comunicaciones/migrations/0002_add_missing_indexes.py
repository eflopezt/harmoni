"""
Add missing database indexes to Notificacion model.

- leida_en: used in views_notif.py to filter read vs unread notifications
  and in bulk-mark-as-read operations. The existing compound index
  (destinatario, tipo, estado) doesn't cover leida_en-based queries efficiently.
- destinatario + estado: the most common query pattern in views_notif.py is
  filter(destinatario__personal=X, estado='PENDIENTE') which benefits from
  this two-column index more than the existing three-column one that includes tipo.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comunicaciones', '0001_initial'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='notificacion',
            index=models.Index(
                fields=['destinatario', 'estado'],
                name='notif_dest_estado_idx',
            ),
        ),
    ]
