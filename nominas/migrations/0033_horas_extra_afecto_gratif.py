"""
Corrige `afecto_gratif` de las horas extra (he-25, he-35, he-100): estaban en
False en el seed original pese a que la documentación legal interna de
Harmoni (docs/internal/REGLAS_PERUANAS.md §3.4) ya afirmaba que las HE son
remunerativas y afectan gratificación. El motor (`calcular_gratificacion`)
ahora lee este flag para promediar las remuneraciones variables/imprecisas
regulares del semestre.
"""
from django.db import migrations

CODIGOS_HE = ['he-25', 'he-35', 'he-100']


def marcar_afecto_gratif(apps, schema_editor):
    ConceptoRemunerativo = apps.get_model('nominas', 'ConceptoRemunerativo')
    ConceptoRemunerativo.objects.filter(codigo__in=CODIGOS_HE).update(afecto_gratif=True)


def revertir(apps, schema_editor):
    ConceptoRemunerativo = apps.get_model('nominas', 'ConceptoRemunerativo')
    ConceptoRemunerativo.objects.filter(codigo__in=CODIGOS_HE).update(afecto_gratif=False)


class Migration(migrations.Migration):

    dependencies = [
        ('nominas', '0032_normalize_legacy_period_values'),
    ]

    operations = [
        migrations.RunPython(marcar_afecto_gratif, revertir),
    ]
