from datetime import date
from importlib import import_module

import pytest
from django.apps import apps

from empresas.models import Empresa
from nominas.models import PeriodoNomina, RegistroNomina
from personal.models import Personal


@pytest.mark.django_db
def test_normaliza_periodo_y_registro_historicos():
    empresa = Empresa.objects.create(ruc='20555555551', razon_social='Legacy SAC')
    personal = Personal.objects.create(
        empresa=empresa,
        nro_doc='75555551',
        apellidos_nombres='PERSONA LEGACY',
        estado='Activo',
        fecha_alta=date(2025, 1, 1),
    )
    periodo = PeriodoNomina.objects.create(
        empresa=empresa,
        tipo='mensual',
        estado='cerrado',
        anio=2026,
        mes=1,
        fecha_inicio=date(2026, 1, 1),
        fecha_fin=date(2026, 1, 31),
    )
    registro = RegistroNomina.objects.create(
        periodo=periodo,
        personal=personal,
        estado='cerrado',
    )

    migration = import_module(
        'nominas.migrations.0032_normalize_legacy_period_values')
    migration.normalizar_valores(apps, None)

    periodo.refresh_from_db()
    registro.refresh_from_db()
    assert periodo.tipo == 'REGULAR'
    assert periodo.estado == 'CERRADO'
    assert registro.estado == 'APROBADO'
