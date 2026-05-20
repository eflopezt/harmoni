"""
Tests for Personal, Area, and SubArea models — personal module.
"""
import pytest
from datetime import date, timedelta

from django.db import IntegrityError

from personal.models import Area, SubArea, Personal


# ────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────

def _make_area(**kwargs):
    defaults = {"nombre": "Operaciones"}
    defaults.update(kwargs)
    return Area.objects.create(**defaults)


def _make_subarea(area=None, **kwargs):
    if area is None:
        area = _make_area()
    defaults = {"nombre": "Campo", "area": area}
    defaults.update(kwargs)
    return SubArea.objects.create(**defaults)


def _make_personal(subarea=None, **kwargs):
    defaults = {
        "nro_doc": "87654321",
        "apellidos_nombres": "LOPEZ GARCIA, CARLOS",
        "cargo": "Ingeniero de Campo",
        "tipo_trab": "Empleado",
        "estado": "Activo",
    }
    if subarea is not None:
        defaults["subarea"] = subarea
    defaults.update(kwargs)
    return Personal.objects.create(**defaults)


# ════════════════════════════════════════════════════════════════
# Area tests
# ════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAreaModel:
    """Tests for the Area model."""

    def test_create_area_basic(self):
        area = _make_area(nombre="Administración", codigo="ADM")
        assert area.pk is not None
        assert area.nombre == "Administración"
        assert area.codigo == "ADM"
        assert area.activa is True

    def test_str_representation(self):
        area = _make_area(nombre="Finanzas")
        assert str(area) == "Finanzas"

    def test_display_nombre_with_codigo(self):
        area = _make_area(nombre="Logística", codigo="LOG")
        assert area.display_nombre == "[LOG] Logística"

    def test_display_nombre_without_codigo(self):
        area = _make_area(nombre="Logística", codigo="")
        assert area.display_nombre == "Logística"

    def test_unique_nombre(self):
        _make_area(nombre="RRHH")
        with pytest.raises(IntegrityError):
            _make_area(nombre="RRHH")

    def test_area_with_responsables(self):
        area = _make_area(nombre="Proyectos")
        p1 = _make_personal(nro_doc="11111111")
        p2 = _make_personal(nro_doc="22222222")
        area.responsables.add(p1, p2)

        assert area.responsables.count() == 2
        assert p1 in area.responsables.all()
        assert p2 in area.responsables.all()

    def test_area_with_jefe(self):
        jefe = _make_personal(nro_doc="33333333")
        area = _make_area(nombre="Ingeniería", jefe_area=jefe)
        assert area.jefe_area == jefe

    def test_area_default_active(self):
        area = _make_area()
        assert area.activa is True

    def test_area_inactive(self):
        area = _make_area(activa=False)
        assert area.activa is False


# ════════════════════════════════════════════════════════════════
# SubArea tests
# ════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestSubAreaModel:
    """Tests for the SubArea model."""

    def test_create_subarea(self):
        area = _make_area(nombre="Operaciones")
        sub = _make_subarea(area=area, nombre="Campo Norte")
        assert sub.pk is not None
        assert sub.area == area
        assert sub.nombre == "Campo Norte"

    def test_str_representation(self):
        area = _make_area(nombre="TI")
        sub = _make_subarea(area=area, nombre="Desarrollo")
        assert str(sub) == "TI - Desarrollo"

    def test_subarea_belongs_to_area(self):
        area = _make_area(nombre="Contabilidad")
        sub = _make_subarea(area=area, nombre="Cuentas por Pagar")
        assert sub.area_id == area.pk
        assert sub in area.subareas.all()

    def test_unique_together_nombre_area(self):
        area = _make_area(nombre="Ventas")
        _make_subarea(area=area, nombre="Canal Directo")
        with pytest.raises(IntegrityError):
            _make_subarea(area=area, nombre="Canal Directo")

    def test_same_name_different_area_ok(self):
        a1 = _make_area(nombre="A1")
        a2 = _make_area(nombre="A2")
        s1 = _make_subarea(area=a1, nombre="General")
        s2 = _make_subarea(area=a2, nombre="General")
        assert s1.pk != s2.pk

    def test_cascade_delete_area(self):
        area = _make_area(nombre="Temporal")
        _make_subarea(area=area, nombre="Temp Sub")
        area_pk = area.pk
        area.delete()
        assert SubArea.objects.filter(area_id=area_pk).count() == 0


