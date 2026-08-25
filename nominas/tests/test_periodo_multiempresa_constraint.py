from datetime import date

import pytest
from django.db import IntegrityError, transaction

from empresas.models import Empresa
from nominas.models import PeriodoNomina

pytestmark = pytest.mark.django_db


def _empresa(ruc):
    return Empresa.objects.create(ruc=ruc, razon_social=f'Empresa {ruc}')


def _periodo(empresa):
    return PeriodoNomina.objects.create(
        empresa=empresa, tipo='REGULAR', anio=2026, mes=8,
        fecha_inicio=date(2026, 7, 22), fecha_fin=date(2026, 8, 21),
    )


def test_mismo_mes_es_valido_en_dos_empresas():
    _periodo(_empresa('20123456801'))
    segundo = _periodo(_empresa('20123456802'))
    assert segundo.pk is not None


def test_mismo_mes_se_rechaza_dentro_de_una_empresa():
    empresa = _empresa('20123456803')
    _periodo(empresa)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _periodo(empresa)
