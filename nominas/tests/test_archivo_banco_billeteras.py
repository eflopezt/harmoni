"""
Tests del archivo de pago a bancos + dispersión a billeteras digitales
(Ley 32413 + D.S. 011-2026-EF).

Cubre:
- Personal.paga_por_billetera: requiere medio BILLETERA + acuerdo + celular válido.
- El archivo de banco (BCP) EXCLUYE a quienes pagan por billetera (evita doble pago).
- El archivo BILLETERAS incluye solo a quienes tienen acuerdo vigente.
- Sin acuerdo, el trabajador sigue saliendo en el archivo de banco.
- PersonalForm exige billetera + celular + acuerdo al elegir medio BILLETERA.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from nominas.models import PeriodoNomina, RegistroNomina
from personal.models import Area, Personal, SubArea


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def subarea(db):
    area = Area.objects.create(nombre="Operaciones")
    return SubArea.objects.create(nombre="Campo", area=area)


def _crear_personal(subarea, nro_doc, nombre, **extra):
    base = dict(
        nro_doc=nro_doc,
        apellidos_nombres=nombre,
        cargo="Operario",
        tipo_trab="Empleado",
        estado="Activo",
        subarea=subarea,
        fecha_alta=date(2024, 1, 1),
        sueldo_base=Decimal("3000.00"),
        cuenta_cci="00219300425860175392",  # CCI válido de 20 dígitos
    )
    base.update(extra)
    return Personal.objects.create(**base)


@pytest.fixture
def periodo(db):
    return PeriodoNomina.objects.create(
        tipo="REGULAR", anio=2026, mes=5,
        fecha_inicio=date(2026, 4, 22), fecha_fin=date(2026, 5, 21),
        estado="APROBADO",
    )


def _crear_registro(periodo, personal, neto="2610.00"):
    return RegistroNomina.objects.create(
        periodo=periodo, personal=personal,
        sueldo_base=Decimal("3000.00"), dias_trabajados=30,
        total_ingresos=Decimal("3000.00"),
        neto_a_pagar=Decimal(neto),
        estado="APROBADO",
    )


@pytest.fixture
def admin_client(db, client):
    User.objects.create_superuser("admin", "a@a.com", "x")
    client.login(username="admin", password="x")
    return client


# ─── Personal.paga_por_billetera ─────────────────────────────────────────────

class TestPagaPorBilletera:
    def test_requiere_los_tres_factores(self, subarea):
        p = _crear_personal(
            subarea, "71000001", "YAPERO UNO",
            medio_pago_haberes="BILLETERA", billetera_tipo="YAPE",
            billetera_celular="987654321", billetera_acuerdo=True,
        )
        assert p.paga_por_billetera is True

    def test_sin_acuerdo_no_paga_por_billetera(self, subarea):
        p = _crear_personal(
            subarea, "71000002", "SIN ACUERDO",
            medio_pago_haberes="BILLETERA", billetera_tipo="YAPE",
            billetera_celular="987654321", billetera_acuerdo=False,
        )
        assert p.paga_por_billetera is False

    @pytest.mark.parametrize("celular", ["", "98765432", "9876543210", "887654321", "98765432a"])
    def test_celular_invalido_no_paga_por_billetera(self, subarea, celular):
        p = _crear_personal(
            subarea, "71000003", "CEL MALO",
            medio_pago_haberes="BILLETERA", billetera_tipo="PLIN",
            billetera_celular=celular, billetera_acuerdo=True,
        )
        assert p.paga_por_billetera is False

    def test_medio_cuenta_ignora_datos_de_billetera(self, subarea):
        p = _crear_personal(
            subarea, "71000004", "POR CUENTA",
            medio_pago_haberes="CUENTA", billetera_tipo="YAPE",
            billetera_celular="987654321", billetera_acuerdo=True,
        )
        assert p.paga_por_billetera is False


# ─── Archivo banco vs billeteras ─────────────────────────────────────────────

class TestArchivosPago:
    @pytest.fixture
    def escenario(self, subarea, periodo):
        """Dos trabajadores: uno por cuenta (CCI), otro por Yape con acuerdo."""
        cuenta = _crear_personal(subarea, "71111111", "BANCARIO, JUAN")
        yapero = _crear_personal(
            subarea, "72222222", "YAPERO, MARIA",
            medio_pago_haberes="BILLETERA", billetera_tipo="YAPE",
            billetera_celular="987654321", billetera_acuerdo=True,
        )
        _crear_registro(periodo, cuenta, "2500.00")
        _crear_registro(periodo, yapero, "1800.00")
        return periodo

    def test_bcp_excluye_billeteras(self, admin_client, escenario):
        url = reverse("nominas_periodo_archivo_banco", args=[escenario.pk])
        resp = admin_client.get(url + "?banco=BCP")
        assert resp.status_code == 200
        body = resp.content.decode("utf-8")
        assert "BANCARIO" in body
        assert "YAPERO" not in body  # va por billetera, no al banco

    def test_billeteras_incluye_solo_con_acuerdo(self, admin_client, escenario):
        url = reverse("nominas_periodo_archivo_banco", args=[escenario.pk])
        resp = admin_client.get(url + "?banco=BILLETERAS")
        assert resp.status_code == 200
        body = resp.content.decode("utf-8")
        assert "YAPERO" in body
        assert "Yape" in body
        assert "987654321" in body
        assert "1800.00" in body
        assert "BANCARIO" not in body

    def test_sin_acuerdo_sigue_en_banco(self, admin_client, subarea, periodo):
        p = _crear_personal(
            subarea, "73333333", "SINACUERDO, PEDRO",
            medio_pago_haberes="BILLETERA", billetera_tipo="PLIN",
            billetera_celular="987654321", billetera_acuerdo=False,
        )
        _crear_registro(periodo, p)
        url = reverse("nominas_periodo_archivo_banco", args=[periodo.pk])
        resp = admin_client.get(url + "?banco=BCP")
        assert resp.status_code == 200
        assert "SINACUERDO" in resp.content.decode("utf-8")

    def test_billeteras_vacio_redirige_con_aviso(self, admin_client, subarea, periodo):
        p = _crear_personal(subarea, "74444444", "BANCARIO, SOLO")
        _crear_registro(periodo, p)
        url = reverse("nominas_periodo_archivo_banco", args=[periodo.pk])
        resp = admin_client.get(url + "?banco=BILLETERAS")
        assert resp.status_code == 302  # redirect con warning, no archivo vacío


# ─── Validación del formulario ───────────────────────────────────────────────

class TestPersonalFormBilletera:
    def _form(self, subarea, **billetera_data):
        from personal.forms import PersonalForm
        data = {
            "tipo_doc": "DNI", "nro_doc": "75555555",
            "apellidos_nombres": "FORM, TEST",
            "cargo": "Operario", "tipo_trab": "Empleado",
            "estado": "Activo", "subarea": subarea.pk,
            "fecha_alta": "2024-01-01", "sueldo_base": "3000.00",
            "medio_pago_haberes": "BILLETERA",
        }
        data.update(billetera_data)
        return PersonalForm(data=data)

    def test_billetera_sin_acuerdo_invalida(self, subarea):
        form = self._form(subarea, billetera_tipo="YAPE", billetera_celular="987654321")
        assert not form.is_valid()
        assert "billetera_acuerdo" in form.errors

    def test_billetera_celular_invalido(self, subarea):
        form = self._form(
            subarea, billetera_tipo="YAPE",
            billetera_celular="123", billetera_acuerdo="on",
        )
        assert not form.is_valid()
        assert "billetera_celular" in form.errors

    def test_billetera_completa_valida_los_campos_billetera(self, subarea):
        form = self._form(
            subarea, billetera_tipo="YAPE",
            billetera_celular="987654321", billetera_acuerdo="on",
        )
        form.is_valid()
        for campo in ("billetera_tipo", "billetera_celular", "billetera_acuerdo"):
            assert campo not in form.errors
