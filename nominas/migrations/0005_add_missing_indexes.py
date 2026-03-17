"""
Add missing database indexes to PeriodoNomina and RegistroNomina.

PeriodoNomina:
- estado: filtered constantly (e.g. filter(estado='CERRADO'), filter(estado='BORRADOR'))
  in cierre, core, portal, integraciones, and AI context views.
- anio + mes: used in lookups like filter(anio=2026, mes=2) across nominas,
  cierre, integraciones, and analytics.

RegistroNomina:
- personal: filtered standalone in portal (employee payslip history),
  integraciones (contable exports), and AI context.
- estado: filtered in review/approval workflows.
- periodo + estado: compound filter used in cierre and approval views.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nominas', '0004_add_plan_plantilla'),
    ]

    operations = [
        # PeriodoNomina indexes
        migrations.AddIndex(
            model_name='periodonomina',
            index=models.Index(
                fields=['estado'],
                name='periodonomina_estado_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='periodonomina',
            index=models.Index(
                fields=['anio', 'mes'],
                name='periodonomina_anio_mes_idx',
            ),
        ),
        # RegistroNomina indexes
        migrations.AddIndex(
            model_name='registronomina',
            index=models.Index(
                fields=['personal'],
                name='registronomina_personal_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='registronomina',
            index=models.Index(
                fields=['estado'],
                name='registronomina_estado_idx',
            ),
        ),
        migrations.AddIndex(
            model_name='registronomina',
            index=models.Index(
                fields=['periodo', 'estado'],
                name='registronomina_periodo_est_idx',
            ),
        ),
    ]
