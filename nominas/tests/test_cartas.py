"""
Tests Sprint 3 — Documentos al cese: Carta de no adeudo + Certificado de trabajo.

Cubre:
  1. generar_carta_no_adeudo retorna bytes válidos (signature PDF).
  2. La carta contiene el nombre de empresa, DNI del trabajador y monto total.
  3. generar_certificado_trabajo con trabajador activo levanta ValueError.
  4. generar_certificado_trabajo con trabajador cesado retorna bytes válidos.
  5. URLs requieren staff (admin).
  6. URL del certificado de trabajo descarga el PDF y trae el nombre.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from asistencia.models import ConfiguracionSistema
from nominas.cartas import (
    generar_carta_no_adeudo,
    generar_certificado_trabajo,
)
from nominas.models import LiquidacionLaboral
from personal.models import Area, Personal, SubArea


def _pdf_text(pdf_bytes: bytes) -> str:
    """Extrae texto del PDF usando pypdf (disponible vía pdfminer)."""
    import io
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return '\n'.join((page.extract_text() or '') for page in reader.pages)
    except Exception:
        # Fallback: pdfminer
        from pdfminer.high_level import extract_text
        return extract_text(io.BytesIO(pdf_bytes)) or ''


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def empresa_config(db):
    """ConfiguracionSistema con nombre y RUC para que las cartas tengan datos."""
    cfg, _ = ConfiguracionSistema.objects.get_or_create(
        pk=1,
        defaults={'empresa_nombre': 'Restaurante Sabores SAC'},
    )
    cfg.empresa_nombre = 'Restaurante Sabores SAC'
    cfg.ruc = '20555666777'
    cfg.empresa_direccion = 'Av. Demo 123, San Isidro, Lima'
    cfg.save()
    return cfg


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username='admin_cartas', password='x', email='cartas@a.com',
    )


@pytest.fixture
def admin_client(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.fixture
def area(db):
    return Area.objects.create(nombre='Operaciones CARTAS')


@pytest.fixture
def subarea(area):
    return SubArea.objects.create(nombre='Sub CARTAS', area=area)


@pytest.fixture
def worker_activo(db, subarea, empresa_config):
    return Personal.objects.create(
        nro_doc='70000001',
        apellidos_nombres='LOPEZ PEREZ, MARIA',
        cargo='Mozo',
        tipo_trab='Empleado',
        estado='Activo',
        subarea=subarea,
        fecha_alta=date(2024, 1, 15),
        sueldo_base=Decimal('2000.00'),
        regimen_pension='AFP',
        afp='Prima',
    )


@pytest.fixture
def worker_cesado(db, subarea, empresa_config):
    return Personal.objects.create(
        nro_doc='70000002',
        apellidos_nombres='CARDENAS RUIZ, JUAN',
        cargo='Bartender',
        tipo_trab='Empleado',
        estado='Cesado',
        subarea=subarea,
        fecha_alta=date(2023, 6, 1),
        fecha_cese=date(2026, 3, 31),
        motivo_cese='RENUNCIA',
        sueldo_base=Decimal('2500.00'),
        regimen_pension='AFP',
        afp='Prima',
    )


@pytest.fixture
def liquidacion_calculada(worker_cesado):
    """LL auto-creada por el signal del cese; la dejamos APROBADA."""
    liq = LiquidacionLaboral.objects.get(personal=worker_cesado)
    liq.estado = 'APROBADA'
    liq.save(update_fields=['estado'])
    return liq


# ─── 1. generar_carta_no_adeudo ──────────────────────────────────────────────

class TestCartaNoAdeudo:
    def test_genera_bytes_pdf_validos(self, liquidacion_calculada):
        """Retorna bytes con signature %PDF al inicio."""
        pdf = generar_carta_no_adeudo(liquidacion_calculada)
        assert isinstance(pdf, (bytes, bytearray))
        assert len(pdf) > 1000  # PDF mínimamente con contenido real
        assert pdf[:4] == b'%PDF', f'No es un PDF válido (header={pdf[:8]!r})'

    def test_contiene_nombre_empresa_dni_y_monto(self, liquidacion_calculada, empresa_config):
        """El PDF debe contener nombre empresa, DNI del trabajador y monto total."""
        pdf = generar_carta_no_adeudo(liquidacion_calculada)
        texto = _pdf_text(pdf)
        assert 'Restaurante Sabores SAC' in texto
        # DNI: 70000002
        assert '70000002' in texto
        # Apellidos
        assert 'CARDENAS' in texto.upper()
        # Título normativo
        assert 'NO ADEUDO' in texto.upper()
        # Monto total formateado (incluye 'S/' y la coma/punto)
        assert 'S/' in texto

    def test_contiene_fecha_cese_y_motivo(self, liquidacion_calculada):
        """Fecha de cese (31/03/2026) y motivo (Renuncia) están en el PDF."""
        pdf = generar_carta_no_adeudo(liquidacion_calculada)
        texto = _pdf_text(pdf)
        assert '31/03/2026' in texto
        # 'Renuncia' aparece en el motivo formateado por get_motivo_cese_display
        assert 'Renuncia' in texto or 'RENUNCIA' in texto


# ─── 2. generar_certificado_trabajo ──────────────────────────────────────────

class TestCertificadoTrabajo:
    def test_trabajador_activo_lanza_valueerror(self, worker_activo):
        """Generar certificado para alguien NO cesado debe lanzar ValueError."""
        with pytest.raises(ValueError) as excinfo:
            generar_certificado_trabajo(worker_activo)
        assert 'no está cesado' in str(excinfo.value).lower()

    def test_trabajador_cesado_retorna_pdf(self, worker_cesado):
        """Trabajador cesado con fecha_cese → PDF válido."""
        pdf = generar_certificado_trabajo(worker_cesado)
        assert isinstance(pdf, (bytes, bytearray))
        assert pdf[:4] == b'%PDF'
        assert len(pdf) > 1000

    def test_contiene_datos_clave(self, worker_cesado, empresa_config):
        """PDF contiene nombre, DNI, cargo, fechas y nombre empresa."""
        pdf = generar_certificado_trabajo(worker_cesado)
        texto = _pdf_text(pdf)
        # Empresa
        assert 'Restaurante Sabores SAC' in texto
        # Datos trabajador
        assert '70000002' in texto
        assert 'CARDENAS' in texto.upper()
        # Cargo
        assert 'Bartender' in texto
        # Fechas (alta 01/06/2023, cese 31/03/2026)
        assert '01/06/2023' in texto
        assert '31/03/2026' in texto
        # Título normativo
        assert 'CERTIFICADO' in texto.upper()

    def test_sin_fecha_cese_lanza_valueerror(self, subarea, empresa_config):
        """estado='Cesado' SIN fecha_cese → ValueError explícito."""
        # Bypass del validator: creamos con estado activo y luego mutamos en memoria
        p = Personal.objects.create(
            nro_doc='70000099',
            apellidos_nombres='SIN FECHA CESE, X',
            cargo='X',
            tipo_trab='Empleado',
            estado='Activo',
            subarea=subarea,
            fecha_alta=date(2024, 1, 1),
            sueldo_base=Decimal('1500.00'),
        )
        # mutar a Cesado sin fecha_cese
        p.estado = 'Cesado'
        p.fecha_cese = None
        with pytest.raises(ValueError) as excinfo:
            generar_certificado_trabajo(p)
        assert 'fecha_cese' in str(excinfo.value)


# ─── 3. URLs (vistas Django) ─────────────────────────────────────────────────

class TestURLs:
    def test_carta_no_adeudo_requiere_staff(self, client, liquidacion_calculada):
        """Sin login → redirect (staff_member_required)."""
        url = reverse('nominas_carta_no_adeudo_pdf', args=[liquidacion_calculada.pk])
        resp = client.get(url)
        assert resp.status_code in (302, 401, 403)

    def test_carta_no_adeudo_admin_descarga_pdf(self, admin_client, liquidacion_calculada):
        """Admin recibe PDF con content-type application/pdf."""
        url = reverse('nominas_carta_no_adeudo_pdf', args=[liquidacion_calculada.pk])
        resp = admin_client.get(url)
        assert resp.status_code == 200
        assert resp['Content-Type'] == 'application/pdf'
        assert resp.content[:4] == b'%PDF'
        # Disposition: inline con nombre que contenga el DNI
        assert '70000002' in resp['Content-Disposition']

    def test_certificado_trabajo_requiere_staff(self, client, worker_cesado):
        """Sin login → redirect."""
        url = reverse('personal_certificado_trabajo_pdf', args=[worker_cesado.pk])
        resp = client.get(url)
        assert resp.status_code in (302, 401, 403)

    def test_certificado_trabajo_admin_descarga_pdf(self, admin_client, worker_cesado):
        """Admin → PDF válido."""
        url = reverse('personal_certificado_trabajo_pdf', args=[worker_cesado.pk])
        resp = admin_client.get(url)
        assert resp.status_code == 200
        assert resp['Content-Type'] == 'application/pdf'
        assert resp.content[:4] == b'%PDF'

    def test_certificado_trabajo_activo_devuelve_400(self, admin_client, worker_activo):
        """Trabajador activo → la vista retorna 400 (no error 500)."""
        url = reverse('personal_certificado_trabajo_pdf', args=[worker_activo.pk])
        resp = admin_client.get(url)
        assert resp.status_code == 400
        assert b'no est' in resp.content  # 'no está cesado'
