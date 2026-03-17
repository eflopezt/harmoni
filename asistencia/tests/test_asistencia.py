"""
Tests para el modulo de Asistencia (Tareo) de Harmoni ERP.

Cubre:
  - RegimenTurno: ciclos de trabajo/descanso, tipos de jornada, turno nocturno
  - TipoHorario: horas de entrada/salida, salida_dia_siguiente, horas brutas/efectivas
  - ConfiguracionSistema: singleton, valores UIT/RMV, jornadas
  - FeriadoCalendario: feriados 2026 cargados por seed
  - HomologacionCodigo: mapeo de codigos origen -> tareo, tipos de evento

Requiere: python manage.py seed_tareo_inicial (ejecutado en setUpClass)
"""
import datetime
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.test import TestCase

from asistencia.models import (
    ConfiguracionSistema,
    FeriadoCalendario,
    HomologacionCodigo,
    RegimenTurno,
    TipoHorario,
)


@pytest.mark.django_db
class TestSeedCommand(TestCase):
    """Verify the seed command runs without errors and is idempotent."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("seed_tareo_inicial", verbosity=0)

    def test_seed_creates_regimenes(self):
        assert RegimenTurno.objects.count() >= 7

    def test_seed_creates_feriados(self):
        assert FeriadoCalendario.objects.count() == 16

    def test_seed_creates_homologaciones(self):
        assert HomologacionCodigo.objects.count() >= 20

    def test_seed_is_idempotent(self):
        """Running the seed a second time should not duplicate records."""
        count_before = RegimenTurno.objects.count()
        call_command("seed_tareo_inicial", verbosity=0)
        assert RegimenTurno.objects.count() == count_before


# =====================================================================
# RegimenTurno
# =====================================================================

@pytest.mark.django_db
class TestRegimenTurno5x2(TestCase):
    """Local 5x2 regime: standard weekly schedule."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("seed_tareo_inicial", verbosity=0)

    def setUp(self):
        self.regimen = RegimenTurno.objects.get(codigo="5X2")

    def test_dias_trabajo(self):
        assert self.regimen.dias_trabajo_ciclo == 5

    def test_dias_descanso(self):
        assert self.regimen.dias_descanso_ciclo == 2

    def test_ciclo_total(self):
        assert self.regimen.ciclo_total_dias == 7

    def test_jornada_tipo_semanal(self):
        assert self.regimen.jornada_tipo == "SEMANAL"

    def test_no_es_nocturno(self):
        assert self.regimen.es_nocturno is False

    def test_horas_max_ciclo_48(self):
        """5+2=7 dias = 1 semana => max 48h."""
        assert self.regimen.horas_max_ciclo == Decimal("48")

    def test_minutos_almuerzo(self):
        assert self.regimen.minutos_almuerzo == 60

    def test_str_representation(self):
        assert "5X2" in str(self.regimen)


@pytest.mark.django_db
class TestRegimenTurno21x7(TestCase):
    """Foraneo 21x7 regime: accumulative schedule."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("seed_tareo_inicial", verbosity=0)

    def setUp(self):
        self.regimen = RegimenTurno.objects.get(codigo="21X7")

    def test_dias_trabajo(self):
        assert self.regimen.dias_trabajo_ciclo == 21

    def test_dias_descanso(self):
        assert self.regimen.dias_descanso_ciclo == 7

    def test_ciclo_total(self):
        assert self.regimen.ciclo_total_dias == 28

    def test_jornada_tipo_acumulativa(self):
        assert self.regimen.jornada_tipo == "ACUMULATIVA"

    def test_semanas_por_ciclo(self):
        assert self.regimen.semanas_por_ciclo == 4.0

    def test_horas_max_ciclo_192(self):
        """28 dias / 7 = 4 semanas * 48h = 192h."""
        assert self.regimen.horas_max_ciclo == Decimal("192")


@pytest.mark.django_db
class TestRegimenTurno14x7(TestCase):
    """Foraneo 14x7 regime."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("seed_tareo_inicial", verbosity=0)

    def setUp(self):
        self.regimen = RegimenTurno.objects.get(codigo="14X7")

    def test_dias_trabajo(self):
        assert self.regimen.dias_trabajo_ciclo == 14

    def test_dias_descanso(self):
        assert self.regimen.dias_descanso_ciclo == 7

    def test_jornada_tipo_acumulativa(self):
        assert self.regimen.jornada_tipo == "ACUMULATIVA"

    def test_horas_max_ciclo_144(self):
        """21 dias / 7 = 3 semanas * 48h = 144h."""
        assert self.regimen.horas_max_ciclo == Decimal("144")


