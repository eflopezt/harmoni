"""
Tests para Legajo Digital — vencimientos auto, PDF, comando, vistas.

Cubre:
- TipoDocumento.vigencia_dias + DocumentoTrabajador.save() auto-calcula fecha_vencimiento
- DocumentoTrabajador.estado_vigencia (VIGENTE / POR_VENCER / VENCIDO)
- Vista legajo responde 200
- Wizard de subida (GET) responde 200
- PDF Legajo se genera y empieza con %PDF
- Comando actualizar_vencimientos actualiza estados
- Vista vencimientos_panel responde 200
"""
from datetime import date, timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from documentos.models import (
    CategoriaDocumento, DocumentoTrabajador, TipoDocumento,
)
from documentos.pdf_legajo import build_legajo_pdf
from personal.models import Area, Personal, SubArea

User = get_user_model()


class _LegajoBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.area = Area.objects.create(nombre='Operaciones')
        cls.subarea = SubArea.objects.create(nombre='Cocina', area=cls.area)
        cls.personal = Personal.objects.create(
            nro_doc='71234567',
            apellidos_nombres='Mamani Quispe, Rosa',
            cargo='Cocinera',
            tipo_trab='Empleado',
            subarea=cls.subarea,
            estado='Activo',
            grupo_tareo='STAFF',
        )
        cls.cat = CategoriaDocumento.objects.create(nombre='SSOMA', orden=4)
        cls.tipo_vence = TipoDocumento.objects.create(
            nombre='Examen Médico',
            categoria=cls.cat,
            vence=True,
            vigencia_dias=365,
            dias_alerta_vencimiento=30,
            obligatorio=True,
        )
        cls.tipo_simple = TipoDocumento.objects.create(
            nombre='DNI',
            categoria=cls.cat,
            vence=False,
            obligatorio=True,
        )
        cls.admin = User.objects.create_superuser(
            username='admin_legajo', password='pwd12345',
            email='admin@example.com',
        )


def _crear_doc(personal, tipo, *, fecha_emision=None, fecha_vencimiento=None, nombre='test.pdf'):
    doc = DocumentoTrabajador(
        personal=personal,
        tipo=tipo,
        fecha_emision=fecha_emision,
        fecha_vencimiento=fecha_vencimiento,
        nombre_archivo=nombre,
    )
    doc.archivo.save(nombre, ContentFile(b'%PDF-1.4\nfake\n%%EOF\n'), save=False)
    doc.save()
    return doc


# ─── Modelo ────────────────────────────────────────────────────────

class TestVencimientoAutoCalc(_LegajoBase):
    """save() auto-calcula fecha_vencimiento si tipo tiene vigencia_dias."""

    def test_calcula_fecha_vencimiento_si_emision_y_vigencia(self):
        emision = date(2026, 1, 1)
        doc = _crear_doc(self.personal, self.tipo_vence, fecha_emision=emision)
        self.assertEqual(doc.fecha_vencimiento, emision + timedelta(days=365))

    def test_no_calcula_si_ya_hay_fecha_vencimiento(self):
        emision = date(2026, 1, 1)
        explicit = date(2026, 6, 30)
        doc = _crear_doc(
            self.personal, self.tipo_vence,
            fecha_emision=emision, fecha_vencimiento=explicit,
        )
        self.assertEqual(doc.fecha_vencimiento, explicit)

    def test_no_calcula_si_tipo_no_vence(self):
        doc = _crear_doc(self.personal, self.tipo_simple, fecha_emision=date(2026, 1, 1))
        self.assertIsNone(doc.fecha_vencimiento)


class TestEstadoVigencia(_LegajoBase):
    """estado_vigencia y dias_para_vencer reflejan correctamente la situación."""

    def test_vigente_si_falta_mucho(self):
        doc = _crear_doc(
            self.personal, self.tipo_vence,
            fecha_vencimiento=date.today() + timedelta(days=180),
        )
        self.assertEqual(doc.estado_vigencia, 'VIGENTE')
        self.assertEqual(doc.estado, 'VIGENTE')

    def test_por_vencer_si_dentro_de_alerta(self):
        doc = _crear_doc(
            self.personal, self.tipo_vence,
            fecha_vencimiento=date.today() + timedelta(days=10),
        )
        self.assertEqual(doc.estado_vigencia, 'POR_VENCER')
        self.assertEqual(doc.estado, 'POR_VENCER')

    def test_vencido_si_ya_paso(self):
        doc = _crear_doc(
            self.personal, self.tipo_vence,
            fecha_vencimiento=date.today() - timedelta(days=5),
        )
        self.assertEqual(doc.estado_vigencia, 'VENCIDO')
        self.assertEqual(doc.estado, 'VENCIDO')

    def test_sin_vencimiento_si_tipo_no_vence(self):
        doc = _crear_doc(self.personal, self.tipo_simple)
        self.assertEqual(doc.estado_vigencia, 'SIN_VENCIMIENTO')

    def test_dias_para_vencer(self):
        doc = _crear_doc(
            self.personal, self.tipo_vence,
            fecha_vencimiento=date.today() + timedelta(days=15),
        )
        self.assertEqual(doc.dias_para_vencer, 15)


