"""
Tests pytest para asistencia/views/reporte_individual.py.

Cubre la lógica de día-de-descanso adaptativa que distingue:
  - Gastronomía / oficina semanal (RCO LOCAL): día libre = DS (no DL),
    día configurable por trabajador via dia_descanso_semanal.
  - Roster acumulativo (FORÁNEO 21×7, 14×7): día libre = DL ganado
    del ciclo.

Bug que motivó esta suite: cliente Sabores del Sur (gastronomía) reportó
que su staff mostraba "DL" en sábados/domingos cuando el régimen real es
6×1 semanal con descanso rotativo (Lun, Mar, Mié, etc. según el turno).
"""
from __future__ import annotations

from datetime import date

import pytest

from asistencia.views.reporte_individual import (
    _auto_ds,
    _dia_descanso_semanal,
    _es_regimen_acumulativo,
)


# ═════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def empresa(db):
    from empresas.models import Empresa
    return Empresa.objects.create(
        razon_social='Test SAC',
        ruc='20000000001',
    )


@pytest.fixture
def gastro_local(db, empresa):
    """Trabajador gastronomía: RCO LOCAL, régimen 6×1 con día libre rotativo."""
    from personal.models import Personal
    return Personal.objects.create(
        apellidos_nombres='CCAMA, Estefani',
        nro_doc='73000099',
        empresa=empresa,
        grupo_tareo='RCO',
        condicion='LOCAL',
        regimen_turno='GASTRO_M',
        estado='Activo',
    )


@pytest.fixture
def oficina_5x2(db, empresa):
    """Oficina admin: RCO LOCAL régimen 5×2 (sat+sun off, pero NO acumulativo)."""
    from personal.models import Personal
    return Personal.objects.create(
        apellidos_nombres='ADMIN, Test',
        nro_doc='73000098',
        empresa=empresa,
        grupo_tareo='RCO',
        condicion='LOCAL',
        regimen_turno='5x2',
        estado='Activo',
    )


@pytest.fixture
def foraneo_21x7(db, empresa):
    """Foráneo minería: RCO FORANEO 21×7 (sí acumulativo, DL legítimo)."""
    from personal.models import Personal
    return Personal.objects.create(
        apellidos_nombres='MINERO, Foraneo',
        nro_doc='73000097',
        empresa=empresa,
        grupo_tareo='RCO',
        condicion='FORANEO',
        regimen_turno='21x7',
        estado='Activo',
    )


@pytest.fixture
def staff_local(db, empresa):
    """Staff oficina Minera Andes: STAFF LOCAL (regimen vacío histórico)
    — recibe DL legítimo por rotaciones foráneas previas."""
    from personal.models import Personal
    return Personal.objects.create(
        apellidos_nombres='STAFF, Test',
        nro_doc='73000096',
        empresa=empresa,
        grupo_tareo='STAFF',
        condicion='LOCAL',
        regimen_turno='',
        estado='Activo',
    )


# ═════════════════════════════════════════════════════════════════════════════
# _es_regimen_acumulativo
# ═════════════════════════════════════════════════════════════════════════════


class TestEsRegimenAcumulativo:
    def test_foraneo_es_acumulativo(self, foraneo_21x7):
        assert _es_regimen_acumulativo(foraneo_21x7) is True

    def test_gastronomia_no_es_acumulativo(self, gastro_local):
        assert _es_regimen_acumulativo(gastro_local) is False

    def test_5x2_no_es_acumulativo(self, oficina_5x2):
        """5×2 (sat+sun off) es semanal fijo, no acumulativo — no genera DL."""
        assert _es_regimen_acumulativo(oficina_5x2) is False

    def test_staff_local_sin_regimen_es_acumulativo(self, staff_local):
        """Compatibilidad: STAFF LOCAL con regimen vacío (Minera) mantiene DL."""
        assert _es_regimen_acumulativo(staff_local) is True

    def test_none_no_es_acumulativo(self):
        assert _es_regimen_acumulativo(None) is False


# ═════════════════════════════════════════════════════════════════════════════
# _dia_descanso_semanal
# ═════════════════════════════════════════════════════════════════════════════


class TestDiaDescansoSemanal:
    def test_default_domingo(self, gastro_local):
        assert _dia_descanso_semanal(gastro_local) == 6

    def test_lunes_configurado(self, gastro_local):
        gastro_local.dia_descanso_semanal = '0'
        gastro_local.save()
        assert _dia_descanso_semanal(gastro_local) == 0

    def test_jueves_configurado(self, gastro_local):
        gastro_local.dia_descanso_semanal = '3'
        gastro_local.save()
        assert _dia_descanso_semanal(gastro_local) == 3

    def test_none_default_domingo(self):
        assert _dia_descanso_semanal(None) == 6

    def test_valor_invalido_cae_a_domingo(self, gastro_local):
        gastro_local.dia_descanso_semanal = 'xx'  # bypasses choice validation
        # No save (would fail validation), solo testear fallback en memoria
        assert _dia_descanso_semanal(gastro_local) == 6


# ═════════════════════════════════════════════════════════════════════════════
# _auto_ds: bug principal — gastronomía no debe mostrar DL
# ═════════════════════════════════════════════════════════════════════════════


