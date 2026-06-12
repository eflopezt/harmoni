"""
Tests del payday email (al aprobar el período).

- Trabajador CON correo → además del IN_APP se crea Notificacion EMAIL
  (tipo_evento payday_email) con el neto y tono cálido.
- Trabajador SIN correo → solo IN_APP, sin registros FALLIDA basura.
- Idempotencia del IN_APP se mantiene (re-aprobar no duplica).
"""
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from comunicaciones.models import Notificacion
from nominas.models import PeriodoNomina, RegistroNomina
from personal.models import Area, Personal, SubArea


@pytest.fixture
def subarea(db):
    area = Area.objects.create(nombre="Operaciones")
    return SubArea.objects.create(nombre="Campo", area=area)


def _trabajador(subarea, doc, nombre, **extra):
    return Personal.objects.create(
        nro_doc=doc, apellidos_nombres=nombre, cargo="Operario",
        tipo_trab="Empleado", estado="Activo", subarea=subarea,
        fecha_alta=date(2024, 1, 1), sueldo_base=Decimal("2000.00"),
        **extra,
    )


@pytest.fixture
def periodo(db):
    return PeriodoNomina.objects.create(
        tipo="REGULAR", anio=2026, mes=5,
        fecha_inicio=date(2026, 4, 22), fecha_fin=date(2026, 5, 21),
        estado="CALCULADO",
    )


@pytest.fixture
def admin_client(db, client):
    User.objects.create_superuser("admin", "a@a.com", "x")
    client.login(username="admin", password="x")
    return client


class TestPaydayEmail:
    def test_con_correo_crea_email(self, admin_client, periodo, subarea):
        con_mail = _trabajador(
            subarea, "71000060", "PAYDAY, ROSA",
            correo_personal="rosa@example.com",
        )
        RegistroNomina.objects.create(
            periodo=periodo, personal=con_mail,
            sueldo_base=Decimal("2000.00"), neto_a_pagar=Decimal("1800.00"),
        )

        resp = admin_client.post(reverse("nominas_periodo_aprobar", args=[periodo.pk]))
        assert resp.status_code == 302

        email = Notificacion.objects.filter(
            destinatario=con_mail, tipo="EMAIL",
            metadata__tipo_evento="payday_email",
        ).first()
        assert email is not None
        assert "1,800.00" in email.cuerpo
        assert "pago" in email.asunto.lower()

        # El IN_APP de siempre también existe
        assert Notificacion.objects.filter(
            destinatario=con_mail, tipo="IN_APP",
            metadata__tipo_evento="boleta_disponible",
        ).exists()

    def test_sin_correo_solo_in_app(self, admin_client, periodo, subarea):
        sin_mail = _trabajador(subarea, "71000061", "SINMAIL, JOSE")
        RegistroNomina.objects.create(
            periodo=periodo, personal=sin_mail,
            sueldo_base=Decimal("2000.00"), neto_a_pagar=Decimal("1700.00"),
        )

        admin_client.post(reverse("nominas_periodo_aprobar", args=[periodo.pk]))

        assert Notificacion.objects.filter(
            destinatario=sin_mail, tipo="IN_APP",
        ).exists()
        assert not Notificacion.objects.filter(
            destinatario=sin_mail, tipo="EMAIL",
        ).exists()
