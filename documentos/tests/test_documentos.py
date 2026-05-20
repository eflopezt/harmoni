"""
Tests for the documentos module.

Covers:
- CategoriaDocumento: ordering, active filter
- TipoDocumento: obligatorio flag, vencimiento handling
- PlantillaConstancia: HTML template rendering with context variables
"""
from datetime import date, timedelta

from django.db import IntegrityError
from django.template import Template, Context
from django.test import TestCase

from documentos.models import (
    CategoriaDocumento,
    TipoDocumento,
    PlantillaConstancia,
    DocumentoTrabajador,
)
from personal.models import Area, SubArea, Personal


class _BaseTestCase(TestCase):
    """Shared fixture: creates Personal + Area for FK requirements."""

    @classmethod
    def setUpTestData(cls):
        cls.area = Area.objects.create(nombre="Operaciones")
        cls.subarea = SubArea.objects.create(nombre="Campo", area=cls.area)
        cls.personal = Personal.objects.create(
            nro_doc="87654321",
            apellidos_nombres="Torres Quispe, Maria",
            cargo="Ingeniera de Campo",
            tipo_trab="Empleado",
            subarea=cls.subarea,
            estado="Activo",
        )


# ─────────────────────────────────────────────────────────────
# 1. CategoriaDocumento
# ─────────────────────────────────────────────────────────────

class TestCategoriaDocumento(TestCase):
    """CategoriaDocumento ordering and active filter."""

    def test_create_basic_category(self):
        cat = CategoriaDocumento.objects.create(
            nombre="Contractual",
            icono="fa-file-contract",
            orden=1,
        )
        self.assertTrue(cat.activa)
        self.assertEqual(str(cat), "Contractual")

    def test_ordering_by_orden_then_nombre(self):
        cat_c = CategoriaDocumento.objects.create(nombre="SSOMA", orden=3)
        cat_a = CategoriaDocumento.objects.create(nombre="Contractual", orden=1)
        cat_b = CategoriaDocumento.objects.create(nombre="Legal", orden=2)

        qs = list(CategoriaDocumento.objects.all())
        self.assertEqual(qs[0].pk, cat_a.pk)
        self.assertEqual(qs[1].pk, cat_b.pk)
        self.assertEqual(qs[2].pk, cat_c.pk)

    def test_ordering_same_orden_alphabetical(self):
        cat_b = CategoriaDocumento.objects.create(nombre="Zebra", orden=0)
        cat_a = CategoriaDocumento.objects.create(nombre="Alpha", orden=0)

        qs = list(CategoriaDocumento.objects.all())
        self.assertEqual(qs[0].pk, cat_a.pk)
        self.assertEqual(qs[1].pk, cat_b.pk)

    def test_active_filter(self):
        CategoriaDocumento.objects.create(nombre="Activa 1", activa=True)
        CategoriaDocumento.objects.create(nombre="Activa 2", activa=True)
        CategoriaDocumento.objects.create(nombre="Inactiva", activa=False)

        activas = CategoriaDocumento.objects.filter(activa=True)
        self.assertEqual(activas.count(), 2)

    def test_inactive_excluded(self):
        CategoriaDocumento.objects.create(nombre="Solo Activas", activa=True)
        CategoriaDocumento.objects.create(nombre="Hidden", activa=False)

        inactivas = CategoriaDocumento.objects.filter(activa=False)
        self.assertEqual(inactivas.count(), 1)
        self.assertEqual(inactivas.first().nombre, "Hidden")

    def test_unique_nombre(self):
        CategoriaDocumento.objects.create(nombre="Unica")
        with self.assertRaises(IntegrityError):
            CategoriaDocumento.objects.create(nombre="Unica")

    def test_default_values(self):
        cat = CategoriaDocumento.objects.create(nombre="Defaults")
        self.assertEqual(cat.icono, "fa-folder")
        self.assertEqual(cat.orden, 0)
        self.assertTrue(cat.activa)


# ─────────────────────────────────────────────────────────────
# 2. TipoDocumento
# ─────────────────────────────────────────────────────────────