@pytest.mark.django_db
class TestRegimenTurno10x4(TestCase):
    """Foraneo 10x4 regime."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("seed_tareo_inicial", verbosity=0)

    def setUp(self):
        self.regimen = RegimenTurno.objects.get(codigo="10X4")

    def test_dias_trabajo(self):
        assert self.regimen.dias_trabajo_ciclo == 10

    def test_dias_descanso(self):
        assert self.regimen.dias_descanso_ciclo == 4

    def test_jornada_tipo_acumulativa(self):
        assert self.regimen.jornada_tipo == "ACUMULATIVA"

    def test_horas_max_ciclo_96(self):
        """14 dias / 7 = 2 semanas * 48h = 96."""
        assert self.regimen.horas_max_ciclo == Decimal("96")


@pytest.mark.django_db
class TestRegimenTurnoNocturno(TestCase):
    """Night shift regime: es_nocturno=True, 35% surcharge."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("seed_tareo_inicial", verbosity=0)

    def setUp(self):
        self.regimen = RegimenTurno.objects.get(codigo="TN")

    def test_es_nocturno(self):
        assert self.regimen.es_nocturno is True

    def test_recargo_nocturno_35(self):
        assert self.regimen.recargo_nocturno_pct == Decimal("35.00")

    def test_jornada_tipo_nocturna(self):
        assert self.regimen.jornada_tipo == "NOCTURNA"

    def test_sin_almuerzo(self):
        assert self.regimen.minutos_almuerzo == 0

    def test_dias_trabajo(self):
        assert self.regimen.dias_trabajo_ciclo == 5

    def test_dias_descanso(self):
        assert self.regimen.dias_descanso_ciclo == 2


# =====================================================================
# TipoHorario
# =====================================================================

