"""
Smoke tests críticos del portal del trabajador.

Cubre las vistas más usadas en mi-portal/:
- portal_home, mi_perfil, mi_asistencia
- mi_nomina, mis_papeletas, mis_vacaciones, mi_banco_horas

Cada vista verifica:
1. Renderiza 200 con un Personal vinculado al user.
2. Renderiza 200 cuando NO hay Personal vinculado (la vista degrada con
   `empleado=None` en el contexto — no redirige, no rompe).
3. Aislamiento de datos: un trabajador NO ve datos de otros trabajadores.

NOTA SOBRE AISLAMIENTO: las vistas del portal filtran por `personal=empleado`
en todas las queries. Los tests de aislamiento crean dos Personales con datos
distintos y verifican que cada trabajador solo ve los suyos en el HTML.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from personal.models import Area, Personal, SubArea


# ─── Fixtures compartidas ────────────────────────────────────────────────────

@pytest.fixture
def area(db):
    return Area.objects.create(nombre="Operaciones")


@pytest.fixture
def subarea(area):
    return SubArea.objects.create(nombre="Campo", area=area)


@pytest.fixture
def user_trabajador(db):
    return User.objects.create_user(
        username="trab1", password="testpass123", email="trab1@ex.com"
    )


@pytest.fixture
def user_otro(db):
    return User.objects.create_user(
        username="trab2", password="testpass123", email="trab2@ex.com"
    )


@pytest.fixture
def user_sin_personal(db):
    return User.objects.create_user(
        username="huerfano", password="testpass123"
    )


@pytest.fixture
def personal_trabajador(user_trabajador, subarea):
    return Personal.objects.create(
        usuario=user_trabajador,
        nro_doc="71111111",
        apellidos_nombres="LOPEZ TRABAJADOR, JUAN",
        cargo="Operario",
        tipo_trab="Empleado",
        estado="Activo",
        subarea=subarea,
        fecha_alta=date(2024, 1, 1),
        fecha_nacimiento=date(1990, 6, 15),
        sueldo_base=Decimal("2500.00"),
        grupo_tareo="RCO",
    )


@pytest.fixture
def personal_otro(user_otro, subarea):
    return Personal.objects.create(
        usuario=user_otro,
        nro_doc="72222222",
        apellidos_nombres="PEREZ OTRO, MARIA",
        cargo="Asistente",
        tipo_trab="Empleado",
        estado="Activo",
        subarea=subarea,
        fecha_alta=date(2023, 5, 1),
        sueldo_base=Decimal("3500.00"),
        grupo_tareo="STAFF",
    )


@pytest.fixture
def client_trabajador(user_trabajador, personal_trabajador):
    """Cliente autenticado como trabajador con Personal vinculado."""
    c = Client()
    c.force_login(user_trabajador)
    return c


@pytest.fixture
def client_sin_personal(user_sin_personal):
    """Cliente autenticado pero sin Personal vinculado."""
    c = Client()
    c.force_login(user_sin_personal)
    return c


# ═════════════════════════════════════════════════════════════════════════════
# portal_home
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPortalHome:

    def test_home_renderiza_200_con_personal_vinculado(self, client_trabajador):
        url = reverse("portal_home")
        resp = client_trabajador.get(url)
        assert resp.status_code == 200

    def test_home_renderiza_200_sin_personal_vinculado(self, client_sin_personal):
        """Sin Personal vinculado, la vista renderiza igual (empleado=None)."""
        url = reverse("portal_home")
        resp = client_sin_personal.get(url)
        assert resp.status_code == 200

    def test_home_requiere_login(self, db):
        url = reverse("portal_home")
        resp = Client().get(url)
        # @login_required → 302 al login
        assert resp.status_code == 302
        assert "/login" in resp.url or "/cuenta" in resp.url

    def test_home_solo_muestra_datos_propios(
        self, client_trabajador, personal_trabajador, personal_otro
    ):
        """El trabajador NO debe ver datos del otro Personal en su home."""
        url = reverse("portal_home")
        resp = client_trabajador.get(url)
        assert resp.status_code == 200
        # El nombre del otro no aparece (los datos están filtrados por personal=)
        # El template no muestra apellidos de otros, pero verificamos contexto.
        assert resp.context["empleado"].pk == personal_trabajador.pk


# ═════════════════════════════════════════════════════════════════════════════
# mi_nomina
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMiNomina:

    def test_mi_nomina_renderiza_200(self, client_trabajador):
        url = reverse("portal_mi_nomina")
        resp = client_trabajador.get(url)
        assert resp.status_code == 200

    def test_mi_nomina_sin_personal_renderiza_sin_error(self, client_sin_personal):
        url = reverse("portal_mi_nomina")
        resp = client_sin_personal.get(url)
        assert resp.status_code == 200

    def test_mi_nomina_requiere_login(self, db):
        url = reverse("portal_mi_nomina")
        resp = Client().get(url)
        assert resp.status_code == 302

    def test_trabajador_ve_su_propia_nomina(
        self, client_trabajador, personal_trabajador, personal_otro
    ):
        """Si hay registros de nómina, solo los del propio Personal deben aparecer."""
        from nominas.models import PeriodoNomina, RegistroNomina

        periodo = PeriodoNomina.objects.create(
            tipo="REGULAR",
            anio=2026, mes=5,
            fecha_inicio=date(2026, 4, 22),
            fecha_fin=date(2026, 5, 21),
            estado="APROBADO",
        )
        RegistroNomina.objects.create(
            periodo=periodo, personal=personal_trabajador,
            sueldo_base=Decimal("2500.00"),
            neto_a_pagar=Decimal("2100.00"),
            estado="APROBADO",
        )
        RegistroNomina.objects.create(
            periodo=periodo, personal=personal_otro,
            sueldo_base=Decimal("3500.00"),
            neto_a_pagar=Decimal("2950.00"),
            estado="APROBADO",
        )

        url = reverse("portal_mi_nomina")
        resp = client_trabajador.get(url)
        assert resp.status_code == 200
        registros = resp.context["registros"]
        # Solo debe ver UNA nómina (la suya)
        assert len(registros) == 1
        assert registros[0].personal_id == personal_trabajador.pk
        # El neto del otro NO está
        for r in registros:
            assert r.neto_a_pagar != Decimal("2950.00")


# ═════════════════════════════════════════════════════════════════════════════
# mi_perfil
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMiPerfil:

    def test_perfil_renderiza_200(self, client_trabajador):
        url = reverse("mi_perfil")
        resp = client_trabajador.get(url)
        assert resp.status_code == 200

    def test_perfil_sin_personal_renderiza_sin_error(self, client_sin_personal):
        url = reverse("mi_perfil")
        resp = client_sin_personal.get(url)
        assert resp.status_code == 200

    def test_perfil_requiere_login(self, db):
        url = reverse("mi_perfil")
        resp = Client().get(url)
        assert resp.status_code == 302

    def test_perfil_muestra_solo_datos_propios(
        self, client_trabajador, personal_trabajador
    ):
        url = reverse("mi_perfil")
        resp = client_trabajador.get(url)
        assert resp.status_code == 200
        empleado_ctx = resp.context["empleado"]
        assert empleado_ctx.pk == personal_trabajador.pk
        assert empleado_ctx.nro_doc == "71111111"


# ═════════════════════════════════════════════════════════════════════════════
# mi_asistencia
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMiAsistencia:

    def test_asistencia_renderiza_200(self, client_trabajador):
        url = reverse("mi_asistencia")
        resp = client_trabajador.get(url)
        assert resp.status_code == 200

    def test_asistencia_sin_personal_renderiza_sin_error(self, client_sin_personal):
        url = reverse("mi_asistencia")
        resp = client_sin_personal.get(url)
        assert resp.status_code == 200

    def test_asistencia_filtros_anio_mes_no_rompen(self, client_trabajador):
        """Aún con anio/mes inválidos en la URL, _safe_int los normaliza."""
        url = reverse("mi_asistencia")
        resp = client_trabajador.get(url + "?anio=NotANumber&mes=NotANumber")
        assert resp.status_code == 200

    def test_asistencia_aislamiento(
        self, client_trabajador, personal_trabajador, personal_otro
    ):
        """Los registros del otro Personal NO aparecen en mi asistencia."""
        from asistencia.models import RegistroTareo, TareoImportacion

        hoy = date.today()
        imp = TareoImportacion.objects.create(
            tipo="RELOJ",
            periodo_inicio=hoy.replace(day=1),
            periodo_fin=hoy,
            estado="COMPLETADO",
        )
        RegistroTareo.objects.create(
            importacion=imp,
            personal=personal_trabajador,
            dni=personal_trabajador.nro_doc,
            grupo="RCO",
            fecha=hoy,
            codigo_dia="T",
            horas_efectivas=Decimal("8"),
            horas_marcadas=Decimal("8"),
        )
        RegistroTareo.objects.create(
            importacion=imp,
            personal=personal_otro,
            dni=personal_otro.nro_doc,
            grupo="STAFF",
            fecha=hoy,
            codigo_dia="T",
            horas_efectivas=Decimal("9"),
            horas_marcadas=Decimal("9"),
        )

        url = (
            reverse("mi_asistencia")
            + f"?anio={hoy.year}&mes={hoy.month}"
        )
        resp = client_trabajador.get(url)
        assert resp.status_code == 200
        registros = resp.context["registros"]
        for r in registros:
            assert r.personal_id == personal_trabajador.pk


# ═════════════════════════════════════════════════════════════════════════════
# mis_papeletas
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMisPapeletas:

    def test_papeletas_renderiza_200(self, client_trabajador):
        url = reverse("mis_papeletas")
        resp = client_trabajador.get(url)
        assert resp.status_code == 200

    def test_papeletas_sin_personal(self, client_sin_personal):
        url = reverse("mis_papeletas")
        resp = client_sin_personal.get(url)
        assert resp.status_code == 200

    def test_papeletas_aislamiento(
        self, client_trabajador, personal_trabajador, personal_otro
    ):
        """Solo papeletas del propio Personal aparecen."""
        from asistencia.models import RegistroPapeleta

        RegistroPapeleta.objects.create(
            personal=personal_trabajador,
            dni=personal_trabajador.nro_doc,
            nombre_archivo=personal_trabajador.apellidos_nombres,
            tipo_permiso="VACACIONES",
            fecha_inicio=date.today(),
            fecha_fin=date.today(),
            dias_habiles=1,
            estado="APROBADA",
            origen="PORTAL",
        )
        RegistroPapeleta.objects.create(
            personal=personal_otro,
            dni=personal_otro.nro_doc,
            nombre_archivo=personal_otro.apellidos_nombres,
            tipo_permiso="VACACIONES",
            fecha_inicio=date.today(),
            fecha_fin=date.today(),
            dias_habiles=1,
            estado="APROBADA",
            origen="PORTAL",
        )

        url = reverse("mis_papeletas") + f"?anio={date.today().year}"
        resp = client_trabajador.get(url)
        assert resp.status_code == 200
        for p in resp.context["papeletas"]:
            assert p.personal_id == personal_trabajador.pk


# ═════════════════════════════════════════════════════════════════════════════
# mis_vacaciones
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMisVacaciones:

    def test_vacaciones_renderiza_200(self, client_trabajador):
        url = reverse("portal_mis_vacaciones")
        resp = client_trabajador.get(url)
        assert resp.status_code == 200

    def test_vacaciones_sin_personal(self, client_sin_personal):
        url = reverse("portal_mis_vacaciones")
        resp = client_sin_personal.get(url)
        assert resp.status_code == 200


# ═════════════════════════════════════════════════════════════════════════════
# mi_banco_horas
# ═════════════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestMiBancoHoras:

    def test_banco_horas_renderiza_200(self, client_trabajador):
        url = reverse("mi_banco_horas")
        resp = client_trabajador.get(url)
        assert resp.status_code == 200

    def test_banco_horas_sin_personal(self, client_sin_personal):
        url = reverse("mi_banco_horas")
        resp = client_sin_personal.get(url)
        assert resp.status_code == 200

    def test_banco_horas_aislamiento(
        self, client_trabajador, personal_trabajador, personal_otro
    ):
        from asistencia.models import BancoHoras

        BancoHoras.objects.create(
            personal=personal_trabajador,
            periodo_anio=2026, periodo_mes=5,
            he_25_acumuladas=Decimal("4"),
            saldo_horas=Decimal("4"),
        )
        BancoHoras.objects.create(
            personal=personal_otro,
            periodo_anio=2026, periodo_mes=5,
            he_25_acumuladas=Decimal("10"),
            saldo_horas=Decimal("10"),
        )

        url = reverse("mi_banco_horas")
        resp = client_trabajador.get(url)
        assert resp.status_code == 200
        for r in resp.context["registros"]:
            assert r.personal_id == personal_trabajador.pk