class TestTipoDocumento(TestCase):
    """TipoDocumento: obligatorio flag and vencimiento handling."""

    @classmethod
    def setUpTestData(cls):
        cls.categoria = CategoriaDocumento.objects.create(
            nombre="SSOMA", orden=1,
        )

    def test_create_basic(self):
        td = TipoDocumento.objects.create(
            nombre="DNI",
            categoria=self.categoria,
        )
        self.assertFalse(td.obligatorio)
        self.assertFalse(td.vence)
        self.assertEqual(str(td), "DNI")

    def test_obligatorio_flag_true(self):
        td = TipoDocumento.objects.create(
            nombre="Contrato de Trabajo",
            categoria=self.categoria,
            obligatorio=True,
        )
        self.assertTrue(td.obligatorio)

    def test_obligatorio_flag_false(self):
        td = TipoDocumento.objects.create(
            nombre="Foto Carnet",
            categoria=self.categoria,
            obligatorio=False,
        )
        self.assertFalse(td.obligatorio)

    def test_vence_flag(self):
        td = TipoDocumento.objects.create(
            nombre="Examen Medico",
            categoria=self.categoria,
            vence=True,
            dias_alerta_vencimiento=60,
        )
        self.assertTrue(td.vence)
        self.assertEqual(td.dias_alerta_vencimiento, 60)

    def test_default_dias_alerta_vencimiento(self):
        td = TipoDocumento.objects.create(
            nombre="SCTR",
            categoria=self.categoria,
            vence=True,
        )
        self.assertEqual(td.dias_alerta_vencimiento, 30)

    def test_aplica_staff_and_rco_defaults(self):
        td = TipoDocumento.objects.create(
            nombre="CV", categoria=self.categoria,
        )
        self.assertTrue(td.aplica_staff)
        self.assertTrue(td.aplica_rco)

    def test_filter_obligatorios(self):
        TipoDocumento.objects.create(
            nombre="Obligatorio 1", categoria=self.categoria, obligatorio=True,
        )
        TipoDocumento.objects.create(
            nombre="Obligatorio 2", categoria=self.categoria, obligatorio=True,
        )
        TipoDocumento.objects.create(
            nombre="Opcional", categoria=self.categoria, obligatorio=False,
        )
        self.assertEqual(
            TipoDocumento.objects.filter(obligatorio=True).count(), 2,
        )

    def test_filter_con_vencimiento(self):
        TipoDocumento.objects.create(
            nombre="Vence 1", categoria=self.categoria, vence=True,
        )
        TipoDocumento.objects.create(
            nombre="No Vence", categoria=self.categoria, vence=False,
        )
        self.assertEqual(
            TipoDocumento.objects.filter(vence=True).count(), 1,
        )

    def test_categoria_can_be_null(self):
        td = TipoDocumento.objects.create(
            nombre="Sin Categoria", categoria=None,
        )
        self.assertIsNone(td.categoria)

    def test_ordering_by_categoria_orden(self):
        cat_late = CategoriaDocumento.objects.create(nombre="ZZ Cat", orden=99)
        cat_early = CategoriaDocumento.objects.create(nombre="AA Cat", orden=0)

        td_late = TipoDocumento.objects.create(
            nombre="Late", categoria=cat_late, orden=0,
        )
        td_early = TipoDocumento.objects.create(
            nombre="Early", categoria=cat_early, orden=0,
        )

        qs = list(TipoDocumento.objects.filter(
            pk__in=[td_late.pk, td_early.pk],
        ))
        self.assertEqual(qs[0].pk, td_early.pk)


# ─────────────────────────────────────────────────────────────
# 3. TipoDocumento + DocumentoTrabajador vencimiento logic
# ─────────────────────────────────────────────────────────────