class TestAutoDsGastronomia:
    """Bug del cliente: gastronomy worker (sin roster) mostraba DL en weekends.

    Expectativa: DL debe convertirse a DS en RCO LOCAL sin régimen acumulativo.
    """

    def test_dl_sabado_gastro_convierte_a_ds(self, gastro_local):
        # 2026-05-16 = sábado
        assert _auto_ds(date(2026, 5, 16), 'DL', 'LOCAL', gastro_local) == 'DS'

    def test_dl_domingo_gastro_convierte_a_ds(self, gastro_local):
        # 2026-05-17 = domingo
        assert _auto_ds(date(2026, 5, 17), 'DL', 'LOCAL', gastro_local) == 'DS'

    def test_dla_gastro_convierte_a_ds(self, gastro_local):
        assert _auto_ds(date(2026, 5, 16), 'DLA', 'LOCAL', gastro_local) == 'DS'

    def test_fa_sabado_se_mantiene(self, gastro_local):
        """Sábado con FA debe seguir FA si no es su día de descanso."""
        # Default: dia_descanso=Domingo, gastro_local trabaja sábado → FA
        assert _auto_ds(date(2026, 5, 16), 'FA', 'LOCAL', gastro_local) == 'FA'

    def test_fa_domingo_convierte_a_ds(self, gastro_local):
        """Domingo (día descanso default) con FA → DS."""
        assert _auto_ds(date(2026, 5, 17), 'FA', 'LOCAL', gastro_local) == 'DS'

    def test_t_domingo_se_mantiene(self, gastro_local):
        """Si realmente trabajó (T) el domingo, no convertir."""
        assert _auto_ds(date(2026, 5, 17), 'T', 'LOCAL', gastro_local) == 'T'


class TestAutoDsDiaDescansoRotativo:
    """Caso gastronomía: cocinero descansa el martes en vez del domingo."""

    def test_martes_dia_descanso_convierte_fa_a_ds(self, gastro_local):
        gastro_local.dia_descanso_semanal = '1'  # martes
        gastro_local.save()
        # 2026-05-12 = martes
        assert _auto_ds(date(2026, 5, 12), 'FA', 'LOCAL', gastro_local) == 'DS'

    def test_domingo_ya_no_es_descanso(self, gastro_local):
        """Si configuré martes como descanso, domingo es día laborable."""
        gastro_local.dia_descanso_semanal = '1'
        gastro_local.save()
        # 2026-05-17 = domingo
        assert _auto_ds(date(2026, 5, 17), 'FA', 'LOCAL', gastro_local) == 'FA'

    def test_dl_sigue_normalizando_a_ds(self, gastro_local):
        """Sin importar el día configurado, DL siempre se normaliza a DS
        (porque no hay roster acumulativo)."""
        gastro_local.dia_descanso_semanal = '1'
        gastro_local.save()
        assert _auto_ds(date(2026, 5, 16), 'DL', 'LOCAL', gastro_local) == 'DS'


class TestAutoDsForaneo:
    """Régimen acumulativo: DL debe respetarse, no convertirse a DS."""

    def test_dl_foraneo_se_mantiene(self, foraneo_21x7):
        assert _auto_ds(date(2026, 5, 17), 'DL', 'FORANEO', foraneo_21x7) == 'DL'

    def test_dla_foraneo_se_mantiene(self, foraneo_21x7):
        assert _auto_ds(date(2026, 5, 16), 'DLA', 'FORANEO', foraneo_21x7) == 'DLA'


class TestAutoDsStaffLocalMinera:
    """STAFF LOCAL (Minera Andes oficina con DL ganado en rotaciones)
    debe respetar DL — compatibilidad con datos históricos."""

    def test_dl_staff_local_se_mantiene(self, staff_local):
        assert _auto_ds(date(2026, 4, 18), 'DL', 'LOCAL', staff_local) == 'DL'


class TestAutoDsOficina5x2:
    """5×2 (oficina sat+sun off) NO es acumulativo: DL→DS.

    Pero el día de descanso default es domingo, no sábado. Es un caso edge:
    en 5×2 ambos días son libres, pero como solo soportamos UN día de
    descanso semanal, el sábado quedaría como FA salvo que el usuario lo
    marque manualmente. (Mejora futura: soporte multi-día de descanso.)
    """

    def test_dl_5x2_convierte_a_ds(self, oficina_5x2):
        assert _auto_ds(date(2026, 5, 16), 'DL', 'LOCAL', oficina_5x2) == 'DS'

    def test_fa_domingo_5x2_convierte_a_ds(self, oficina_5x2):
        assert _auto_ds(date(2026, 5, 17), 'FA', 'LOCAL', oficina_5x2) == 'DS'


class TestAutoDsSinPersonal:
    """Compatibilidad: si no se pasa personal, _auto_ds debe seguir funcionando
    como antes (domingo LOCAL → DS)."""

    def test_fa_domingo_local_sin_personal(self):
        assert _auto_ds(date(2026, 5, 17), 'FA', 'LOCAL', None) == 'DS'

    def test_fa_sabado_local_sin_personal(self):
        assert _auto_ds(date(2026, 5, 16), 'FA', 'LOCAL', None) == 'FA'

    def test_dl_sin_personal_se_convierte_a_ds(self):
        """Sin personal no podemos saber si es acumulativo → mejor convertir
        DL a DS (default conservador, el caso gastronómico es más común).

        Los callers (_build_staff_data, _build_rco_data) siempre pasan personal,
        así que este caso solo aplica si _auto_ds se invoca aislado.
        """
        assert _auto_ds(date(2026, 5, 17), 'DL', 'LOCAL', None) == 'DS'