# ════════════════════════════════════════════════════════════════
# Personal tests
# ════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPersonalModel:
    """Tests for the Personal model."""

    # ── Creation with required fields ──────────────────────────

    def test_create_employee_required_fields(self):
        p = _make_personal()
        assert p.pk is not None
        assert p.nro_doc == "87654321"
        assert p.apellidos_nombres == "LOPEZ GARCIA, CARLOS"
        assert p.cargo == "Ingeniero de Campo"
        assert p.tipo_trab == "Empleado"

    def test_str_representation(self):
        p = _make_personal()
        assert str(p) == "LOPEZ GARCIA, CARLOS (87654321)"

    def test_unique_nro_doc(self):
        _make_personal(nro_doc="99999999")
        with pytest.raises(IntegrityError):
            _make_personal(nro_doc="99999999")

    # ── apellidos_nombres / nombre_completo property ───────────

    def test_nombre_completo_property(self):
        p = _make_personal(apellidos_nombres="RUIZ DIAZ, MARIA")
        assert p.nombre_completo == "RUIZ DIAZ, MARIA"

    def test_apellidos_nombres_stored_as_given(self):
        p = _make_personal(
            nro_doc="44444444",
            apellidos_nombres="QUISPE HUAMAN, JOSE LUIS",
        )
        assert p.apellidos_nombres == "QUISPE HUAMAN, JOSE LUIS"

    # ── TIPO_CONTRATO_CHOICES ──────────────────────────────────

    def test_tipo_contrato_indefinido(self):
        p = _make_personal(nro_doc="50000001", tipo_contrato="INDEFINIDO")
        assert p.tipo_contrato == "INDEFINIDO"

    def test_tipo_contrato_plazo_fijo(self):
        p = _make_personal(nro_doc="50000002", tipo_contrato="PLAZO_FIJO")
        assert p.tipo_contrato == "PLAZO_FIJO"

    def test_tipo_contrato_obra_servicio(self):
        p = _make_personal(nro_doc="50000003", tipo_contrato="OBRA_SERVICIO")
        assert p.tipo_contrato == "OBRA_SERVICIO"

    def test_tipo_contrato_snp(self):
        p = _make_personal(nro_doc="50000004", tipo_contrato="SNP")
        assert p.tipo_contrato == "SNP"

    def test_tipo_contrato_choices_list(self):
        keys = [k for k, _ in Personal.TIPO_CONTRATO_CHOICES]
        assert "INDEFINIDO" in keys
        assert "PLAZO_FIJO" in keys
        assert "OBRA_SERVICIO" in keys
        assert "SNP" in keys
        assert "PRACTICANTE" in keys

    # ── CONDICION_CHOICES ──────────────────────────────────────

    def test_condicion_foraneo(self):
        p = _make_personal(nro_doc="60000001", condicion="FORANEO")
        assert p.condicion == "FORANEO"

    def test_condicion_local(self):
        p = _make_personal(nro_doc="60000002", condicion="LOCAL")
        assert p.condicion == "LOCAL"

    def test_condicion_lima(self):
        p = _make_personal(nro_doc="60000003", condicion="LIMA")
        assert p.condicion == "LIMA"

    def test_condicion_choices_list(self):
        keys = [k for k, _ in Personal.CONDICION_CHOICES]
        assert keys == ["FORANEO", "LOCAL", "LIMA"]

    def test_condicion_blank_default(self):
        p = _make_personal(nro_doc="60000004")
        assert p.condicion == ""

    # ── fecha_fin_contrato handling ────────────────────────────

    def test_fecha_fin_contrato_null_means_indefinido(self):
        p = _make_personal(nro_doc="70000001", tipo_contrato="INDEFINIDO")
        assert p.fecha_fin_contrato is None
        assert p.dias_para_vencimiento_contrato is None

    def test_fecha_fin_contrato_future(self):
        future = date.today() + timedelta(days=30)
        p = _make_personal(nro_doc="70000002", fecha_fin_contrato=future)
        assert p.fecha_fin_contrato == future
        assert p.dias_para_vencimiento_contrato == 30

    def test_fecha_fin_contrato_past(self):
        past = date.today() - timedelta(days=10)
        p = _make_personal(nro_doc="70000003", fecha_fin_contrato=past)
        assert p.dias_para_vencimiento_contrato == -10

    def test_fecha_fin_contrato_today(self):
        p = _make_personal(nro_doc="70000004", fecha_fin_contrato=date.today())
        assert p.dias_para_vencimiento_contrato == 0

    # ── Estado / esta_activo ───────────────────────────────────

    def test_esta_activo_true(self):
        p = _make_personal(nro_doc="80000001", estado="Activo")
        assert p.esta_activo is True

    def test_esta_activo_false_when_cesado(self):
        p = _make_personal(nro_doc="80000002", estado="Cesado")
        assert p.esta_activo is False

    def test_esta_activo_false_when_suspendido(self):
        p = _make_personal(nro_doc="80000003", estado="Suspendido")
        assert p.esta_activo is False

    # ── es_confianza_o_direccion ───────────────────────────────

    def test_es_confianza(self):
        p = _make_personal(nro_doc="80000004", categoria="CONFIANZA")
        assert p.es_confianza_o_direccion is True

    def test_es_direccion(self):
        p = _make_personal(nro_doc="80000005", categoria="DIRECCION")
        assert p.es_confianza_o_direccion is True

    def test_normal_not_confianza(self):
        p = _make_personal(nro_doc="80000006", categoria="NORMAL")
        assert p.es_confianza_o_direccion is False

    # ── periodo_prueba_meses ───────────────────────────────────

    def test_periodo_prueba_normal(self):
        p = _make_personal(nro_doc="80000007", categoria="NORMAL")
        assert p.periodo_prueba_meses == 3

    def test_periodo_prueba_confianza(self):
        p = _make_personal(nro_doc="80000008", categoria="CONFIANZA")
        assert p.periodo_prueba_meses == 6

    def test_periodo_prueba_direccion(self):
        p = _make_personal(nro_doc="80000009", categoria="DIRECCION")
        assert p.periodo_prueba_meses == 12

    # ── Defaults ───────────────────────────────────────────────

    def test_default_grupo_tareo(self):
        p = _make_personal(nro_doc="90000001")
        assert p.grupo_tareo == "STAFF"

    def test_default_regimen_pension(self):
        p = _make_personal(nro_doc="90000002")
        assert p.regimen_pension == "AFP"

    def test_default_jornada_horas(self):
        p = _make_personal(nro_doc="90000003")
        assert p.jornada_horas == 8

    def test_default_tipo_doc(self):
        p = _make_personal(nro_doc="90000004")
        assert p.tipo_doc == "DNI"