class TestDocumentoVencimientoAutoEstado(_BaseTestCase):
    """DocumentoTrabajador.save() auto-calculates estado from vencimiento."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.tipo_vence = TipoDocumento.objects.create(
            nombre="Examen Medico",
            vence=True,
            dias_alerta_vencimiento=30,
        )
        cls.tipo_no_vence = TipoDocumento.objects.create(
            nombre="DNI",
            vence=False,
        )

    def test_vigente_when_far_from_expiry(self):
        doc = DocumentoTrabajador(
            personal=self.personal,
            tipo=self.tipo_vence,
            archivo="test.pdf",
            fecha_vencimiento=date.today() + timedelta(days=90),
        )
        doc.save()
        self.assertEqual(doc.estado, "VIGENTE")

    def test_por_vencer_within_alert_window(self):
        doc = DocumentoTrabajador(
            personal=self.personal,
            tipo=self.tipo_vence,
            archivo="test.pdf",
            fecha_vencimiento=date.today() + timedelta(days=15),
        )
        doc.save()
        self.assertEqual(doc.estado, "POR_VENCER")

    def test_vencido_when_past_expiry(self):
        doc = DocumentoTrabajador(
            personal=self.personal,
            tipo=self.tipo_vence,
            archivo="test.pdf",
            fecha_vencimiento=date.today() - timedelta(days=1),
        )
        doc.save()
        self.assertEqual(doc.estado, "VENCIDO")

    def test_no_auto_estado_when_tipo_no_vence(self):
        doc = DocumentoTrabajador(
            personal=self.personal,
            tipo=self.tipo_no_vence,
            archivo="test.pdf",
            fecha_vencimiento=date.today() - timedelta(days=100),
            estado="VIGENTE",
        )
        doc.save()
        # Should NOT auto-change because tipo.vence is False
        self.assertEqual(doc.estado, "VIGENTE")

    def test_boundary_exactly_on_alert_day(self):
        doc = DocumentoTrabajador(
            personal=self.personal,
            tipo=self.tipo_vence,
            archivo="test.pdf",
            fecha_vencimiento=date.today() + timedelta(days=30),
        )
        doc.save()
        # Exactly at boundary: <= dias_alerta means POR_VENCER
        self.assertEqual(doc.estado, "POR_VENCER")

    def test_boundary_one_day_after_alert(self):
        doc = DocumentoTrabajador(
            personal=self.personal,
            tipo=self.tipo_vence,
            archivo="test.pdf",
            fecha_vencimiento=date.today() + timedelta(days=31),
        )
        doc.save()
        self.assertEqual(doc.estado, "VIGENTE")


# ─────────────────────────────────────────────────────────────
# 4. PlantillaConstancia
# ─────────────────────────────────────────────────────────────

class TestPlantillaConstancia(TestCase):
    """PlantillaConstancia model and HTML template rendering."""

    def test_create_basic(self):
        p = PlantillaConstancia.objects.create(
            nombre="Constancia de Trabajo",
            codigo="constancia-trabajo",
            categoria="CONSTANCIA",
            contenido_html="<p>{{ personal.apellidos_nombres }} trabaja en {{ empresa.nombre }}.</p>",
        )
        self.assertTrue(p.activa)
        self.assertEqual(str(p), "Constancia de Trabajo")

    def test_str(self):
        p = PlantillaConstancia.objects.create(
            nombre="Certificado Laboral",
            codigo="cert-laboral",
            contenido_html="body",
        )
        self.assertEqual(str(p), "Certificado Laboral")

    def test_codigo_unique(self):
        PlantillaConstancia.objects.create(
            nombre="A", codigo="unique-slug", contenido_html="x",
        )
        with self.assertRaises(IntegrityError):
            PlantillaConstancia.objects.create(
                nombre="B", codigo="unique-slug", contenido_html="y",
            )

    def test_ordering_by_orden_then_nombre(self):
        p2 = PlantillaConstancia.objects.create(
            nombre="ZZZ", codigo="zzz", contenido_html="b", orden=2,
        )
        p1 = PlantillaConstancia.objects.create(
            nombre="AAA", codigo="aaa", contenido_html="a", orden=1,
        )

        qs = list(PlantillaConstancia.objects.all())
        self.assertEqual(qs[0].pk, p1.pk)
        self.assertEqual(qs[1].pk, p2.pk)

    def test_render_html_with_personal_context(self):
        """Renders contenido_html with personal-like context variables."""
        p = PlantillaConstancia.objects.create(
            nombre="Constancia de Trabajo",
            codigo="constancia-trabajo-render",
            contenido_html=(
                "<div>"
                "<h1>CONSTANCIA DE TRABAJO</h1>"
                "<p>Se certifica que <strong>{{ personal_nombre }}</strong>, "
                "identificado con DNI <strong>{{ personal_dni }}</strong>, "
                "labora en <strong>{{ empresa_nombre }}</strong> "
                "desde el {{ fecha_alta }} desempenando el cargo de "
                "<strong>{{ cargo }}</strong>.</p>"
                "<p>Fecha: {{ hoy }}</p>"
                "</div>"
            ),
        )
        ctx = Context({
            "personal_nombre": "Torres Quispe, Maria",
            "personal_dni": "87654321",
            "empresa_nombre": "Harmoni SAC",
            "fecha_alta": "01/06/2020",
            "cargo": "Ingeniera de Campo",
            "hoy": "17/03/2026",
        })

        rendered = Template(p.contenido_html).render(ctx)

        self.assertIn("Torres Quispe, Maria", rendered)
        self.assertIn("87654321", rendered)
        self.assertIn("Harmoni SAC", rendered)
        self.assertIn("Ingeniera de Campo", rendered)
        self.assertIn("17/03/2026", rendered)

    def test_render_html_with_antiguedad(self):
        p = PlantillaConstancia.objects.create(
            nombre="Constancia Antiguedad",
            codigo="const-antiguedad",
            contenido_html=(
                "<p>{{ personal_nombre }} tiene una antiguedad de {{ antiguedad }}.</p>"
            ),
        )
        ctx = Context({
            "personal_nombre": "Juan Lopez",
            "antiguedad": "5 anios, 3 meses",
        })
        rendered = Template(p.contenido_html).render(ctx)
        self.assertIn("5 anios, 3 meses", rendered)

    def test_render_with_missing_variable_is_blank(self):
        """Missing variables render as empty string (Django default)."""
        p = PlantillaConstancia.objects.create(
            nombre="Sparse",
            codigo="sparse",
            contenido_html="<p>Nombre: {{ nombre }}. Extra: {{ no_existe }}.</p>",
        )
        ctx = Context({"nombre": "Test"})
        rendered = Template(p.contenido_html).render(ctx)
        self.assertIn("Nombre: Test", rendered)
        self.assertIn("Extra: .", rendered)

    def test_categoria_choices(self):
        for code, _ in PlantillaConstancia.CATEGORIA_CHOICES:
            p = PlantillaConstancia.objects.create(
                nombre=f"Cat {code}",
                codigo=f"cat-{code.lower()}",
                categoria=code,
                contenido_html="x",
            )
            self.assertEqual(p.categoria, code)

    def test_active_filter(self):
        PlantillaConstancia.objects.create(
            nombre="Activa", codigo="activa", contenido_html="x", activa=True,
        )
        PlantillaConstancia.objects.create(
            nombre="Inactiva", codigo="inactiva", contenido_html="x", activa=False,
        )
        activas = PlantillaConstancia.objects.filter(activa=True)
        self.assertEqual(activas.count(), 1)
        self.assertEqual(activas.first().codigo, "activa")

    def test_default_categoria_is_constancia(self):
        p = PlantillaConstancia.objects.create(
            nombre="Defaults", codigo="defaults", contenido_html="x",
        )
        self.assertEqual(p.categoria, "CONSTANCIA")

    def test_timestamps_auto_set(self):
        p = PlantillaConstancia.objects.create(
            nombre="Timestamped", codigo="timestamped", contenido_html="x",
        )
        self.assertIsNotNone(p.creado_en)
        self.assertIsNotNone(p.actualizado_en)
