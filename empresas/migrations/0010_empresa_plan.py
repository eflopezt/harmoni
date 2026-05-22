"""
Agrega campo Empresa.plan para identificar tier comercial.

Reemplaza el flag basado en username (STARTER_USERNAMES) por uno basado
en la empresa del usuario, lo que cubre también a workers de un cliente
Starter (no solo al admin).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('empresas', '0009_empresa_plan_cuentas'),
    ]

    operations = [
        migrations.AddField(
            model_name='empresa',
            name='plan',
            field=models.CharField(
                choices=[
                    ('STARTER',     'Starter — S/ 149/mes (hasta 30 colaboradores)'),
                    ('PROFESIONAL', 'Profesional — S/ 399/mes (hasta 100 colaboradores)'),
                    ('BUSINESS',    'Business — S/ 799/mes (hasta 300 colaboradores)'),
                    ('ENTERPRISE',  'Enterprise — Personalizado (300+ colaboradores)'),
                ],
                default='PROFESIONAL',
                help_text=(
                    'Plan contratado por esta empresa. Determina qué módulos y '
                    'features están habilitados. El middleware PlanStarterMiddleware '
                    'restringe acceso para empresas con plan=STARTER.'
                ),
                max_length=20,
                verbose_name='Plan Harmoni',
            ),
        ),
    ]
