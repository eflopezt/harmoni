"""Las liquidaciones respetan la empresa activa en todas sus rutas."""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from empresas.models import Empresa
from nominas.models import LiquidacionLaboral
from personal.models import Personal

pytestmark = pytest.mark.django_db


def _empresa(ruc, nombre, owner):
    return Empresa.objects.create(
        ruc=ruc,
        razon_social=nombre,
        activa=True,
        creado_por=owner,
    )


def _cesado(empresa, doc, nombre):
    return Personal.objects.create(
        empresa=empresa,
        nro_doc=doc,
        apellidos_nombres=nombre,
        cargo='Operario',
        tipo_trab='Empleado',
        estado='Cesado',
        fecha_alta=date(2024, 1, 1),
        fecha_cese=date(2026, 6, 30),
        motivo_cese='RENUNCIA',
        sueldo_base=Decimal('2500'),
    )


@pytest.fixture
def tenant_case(client):
    admin = User.objects.create_superuser('liq_tenant', 'liq@tenant.pe', 'pw')
    propia = _empresa('20611111111', 'Empresa liquidacion propia', admin)
    ajena = _empresa('20622222222', 'Empresa liquidacion ajena', admin)
    trabajador_propio = _cesado(propia, '72001001', 'LIQUIDACION PROPIA')
    trabajador_ajeno = _cesado(ajena, '72001002', 'LIQUIDACION AJENA')
    client.force_login(admin)
    session = client.session
    session['empresa_actual_id'] = propia.pk
    session.save()
    return client, trabajador_propio, trabajador_ajeno


def test_panel_muestra_solo_liquidaciones_de_empresa_activa(tenant_case):
    client, trabajador_propio, trabajador_ajeno = tenant_case
    response = client.get(reverse('nominas_liquidaciones'))

    assert response.status_code == 200
    ids = {row.personal_id for row in response.context['abiertas']}
    assert trabajador_propio.pk in ids
    assert trabajador_ajeno.pk not in ids
    assert 'LIQUIDACION AJENA' not in response.content.decode()


def test_detalle_y_api_no_exponen_otra_empresa(tenant_case):
    client, _, trabajador_ajeno = tenant_case
    liquidacion = LiquidacionLaboral.objects.get(personal=trabajador_ajeno)

    detail = client.get(reverse(
        'nominas_liquidacion_laboral_detalle',
        args=[liquidacion.pk],
    ))
    api = client.get(reverse(
        'nominas_api_liquidacion',
        args=[trabajador_ajeno.pk],
    ))

    assert detail.status_code == 404
    assert api.status_code == 404


def test_aprobacion_no_modifica_liquidacion_de_otra_empresa(tenant_case):
    client, _, trabajador_ajeno = tenant_case
    liquidacion = LiquidacionLaboral.objects.get(personal=trabajador_ajeno)
    estado_inicial = liquidacion.estado

    response = client.post(reverse(
        'nominas_liquidacion_laboral_aprobar',
        args=[liquidacion.pk],
    ))

    assert response.status_code == 404
    liquidacion.refresh_from_db()
    assert liquidacion.estado == estado_inicial
