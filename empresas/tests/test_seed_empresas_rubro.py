"""Tests del seed de empresas genéricas por rubro."""
import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_seed_crea_una_empresa_por_rubro():
    from empresas.models import Empresa
    call_command('seed_empresas_rubro', verbosity=0)
    call_command('seed_empresas_rubro', verbosity=0)  # idempotente (no duplica)

    esperado = {
        '20600000011': 'CONSTRUCCION',
        '20600000029': 'MINERIA',
        '20600000037': 'GASTRONOMIA',
        '20600000045': 'AUDIOVISUAL',
        '20600000053': 'GENERAL',
    }
    for ruc, rubro in esperado.items():
        e = Empresa.objects.get(ruc=ruc)   # get() falla si hay duplicados
        assert e.rubro == rubro

    assert 'CONSTRUCTORA' in Empresa.objects.get(ruc='20600000011').razon_social.upper()


@pytest.mark.django_db
def test_seed_solo_filtra():
    from empresas.models import Empresa
    call_command('seed_empresas_rubro', '--solo', 'MINERIA', verbosity=0)
    assert Empresa.objects.filter(rubro='MINERIA').count() == 1
    assert Empresa.objects.filter(rubro='CONSTRUCCION').count() == 0