# ─── Vistas ───────────────────────────────────────────────────────

class TestVistaLegajo(_LegajoBase):
    def setUp(self):
        self.client = Client()
        self.client.force_login(self.admin)

    def test_legajo_responde_200(self):
        _crear_doc(
            self.personal, self.tipo_vence,
            fecha_emision=date.today() - timedelta(days=30),
        )
        url = reverse('documentos_legajo', kwargs={'personal_id': self.personal.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, self.personal.apellidos_nombres)

    def test_wizard_subida_get_200(self):
        url = reverse('documentos_subir_wizard', kwargs={'personal_pk': self.personal.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Subir')

    def test_vencimientos_panel_200(self):
        _crear_doc(
            self.personal, self.tipo_vence,
            fecha_vencimiento=date.today() + timedelta(days=10),
        )
        url = reverse('documentos_vencimientos')
        resp = self.client.get(url + '?dias=30')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Vencimientos')


class TestVistaPDF(_LegajoBase):
    """El PDF debe empezar con magic bytes %PDF y tener tamaño plausible."""

    def test_pdf_build_directo(self):
        _crear_doc(
            self.personal, self.tipo_vence,
            fecha_emision=date.today() - timedelta(days=10),
        )
        _crear_doc(self.personal, self.tipo_simple, nombre='dni.pdf')
        buf = build_legajo_pdf(self.personal)
        data = buf.getvalue()
        self.assertTrue(data.startswith(b'%PDF'))
        self.assertGreater(len(data), 500)

    def test_pdf_endpoint_200(self):
        c = Client()
        c.force_login(self.admin)
        url = reverse('documentos_legajo_pdf', kwargs={'personal_pk': self.personal.pk})
        resp = c.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))


# ─── Comando management ───────────────────────────────────────────

class TestComandoActualizarVencimientos(_LegajoBase):
    def test_calcula_fechas_y_actualiza_estados(self):
        # Doc con fecha_emision pero sin fecha_vencimiento
        doc_a = DocumentoTrabajador.objects.create(
            personal=self.personal, tipo=self.tipo_vence,
            fecha_emision=date.today() - timedelta(days=400),
            nombre_archivo='a.pdf',
        )
        doc_a.archivo.save('a.pdf', ContentFile(b'%PDF-1.4'), save=False)
        # Forzar a no tener fecha_vencimiento (el save autocalcularía)
        DocumentoTrabajador.objects.filter(pk=doc_a.pk).update(
            fecha_vencimiento=None,
        )

        # Doc vencido
        doc_b = _crear_doc(
            self.personal, self.tipo_vence,
            fecha_vencimiento=date.today() - timedelta(days=5),
        )
        # Doc por vencer
        doc_c = _crear_doc(
            self.personal, self.tipo_vence,
            fecha_vencimiento=date.today() + timedelta(days=10),
        )

        out = StringIO()
        call_command('actualizar_vencimientos', stdout=out)
        salida = out.getvalue()
        self.assertIn('fecha_vencimiento calculada', salida)

        doc_a.refresh_from_db()
        self.assertIsNotNone(doc_a.fecha_vencimiento)

        doc_b.refresh_from_db()
        self.assertEqual(doc_b.estado, 'VENCIDO')

        doc_c.refresh_from_db()
        self.assertEqual(doc_c.estado, 'POR_VENCER')

    def test_dry_run_no_persiste(self):
        doc = _crear_doc(self.personal, self.tipo_vence)
        DocumentoTrabajador.objects.filter(pk=doc.pk).update(
            fecha_emision=date.today() - timedelta(days=400),
            fecha_vencimiento=None,
            estado='VIGENTE',
        )
        out = StringIO()
        call_command('actualizar_vencimientos', '--dry-run', stdout=out)
        self.assertIn('DRY-RUN', out.getvalue())
        doc.refresh_from_db()
        self.assertIsNone(doc.fecha_vencimiento)