@pytest.mark.django_db
class TestTipoHorarioLocal(TestCase):
    """Horarios for the 5x2 Local regime."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("seed_tareo_inicial", verbosity=0)

    def setUp(self):
        self.regimen = RegimenTurno.objects.get(codigo="5X2")

    def test_lunes_viernes_entry(self):
        h = TipoHorario.objects.get(regimen=self.regimen, tipo_dia="LUNES_VIERNES")
        assert h.hora_entrada == datetime.time(7, 30)

    def test_lunes_viernes_exit(self):
        h = TipoHorario.objects.get(regimen=self.regimen, tipo_dia="LUNES_VIERNES")
        assert h.hora_salida == datetime.time(17, 0)

    def test_lunes_viernes_not_next_day(self):
        h = TipoHorario.objects.get(regimen=self.regimen, tipo_dia="LUNES_VIERNES")
        assert h.salida_dia_siguiente is False

    def test_lunes_viernes_horas_brutas(self):
        """07:30 to 17:00 = 9.5 hours brutos."""
        h = TipoHorario.objects.get(regimen=self.regimen, tipo_dia="LUNES_VIERNES")
        assert h.horas_brutas == Decimal("9.5")

    def test_lunes_viernes_horas_efectivas(self):
        """9.5h - 1h almuerzo = 8.5h efectivas."""
        h = TipoHorario.objects.get(regimen=self.regimen, tipo_dia="LUNES_VIERNES")
        assert h.horas_efectivas == Decimal("8.5")

    def test_sabado_entry_exit(self):
        h = TipoHorario.objects.get(regimen=self.regimen, tipo_dia="SABADO")
        assert h.hora_entrada == datetime.time(7, 30)
        assert h.hora_salida == datetime.time(13, 0)

    def test_sabado_horas_brutas(self):
        """07:30 to 13:00 = 5.5h brutas."""
        h = TipoHorario.objects.get(regimen=self.regimen, tipo_dia="SABADO")
        assert h.horas_brutas == Decimal("5.5")

    def test_sabado_horas_efectivas(self):
        """5.5h - 1h almuerzo = 4.5h efectivas."""
        h = TipoHorario.objects.get(regimen=self.regimen, tipo_dia="SABADO")
        assert h.horas_efectivas == Decimal("4.5")


@pytest.mark.django_db
class TestTipoHorarioForaneo(TestCase):
    """Horarios for the 21x7 Foraneo regime."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("seed_tareo_inicial", verbosity=0)

    def setUp(self):
        self.regimen = RegimenTurno.objects.get(codigo="21X7")

    def test_lunes_sabado_entry_exit(self):
        h = TipoHorario.objects.get(regimen=self.regimen, tipo_dia="LUNES_SABADO")
        assert h.hora_entrada == datetime.time(7, 30)
        assert h.hora_salida == datetime.time(18, 30)

    def test_lunes_sabado_horas_brutas(self):
        """07:30 to 18:30 = 11h brutas."""
        h = TipoHorario.objects.get(regimen=self.regimen, tipo_dia="LUNES_SABADO")
        assert h.horas_brutas == Decimal("11")

    def test_lunes_sabado_horas_efectivas(self):
        """11h - 1h almuerzo = 10h efectivas."""
        h = TipoHorario.objects.get(regimen=self.regimen, tipo_dia="LUNES_SABADO")
        assert h.horas_efectivas == Decimal("10")

    def test_domingo_entry_exit(self):
        h = TipoHorario.objects.get(regimen=self.regimen, tipo_dia="DOMINGO")
        assert h.hora_entrada == datetime.time(8, 0)
        assert h.hora_salida == datetime.time(12, 0)

    def test_domingo_horas_brutas(self):
        """08:00 to 12:00 = 4h brutas."""
        h = TipoHorario.objects.get(regimen=self.regimen, tipo_dia="DOMINGO")
        assert h.horas_brutas == Decimal("4")


