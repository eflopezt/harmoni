from django.db import migrations


def normalizar_valores(apps, schema_editor):
    PeriodoNomina = apps.get_model('nominas', 'PeriodoNomina')
    RegistroNomina = apps.get_model('nominas', 'RegistroNomina')

    tipos = {
        'mensual': 'REGULAR',
        'regular': 'REGULAR',
        'gratificacion': 'GRATIFICACION',
        'gratificación': 'GRATIFICACION',
        'cts': 'CTS',
        'utilidades': 'UTILIDADES',
        'liquidacion': 'LIQUIDACION',
        'liquidación': 'LIQUIDACION',
    }
    estados_periodo = {
        'borrador': 'BORRADOR',
        'calculado': 'CALCULADO',
        'aprobado': 'APROBADO',
        'cerrado': 'CERRADO',
        'anulado': 'ANULADO',
    }
    estados_registro = {
        'calculado': 'CALCULADO',
        'revisado': 'REVISADO',
        'aprobado': 'APROBADO',
        'observado': 'OBSERVADO',
        # Un registro pertenece a un periodo cerrado, pero su catalogo
        # individual termina en APROBADO.
        'cerrado': 'APROBADO',
    }

    for anterior, canonico in tipos.items():
        PeriodoNomina.objects.filter(tipo__iexact=anterior).update(tipo=canonico)
    for anterior, canonico in estados_periodo.items():
        PeriodoNomina.objects.filter(estado__iexact=anterior).update(estado=canonico)
    for anterior, canonico in estados_registro.items():
        RegistroNomina.objects.filter(estado__iexact=anterior).update(estado=canonico)


class Migration(migrations.Migration):
    dependencies = [
        ('nominas', '0031_periodo_empresa_unique'),
    ]

    operations = [
        migrations.RunPython(normalizar_valores, migrations.RunPython.noop),
    ]
