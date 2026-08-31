from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from personal.models import Area, Contrato, Personal, RenovacionContrato, SubArea


@pytest.fixture
def admin(db):
    return User.objects.create_superuser(
        username="contratos_admin",
        password="adminpass",
        email="contratos@example.com",
    )


@pytest.fixture
def client_admin(admin):
    client = Client()
    client.force_login(admin)
    return client


@pytest.fixture
def subarea(db):
    area = Area.objects.create(nombre="Legal")
    return SubArea.objects.create(nombre="Contratos", area=area)


def crear_personal(subarea, dni, nombre, fecha_fin):
    return Personal.objects.create(
        nro_doc=dni,
        apellidos_nombres=nombre,
        cargo="Analista",
        tipo_trab="Empleado",
        estado="Activo",
        subarea=subarea,
        fecha_alta=date(2024, 1, 1),
        tipo_contrato="PLAZO_FIJO",
        fecha_inicio_contrato=date(2024, 1, 1),
        fecha_fin_contrato=fecha_fin,
        sueldo_base=Decimal("2500.00"),
    )


@pytest.mark.django_db
def test_panel_contratos_muestra_renovacion_masiva_en_vencidos(client_admin, subarea):
    crear_personal(
        subarea,
        "70000000",
        "PANEL, RENATA",
        date(2024, 1, 31),
    )

    response = client_admin.get(f"{reverse('contratos_panel')}?tab=vencimientos")

    assert response.status_code == 200
    html = response.content.decode()
    assert "Renovación masiva" in html
    assert reverse("contratos_renovar_masivo") in html


@pytest.mark.django_db
def test_renovacion_masiva_cierra_original_crea_nuevo_y_sincroniza(client_admin, subarea):
    personal = crear_personal(
        subarea,
        "70000001",
        "RENOVABLE, ANA",
        date(2024, 3, 31),
    )
    original = Contrato.objects.create(
        personal=personal,
        tipo_contrato="PLAZO_FIJO",
        fecha_inicio=date(2024, 1, 1),
        fecha_fin=date(2024, 3, 31),
        estado="VIGENTE",
        sueldo_pactado=Decimal("2500.00"),
        cargo_contrato="Analista",
    )

    response = client_admin.post(
        reverse("contratos_renovar_masivo"),
        {
            "personal_ids": [str(personal.pk)],
            "tipo_contrato": "__MANTENER__",
            "fecha_fin": "2099-12-31",
            "motivo": "Continuidad operativa",
        },
    )

    assert response.status_code == 302
    assert response.url == f"{reverse('contratos_panel')}?tab=vencimientos"

    personal.refresh_from_db()
    original.refresh_from_db()
    nuevo = Contrato.objects.get(personal=personal, estado="VIGENTE")
    renovacion = RenovacionContrato.objects.get(
        contrato_original=original,
        contrato_nuevo=nuevo,
    )

    assert original.estado == "RENOVADO"
    assert nuevo.fecha_inicio == date(2024, 4, 1)
    assert nuevo.fecha_fin == date(2099, 12, 31)
    assert nuevo.sueldo_pactado == Decimal("2500.00")
    assert personal.fecha_inicio_contrato == date(2024, 4, 1)
    assert personal.fecha_fin_contrato == date(2099, 12, 31)
    assert renovacion.motivo == "Continuidad operativa"


@pytest.mark.django_db
def test_renovacion_masiva_crea_historico_si_solo_hay_datos_en_ficha(client_admin, subarea):
    personal = crear_personal(
        subarea,
        "70000002",
        "LEGACY, LUIS",
        date(2024, 2, 29),
    )

    response = client_admin.post(
        reverse("contratos_renovar_masivo"),
        {
            "personal_ids": [str(personal.pk)],
            "tipo_contrato": "OBRA_SERVICIO",
            "fecha_fin": "2099-06-30",
            "motivo": "Prórroga de obra",
        },
    )

    assert response.status_code == 302
    assert Contrato.objects.filter(personal=personal).count() == 2

    historico = Contrato.objects.get(personal=personal, estado="RENOVADO")
    nuevo = Contrato.objects.get(personal=personal, estado="VIGENTE")
    personal.refresh_from_db()

    assert historico.fecha_fin == date(2024, 2, 29)
    assert nuevo.tipo_contrato == "OBRA_SERVICIO"
    assert nuevo.fecha_inicio == date(2024, 3, 1)
    assert personal.tipo_contrato == "OBRA_SERVICIO"
    assert RenovacionContrato.objects.filter(
        contrato_original=historico,
        contrato_nuevo=nuevo,
    ).exists()


@pytest.mark.django_db
def test_renovacion_masiva_omite_contratos_que_ya_no_estan_vencidos(client_admin, subarea):
    vencido = crear_personal(
        subarea,
        "70000003",
        "VENCIDO, MARIA",
        date(2024, 5, 31),
    )
    vigente = crear_personal(
        subarea,
        "70000004",
        "VIGENTE, JOSE",
        date(2099, 5, 31),
    )

    Contrato.objects.create(
        personal=vencido,
        tipo_contrato="PLAZO_FIJO",
        fecha_inicio=date(2024, 1, 1),
        fecha_fin=date(2024, 5, 31),
        estado="VIGENTE",
    )
    Contrato.objects.create(
        personal=vigente,
        tipo_contrato="PLAZO_FIJO",
        fecha_inicio=date(2099, 1, 1),
        fecha_fin=date(2099, 5, 31),
        estado="VIGENTE",
    )

    response = client_admin.post(
        reverse("contratos_renovar_masivo"),
        {
            "personal_ids": [str(vencido.pk), str(vigente.pk)],
            "tipo_contrato": "__MANTENER__",
            "fecha_fin": "2099-12-31",
        },
    )

    assert response.status_code == 302
    assert RenovacionContrato.objects.count() == 1

    vigente.refresh_from_db()
    assert vigente.fecha_fin_contrato == date(2099, 5, 31)
    assert Contrato.objects.filter(personal=vigente).count() == 1