@pytest.mark.django_db
class TestTipoHorarioNocturno(TestCase):
    """Night shift horario: crosses midnight."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("seed_tareo_inicial", verbosity=0)

    def setUp(self):
        self.regimen = RegimenTurno.objects.get(codigo="TN")

    def test_night_shift_entry(self):
        h = TipoHorario.objects.get(regimen=self.regimen, tipo_dia="LUNES_VIERNES")
        assert h.hora_entrada == datetime.time(22, 0)

    def test_night_shift_exit(self):
        h = TipoHorario.objects.get(regimen=self.regimen, tipo_dia="LUNES_VIERNES")
        assert h.hora_salida == datetime.time(6, 0)

    def test_salida_dia_siguiente(self):
        h = TipoHorario.objects.get(regimen=self.regimen, tipo_dia="LUNES_VIERNES")
        assert h.salida_dia_siguiente is True

    def test_horas_brutas_crosses_midnight(self):
        """22:00 to 06:00 next day = 8h brutas."""
        h = TipoHorario.objects.get(regimen=self.regimen, tipo_dia="LUNES_VIERNES")
        assert h.horas_brutas == Decimal("8")

    def test_horas_efectivas_no_almuerzo(self):
        """Night shift has 0 min almuerzo, so efectivas = brutas = 8h."""
        h = TipoHorario.objects.get(regimen=self.regimen, tipo_dia="LUNES_VIERNES")
        assert h.horas_efectivas == Decimal("8")


# =====================================================================
# ConfiguracionSistema (singleton)
# =====================================================================

@pytest.mark.django_db
class TestConfiguracionSistema(TestCase):
    """Verify the singleton ConfiguracionSistema and its default values."""

    def test_singleton_get_or_create(self):
        config = ConfiguracionSistema.get()
        assert config.pk == 1

    def test_singleton_always_pk_1(self):
        """Even if we create a new instance, save forces pk=1."""
        config = ConfiguracionSistema()
        config.empresa_nombre = "Test"
        config.save()
        assert config.pk == 1
        assert ConfiguracionSistema.objects.count() == 1

    def test_uit_default_value(self):
        config = ConfiguracionSistema.get()
        assert config.uit_valor == Decimal("5500.00")

    def test_uit_anno(self):
        config = ConfiguracionSistema.get()
        assert config.uit_anno == 2026

    def test_rmv_default_value(self):
        config = ConfiguracionSistema.get()
        assert config.rmv_valor == Decimal("1130.00")

    def test_jornada_local_horas(self):
        config = ConfiguracionSistema.get()
        assert config.jornada_local_horas == Decimal("8.5")

    def test_jornada_foraneo_horas(self):
        config = ConfiguracionSistema.get()
        assert config.jornada_foraneo_horas == Decimal("11.0")

    def test_str_contains_empresa(self):
        config = ConfiguracionSistema.get()
        result = str(config)
        assert "Configuraci" in result


# =====================================================================
# FeriadoCalendario
# =====================================================================

@pytest.mark.django_db
class TestFeriadoCalendario(TestCase):
    """Verify 2026 Peruvian holidays loaded by seed."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("seed_tareo_inicial", verbosity=0)

    def test_total_feriados_2026(self):
        count = FeriadoCalendario.objects.filter(
            fecha__year=2026
        ).count()
        assert count == 16

    def test_ano_nuevo(self):
        f = FeriadoCalendario.objects.get(fecha=datetime.date(2026, 1, 1))
        assert "Nuevo" in f.nombre
        assert f.tipo == "NO_RECUPERABLE"

    def test_fiestas_patrias_jul_28(self):
        f = FeriadoCalendario.objects.get(fecha=datetime.date(2026, 7, 28))
        assert "Patrias" in f.nombre

    def test_fiestas_patrias_jul_29(self):
        f = FeriadoCalendario.objects.get(fecha=datetime.date(2026, 7, 29))
        assert "Patrias" in f.nombre

    def test_navidad(self):
        f = FeriadoCalendario.objects.get(fecha=datetime.date(2026, 12, 25))
        assert "Navidad" in f.nombre
        assert f.tipo == "NO_RECUPERABLE"

    def test_dia_del_trabajo(self):
        f = FeriadoCalendario.objects.get(fecha=datetime.date(2026, 5, 1))
        assert "Trabajo" in f.nombre

    def test_santa_rosa(self):
        f = FeriadoCalendario.objects.get(fecha=datetime.date(2026, 8, 30))
        assert "Santa Rosa" in f.nombre

    def test_all_non_recuperable(self):
        """All 2026 holidays from seed are NO_RECUPERABLE."""
        all_nr = FeriadoCalendario.objects.filter(
            fecha__year=2026,
            tipo="NO_RECUPERABLE",
        ).count()
        assert all_nr == 16

    def test_str_representation(self):
        f = FeriadoCalendario.objects.get(fecha=datetime.date(2026, 1, 1))
        s = str(f)
        assert "2026-01-01" in s
        assert "Nuevo" in s


# =====================================================================
# HomologacionCodigo
# =====================================================================

