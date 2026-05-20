"""
Tests para boleta PDF con QR + hash de integridad, endpoint público de
verificación, tracking de recepción (DS 009-2011-TR) y rate limit IA.

Cubre:
- generar_token_verificacion / calcular_hash_integridad: estabilidad + sensibilidad.
- generar_boleta_pdf: incluye leyenda DS 009-2011-TR y hash.
- /nominas/verificar/<token>/: 200 con token válido, 404 con token inválido.
- boleta_pdf marca BoletaPago.confirmada al trabajador propio.
- explicar_boleta_ia bloquea con 429 al superar la cuota.
"""
from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.cache import cache
from django.urls import reverse

from nominas.models import PeriodoNomina, RegistroNomina
from nominas.pdf import (
    calcular_hash_integridad,
    generar_boleta_pdf,
    generar_token_verificacion,
)
from personal.models import Area, Personal, SubArea


# ─── Helpers ──────────────────────────────────────────────────────────────────

@pytest.fixture
def area(db):
    return Area.objects.create(nombre="Operaciones")


@pytest.fixture
def subarea(area):
    return SubArea.objects.create(nombre="Campo", area=area)


@pytest.fixture
def personal(db, subarea):
    return Personal.objects.create(
        nro_doc="71234567",
        apellidos_nombres="LOPEZ GARCIA, CARLOS",
        cargo="Operario",
        tipo_trab="Empleado",
        estado="Activo",
        subarea=subarea,
        fecha_alta=date(2024, 1, 1),
        sueldo_base=Decimal("3000.00"),
    )


@pytest.fixture
def periodo(db):
    return PeriodoNomina.objects.create(
        tipo="REGULAR",
        anio=2026,
        mes=5,
        fecha_inicio=date(2026, 4, 22),
        fecha_fin=date(2026, 5, 21),
        estado="APROBADO",
    )


@pytest.fixture
def registro(personal, periodo):
    return RegistroNomina.objects.create(
        periodo=periodo,
        personal=personal,
        sueldo_base=Decimal("3000.00"),
        dias_trabajados=30,
        total_ingresos=Decimal("3000.00"),
        total_descuentos=Decimal("390.00"),
        neto_a_pagar=Decimal("2610.00"),
        aporte_essalud=Decimal("270.00"),
        costo_total_empresa=Decimal("3270.00"),
        estado="APROBADO",
    )


# ─── Token + hash ─────────────────────────────────────────────────────────────

class TestTokenYHash:
    def test_token_es_deterministico(self, registro):
        t1 = generar_token_verificacion(registro)
        t2 = generar_token_verificacion(registro)
        assert t1 == t2
        assert len(t1) == 32

    def test_token_cambia_si_cambia_neto(self, registro):
        t1 = generar_token_verificacion(registro)
        registro.neto_a_pagar = Decimal("9999.99")
        t2 = generar_token_verificacion(registro)
        assert t1 != t2

    def test_hash_integridad_16_chars(self, registro):
        h = calcular_hash_integridad(registro)
        assert len(h) == 16
        # Solo hexadecimal
        assert re.fullmatch(r"[0-9a-f]{16}", h)


# ─── PDF generation ───────────────────────────────────────────────────────────

class TestPDFGeneracion:
    def test_pdf_se_genera_y_es_bytes(self, registro):
        pdf = generar_boleta_pdf(registro)
        assert isinstance(pdf, bytes)
        assert pdf.startswith(b"%PDF")

    def test_pdf_persiste_hash_integridad_en_db(self, registro):
        assert registro.hash_integridad == ""
        generar_boleta_pdf(registro)
        registro.refresh_from_db()
        assert registro.hash_integridad == calcular_hash_integridad(registro)

    def test_pdf_contiene_leyenda_ds_2011(self, registro):
        """
        Parsea el PDF y verifica que aparece la leyenda obligatoria
        DS 009-2011-TR y el hash truncado en el footer.
        """
        try:
            import pdfplumber
        except ImportError:
            pytest.skip("pdfplumber no instalado")

        import io as _io
        pdf_bytes = generar_boleta_pdf(registro)
        with pdfplumber.open(_io.BytesIO(pdf_bytes)) as pdf:
            text = "\n".join(page.extract_text() or "" for page in pdf.pages)

        # Leyenda DS 009-2011-TR
        assert "DS 009-2011-TR" in text
        assert (
            "RECIBIR Y FIRMAR LA PRESENTE BOLETA NO IMPLICA RENUNCIA"
            in text.upper()
        )

        # Hash de verificación truncado (16 chars) en el footer
        token = generar_token_verificacion(registro)
        assert token[:16] in text


