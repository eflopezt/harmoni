"""
Reestructura los planes comerciales de headcount → módulos (4 niveles):
ASISTENCIA / PLANILLA / TALENTO / SUITE (ver core/planes.py).

Migra los planes existentes SIN downgrade:
  STARTER     → PLANILLA  (tenía asistencia + planilla)
  PROFESIONAL → SUITE     (tenía casi todo → conserva acceso completo)
  BUSINESS    → SUITE
  ENTERPRISE  → SUITE
"""
from django.db import migrations, models

MAPEO = {
    'STARTER':     'PLANILLA',
    'PROFESIONAL': 'SUITE',
    'BUSINESS':    'SUITE',
    'ENTERPRISE':  'SUITE',
}

NUEVOS_CHOICES = [
    ('ASISTENCIA', 'Asistencia — S/ 99/mes (hasta 50 colaboradores)'),
    ('PLANILLA',   'Planilla — S/ 199/mes (hasta 100 colaboradores)'),
    ('TALENTO',    'Talento — S/ 399/mes (hasta 300 colaboradores)'),
    ('SUITE',      'Suite — S/ 699/mes (300+ colaboradores)'),
]


def migrar_planes(apps, schema_editor):
    Empresa = apps.get_model('empresas', 'Empresa')
    for viejo, nuevo in MAPEO.items():
        Empresa.objects.filter(plan=viejo).update(plan=nuevo)


def revertir_planes(apps, schema_editor):
    Empresa = apps.get_model('empresas', 'Empresa')
    # Reversa aproximada (no perfecta: SUITE→PROFESIONAL, PLANILLA→STARTER)
    Empresa.objects.filter(plan='PLANILLA').update(plan='STARTER')
    Empresa.objects.filter(plan__in=['TALENTO', 'SUITE']).update(plan='PROFESIONAL')


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0011_empresa_portal_beneficios'),
    ]

    operations = [
        migrations.RunPython(migrar_planes, revertir_planes),
        migrations.AlterField(
            model_name='empresa',
            name='plan',
            field=models.CharField(
                choices=NUEVOS_CHOICES, default='SUITE', max_length=20,
                verbose_name='Plan Harmoni',
                help_text=(
                    'Plan contratado (Asistencia/Planilla/Talento/Suite). Determina '
                    'qué módulos están habilitados. El gating por nivel está en '
                    'core/planes.py y lo aplica PlanGatingMiddleware.'
                ),
            ),
        ),
    ]