@pytest.mark.django_db
class TestHomologacionCodigo(TestCase):
    """Verify code mapping table loaded by seed."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("seed_tareo_inicial", verbosity=0)

    def test_b_maps_to_dl(self):
        """'B' (bajada) maps to tareo code 'DL' (dia libre)."""
        h = HomologacionCodigo.objects.get(codigo_origen="B")
        assert h.codigo_tareo == "DL"
        assert h.codigo_roster == "DL"
        assert h.tipo_evento == "DESCANSO"

    def test_positive_hours_maps_to_a(self):
        """'>0' (positive numeric hours) maps to tareo code 'A' (asistencia)."""
        h = HomologacionCodigo.objects.get(codigo_origen=">0")
        assert h.codigo_tareo == "A"
        assert h.codigo_roster == "T"
        assert h.tipo_evento == "ASISTENCIA"
        assert h.es_numerico is True
        assert h.genera_he is True

    def test_zero_is_falta(self):
        """'0' (zero hours) maps to 'FALTA' = ausencia."""
        h = HomologacionCodigo.objects.get(codigo_origen="0")
        assert h.codigo_tareo == "FALTA"
        assert h.tipo_evento == "AUSENCIA"
        assert h.signo == "-"
        assert h.cuenta_asistencia is False

    def test_blank_is_ausencia(self):
        """'BLANK' (no data) maps to 'F' = falta/ausencia."""
        h = HomologacionCodigo.objects.get(codigo_origen="BLANK")
        assert h.codigo_tareo == "F"
        assert h.tipo_evento == "AUSENCIA"
        assert h.signo == "-"

    def test_vacaciones_code(self):
        h = HomologacionCodigo.objects.get(codigo_origen="V")
        assert h.codigo_tareo == "VAC"
        assert h.tipo_evento == "VACACIONES"
        assert h.signo == "+"

    def test_descanso_medico(self):
        h = HomologacionCodigo.objects.get(codigo_origen="DM")
        assert h.codigo_tareo == "DM"
        assert h.tipo_evento == "DESCANSO_MEDICO"

    def test_feriado_no_laborado(self):
        h = HomologacionCodigo.objects.get(codigo_origen="FR")
        assert h.codigo_tareo == "FR"
        assert h.tipo_evento == "FERIADO"

    def test_feriado_laborado(self):
        h = HomologacionCodigo.objects.get(codigo_origen="FL")
        assert h.codigo_tareo == "FL"
        assert h.tipo_evento == "FERIADO_LABORADO"
        assert h.genera_he is True

    def test_suspension_signo_negativo(self):
        h = HomologacionCodigo.objects.get(codigo_origen="AS")
        assert h.codigo_tareo == "F"
        assert h.tipo_evento == "SUSPENSION"
        assert h.signo == "-"
        assert h.cuenta_asistencia is False

    def test_teletrabajo(self):
        h = HomologacionCodigo.objects.get(codigo_origen="TR")
        assert h.codigo_tareo == "TR"
        assert h.tipo_evento == "TELETRABAJO"
        assert h.cuenta_asistencia is True

    def test_prioridad_papeletas_highest(self):
        """Papeleta codes (CHE, CPF, CDT) have priority 1 (highest)."""
        papeletas = HomologacionCodigo.objects.filter(
            codigo_origen__in=["CHE", "CPF", "CDT"]
        )
        for p in papeletas:
            assert p.prioridad == 1

    def test_prioridad_falta_lowest(self):
        """Falta/blank codes have priority 99 (lowest)."""
        faltas = HomologacionCodigo.objects.filter(
            codigo_origen__in=["0", "BLANK"]
        )
        for f in faltas:
            assert f.prioridad == 99

    def test_str_representation(self):
        h = HomologacionCodigo.objects.get(codigo_origen="B")
        s = str(h)
        assert "B" in s
        assert "DL" in s


# =====================================================================
# RegimenTurno model validation
# =====================================================================

@pytest.mark.django_db
class TestRegimenTurnoValidation(TestCase):
    """Test model-level validation on RegimenTurno."""

    def test_clean_rejects_zero_work_days(self):
        r = RegimenTurno(
            nombre="Test Zero",
            codigo="T0",
            dias_trabajo_ciclo=0,
            dias_descanso_ciclo=2,
        )
        from django.core.exceptions import ValidationError
        with pytest.raises(ValidationError):
            r.clean()

    def test_clean_accepts_valid(self):
        r = RegimenTurno(
            nombre="Test Valid",
            codigo="TV",
            dias_trabajo_ciclo=5,
            dias_descanso_ciclo=2,
        )
        # Should not raise
        r.clean()
