"""
Tests del blindaje de datos de pago del trabajador (anti payroll-pirates).

Cubre:
- Validación de formato: CCI = 20 dígitos exactos; cuentas solo dígitos.
  Solo se valida el campo que CAMBIÓ (data legacy no bloquea otras ediciones).
- Re-auth: editar banco/cuenta/CCI/billetera de un trabajador existente
  exige password_confirma correcto del usuario.
- Cambios de campos no-pago no piden contraseña.
- Al guardar un cambio de datos de pago se notifica IN_APP al trabajador.
- Crear personal nuevo no exige re-auth.
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User

from personal.forms import CAMPOS_PAGO, PersonalForm
from personal.models import Area, Personal, SubArea


@pytest.fixture
def subarea(db):
    area = Area.objects.create(nombre="Operaciones")
    return SubArea.objects.create(nombre="Campo", area=area)


@pytest.fixture
def usuario(db):
    return User.objects.create_user("rrhh", "r@r.com", "clave-segura-1")


@pytest.fixture
def trabajador(subarea):
    return Personal.objects.create(
        nro_doc="71000030",
        apellidos_nombres="BLINDADO PRUEBA, MARIO",
        cargo="Operario", tipo_trab="Empleado", estado="Activo",
        subarea=subarea, fecha_alta=date(2024, 1, 1),
        sueldo_base=Decimal("2500.00"),
        banco="BCP", cuenta_ahorros="19112345678901",
        cuenta_cci="00219112345678901234",
    )


def _data_desde(personal, **overrides):
    """Arma el POST data del form a partir del estado actual del trabajador."""
    form = PersonalForm(instance=personal)
    data = {}
    for name, field in form.fields.items():
        val = form.initial.get(name, getattr(personal, name, None) if name != 'password_confirma' else '')
        if val is None:
            val = ''
        elif val is True:
            val = 'on'
        elif val is False:
            val = ''
        data[name] = val
    data.update(overrides)
    return data


class TestValidacionFormato:
    def test_cci_debe_tener_20_digitos(self, trabajador, usuario):
        data = _data_desde(trabajador, cuenta_cci="123", password_confirma="clave-segura-1")
        form = PersonalForm(data, instance=trabajador, user=usuario)
        assert not form.is_valid()
        assert "cuenta_cci" in form.errors

    def test_cuenta_solo_digitos(self, trabajador, usuario):
        data = _data_desde(trabajador, cuenta_ahorros="ABC123", password_confirma="clave-segura-1")
        form = PersonalForm(data, instance=trabajador, user=usuario)
        assert not form.is_valid()
        assert "cuenta_ahorros" in form.errors

    def test_data_legacy_no_bloquea_si_no_cambia(self, subarea, usuario):
        # Trabajador con CCI legacy inválido: editar OTRO campo no debe fallar
        p = Personal.objects.create(
            nro_doc="71000031", apellidos_nombres="LEGACY, ANA",
            cargo="Operario", tipo_trab="Empleado", estado="Activo",
            subarea=subarea, fecha_alta=date(2024, 1, 1),
            sueldo_base=Decimal("2000.00"), cuenta_cci="CCI-VIEJO-MALO",
        )
        data = _data_desde(p, celular="999888777")
        form = PersonalForm(data, instance=p, user=usuario)
        assert form.is_valid(), form.errors


class TestReAuth:
    def test_cambio_de_cuenta_sin_password_falla(self, trabajador, usuario):
        data = _data_desde(trabajador, cuenta_cci="00298765432109876543")
        form = PersonalForm(data, instance=trabajador, user=usuario)
        assert not form.is_valid()
        assert "password_confirma" in form.errors

    def test_cambio_con_password_incorrecto_falla(self, trabajador, usuario):
        data = _data_desde(
            trabajador, cuenta_cci="00298765432109876543",
            password_confirma="incorrecta",
        )
        form = PersonalForm(data, instance=trabajador, user=usuario)
        assert not form.is_valid()
        assert "password_confirma" in form.errors

    def test_cambio_con_password_correcto_pasa(self, trabajador, usuario):
        data = _data_desde(
            trabajador, cuenta_cci="00298765432109876543",
            password_confirma="clave-segura-1",
        )
        form = PersonalForm(data, instance=trabajador, user=usuario)
        assert form.is_valid(), form.errors
        assert form.campos_pago_cambiados == ["cuenta_cci"]

    def test_campo_no_pago_no_pide_password(self, trabajador, usuario):
        data = _data_desde(trabajador, celular="987111222")
        form = PersonalForm(data, instance=trabajador, user=usuario)
        assert form.is_valid(), form.errors
        assert form.campos_pago_cambiados == []

    def test_alta_nueva_no_pide_password(self, subarea, usuario):
        form = PersonalForm({
            "tipo_doc": "DNI", "nro_doc": "71000032",
            "apellidos_nombres": "NUEVO, PEDRO", "cargo": "Operario",
            "tipo_trab": "Empleado", "estado": "Activo",
            "subarea": subarea.pk, "fecha_alta": "2026-01-01",
            "sueldo_base": "2000", "banco": "BCP",
            "cuenta_cci": "00219112345678901234",
            "regimen_pension": "ONP",
        }, user=usuario)
        # Puede fallar por otros required, pero NO por password_confirma
        form.is_valid()
        assert "password_confirma" not in form.errors


class TestNotificacionTrabajador:
    def test_update_view_notifica_cambio_pago(self, client, trabajador, db):
        from comunicaciones.models import Notificacion
        User.objects.create_superuser("admin", "a@a.com", "clave-admin-9")
        client.login(username="admin", password="clave-admin-9")

        data = _data_desde(
            trabajador, cuenta_cci="00298765432109876543",
            password_confirma="clave-admin-9",
        )
        from django.urls import reverse
        resp = client.post(reverse("personal_update", args=[trabajador.pk]), data)
        assert resp.status_code == 302, getattr(resp, "context", None) and resp.context["form"].errors

        trabajador.refresh_from_db()
        assert trabajador.cuenta_cci == "00298765432109876543"

        notif = Notificacion.objects.filter(
            destinatario=trabajador,
            metadata__tipo_evento="cambio_datos_pago",
        ).first()
        assert notif is not None
        assert "cuenta" in notif.cuerpo.lower() or "CCI" in notif.cuerpo
        assert notif.metadata["modificado_por"] == "admin"