# ─── Endpoint público /verificar/<token>/ ────────────────────────────────────

class TestVerificarEndpoint:
    def test_token_valido_devuelve_200_y_datos(self, registro, client):
        token = generar_token_verificacion(registro)
        resp = client.get(reverse("verificar_boleta", args=[token]))
        assert resp.status_code == 200
        content = resp.content.decode("utf-8")
        # DNI parcialmente enmascarado (71***4567 según el patrón)
        assert "71***4567" in content
        # Período Mayo 2026
        assert "Mayo" in content
        assert "2026" in content
        # Neto
        assert "2610" in content
        # No expone el DNI completo
        assert "71234567" not in content

    def test_token_invalido_devuelve_404(self, registro, client):
        # 32 chars pero no corresponde a ninguna boleta
        bogus = "0" * 32
        resp = client.get(reverse("verificar_boleta", args=[bogus]))
        assert resp.status_code == 404

    def test_token_longitud_incorrecta_devuelve_404(self, client):
        resp = client.get(reverse("verificar_boleta", args=["x" * 10]))
        assert resp.status_code == 404


# ─── Tracking de lectura BoletaPago ───────────────────────────────────────────

class TestTrackingLectura:
    def test_descarga_trabajador_propio_marca_confirmada(self, registro, client):
        """
        Cuando un trabajador descarga su propia boleta, se crea/actualiza
        un BoletaPago.confirmada=True con la IP y user-agent.
        """
        from documentos.models import BoletaPago

        # Usuario vinculado al Personal
        user = User.objects.create_user(
            username="trabajador1", password="testpass1234"
        )
        registro.personal.usuario = user
        registro.personal.save()

        client.force_login(user)
        resp = client.get(
            reverse("nominas_boleta_pdf", args=[registro.pk]),
            HTTP_USER_AGENT="pytest-agent/1.0",
            REMOTE_ADDR="10.1.2.3",
        )
        assert resp.status_code == 200
        assert resp["Content-Type"] == "application/pdf"

        b = BoletaPago.objects.get(
            personal=registro.personal,
            periodo=date(2026, 5, 1),
        )
        assert b.confirmada is True
        assert b.fecha_confirmacion is not None
        assert b.metodo_acceso == "PDF_DESCARGA"
        assert b.user_agent == "pytest-agent/1.0"
        # Estado escala a LEIDA
        assert b.estado == "LEIDA"

    def test_descarga_admin_no_marca_confirmada(self, registro, client):
        """Cuando un admin/staff descarga, no se debe confirmar nada."""
        from documentos.models import BoletaPago

        admin = User.objects.create_superuser(
            username="admin1", password="adminpass", email="a@a.com"
        )
        client.force_login(admin)
        resp = client.get(reverse("nominas_boleta_pdf", args=[registro.pk]))
        assert resp.status_code == 200

        existe = BoletaPago.objects.filter(
            personal=registro.personal,
            periodo=date(2026, 5, 1),
        ).exists()
        assert existe is False


# ─── Rate limit IA ────────────────────────────────────────────────────────────

class TestRateLimitIA:
    def test_rate_limit_devuelve_429_al_sexto_call(self, registro, client):
        """6 llamadas consecutivas: la 6ta debe ser 429."""
        cache.clear()

        # Usuario común (no superuser) ligado al Personal
        user = User.objects.create_user(
            username="trab_ia", password="testpass1234"
        )
        registro.personal.usuario = user
        registro.personal.save()
        client.force_login(user)

        # Mockear el servicio IA para que no haga llamadas reales
        with patch("asistencia.services.ai_service.get_service") as mock_get:
            svc = mock_get.return_value
            svc.generate.return_value = "Explicación de prueba"

            url = reverse("nominas_explicar_boleta", args=[registro.pk])
            # Primeras 5 llamadas: OK
            for i in range(5):
                r = client.get(url)
                assert r.status_code == 200, f"call #{i+1} debería ser 200"

            # 6ta: 429
            r = client.get(url)
            assert r.status_code == 429
            data = r.json()
            assert data["ok"] is False
            assert "cuota" in data["error"].lower()

    def test_superuser_exento_de_rate_limit(self, registro, client):
        cache.clear()
        admin = User.objects.create_superuser(
            username="admin_ia", password="adminpass", email="x@x.com"
        )
        client.force_login(admin)
        with patch("asistencia.services.ai_service.get_service") as mock_get:
            svc = mock_get.return_value
            svc.generate.return_value = "OK"
            url = reverse("nominas_explicar_boleta", args=[registro.pk])
            for _ in range(7):
                r = client.get(url)
                assert r.status_code == 200
