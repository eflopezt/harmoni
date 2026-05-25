"""
Tests directos para `asistencia.services.he_calculator`.

Cubren la API pública del módulo unificado sin pasar por processor o
calendario (smoke tests aislados que verifican el contrato del módulo).
"""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest

from asistencia.services.he_calculator import (
    CODIGOS_SIN_HE,
    CODIGOS_SIN_HE_UI,
    calcular_he_componentes,
    calcular_he_para_registro,
    obtener_jornada_diaria,
)


CERO = Decimal('0')


# ═════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ═════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def config(db):
    from asistencia.models import ConfiguracionSistema
    cfg = ConfiguracionSistema.get()
    cfg.jornada_local_horas = Decimal('8.5')
    cfg.jornada_sabado_horas = Decimal('5.5')
    cfg.jornada_domingo_horas = Decimal('4.0')
    cfg.jornada_foraneo_horas = Decimal('11.0')
    cfg.he_requiere_solicitud = False
    cfg.save()
    return cfg


@pytest.fixture
def personal_local(db):
    from personal.models import Personal
    return Personal.objects.create(
        nro_doc='80000001',
        apellidos_nombres='HE TEST, ANA',
        cargo='Analista',
        tipo_trab='Empleado',
        estado='Activo',
        grupo_tareo='STAFF',
        condicion='LOCAL',
        fecha_alta=date(2024, 1, 1),
        sueldo_base=Decimal('3000'),
    )


@pytest.fixture
def importacion(db):
    from asistencia.models import TareoImportacion
    return TareoImportacion.objects.create(
        tipo='RELOJ',
        periodo_inicio=date(2026, 4, 22),
        periodo_fin=date(2026, 5, 21),
        archivo_nombre='test_he_calc.xlsx',
        estado='PENDIENTE',
    )


# ═════════════════════════════════════════════════════════════════════════════
# calcular_he_componentes (función pura — sin DB)
# ═════════════════════════════════════════════════════════════════════════════


class TestCalcularHeComponentes:

    def test_he_basico_jornada_local_85(self):
        """LOCAL jornada 8.5h, marcó 11.5h, almuerzo 1h auto → 10.5 ef →
        8.5 normales + 2 HE25."""
        ef, hn, h25, h35, h100 = calcular_he_componentes(
            codigo='T',
            horas_marcadas=Decimal('11.5'),
            jornada_h=Decimal('8.5'),
            es_feriado=False,
            es_ss=False,
            dia_semana=0,  # lunes
        )
        assert ef == Decimal('10.5')
        assert hn == Decimal('8.5')
        assert h25 == Decimal('2.0')
        assert h35 == CERO
        assert h100 == CERO

    def test_he_25_y_35(self):
        """Marcó 14.5h, jornada 8.5h → 13.5 ef → 8.5 norm + 2 HE25 + 3 HE35."""
        ef, hn, h25, h35, h100 = calcular_he_componentes(
            codigo='T',
            horas_marcadas=Decimal('14.5'),
            jornada_h=Decimal('8.5'),
            es_feriado=False,
            dia_semana=1,
        )
        assert ef == Decimal('13.5')
        assert hn == Decimal('8.5')
        assert h25 == Decimal('2.0')
        assert h35 == Decimal('3.0')
        assert h100 == CERO

    def test_feriado_al_100(self):
        """Feriado trabajado → todas las horas al 100%."""
        ef, hn, h25, h35, h100 = calcular_he_componentes(
            codigo='T',
            horas_marcadas=Decimal('9'),
            jornada_h=Decimal('8.5'),
            es_feriado=True,
            dia_semana=4,
        )
        assert ef == Decimal('8.0')   # 9 - 1 (almuerzo)
        assert h100 == Decimal('8.0')
        assert hn == CERO
        assert h25 == CERO
        assert h35 == CERO

    def test_almuerzo_descontado_auto(self):
        """horas_marcadas > 7 y jornada > 6 → descuenta 1h automática."""
        ef, hn, h25, h35, h100 = calcular_he_componentes(
            codigo='T',
            horas_marcadas=Decimal('9.5'),
            jornada_h=Decimal('8.5'),
            es_feriado=False,
            dia_semana=0,
        )
        # 9.5 - 1 (almuerzo auto) = 8.5 ef → todo normal, sin HE
        assert ef == Decimal('8.5')
        assert hn == Decimal('8.5')
        assert h25 == CERO

    def test_almuerzo_manual_override(self):
        """almuerzo_manual=0 → no descuenta nada."""
        ef, hn, h25, h35, h100 = calcular_he_componentes(
            codigo='T',
            horas_marcadas=Decimal('9'),
            jornada_h=Decimal('8.5'),
            es_feriado=False,
            dia_semana=0,
            almuerzo_manual=Decimal('0'),
        )
        # 9 - 0 = 9 ef → 8.5 norm + 0.5 HE25
        assert ef == Decimal('9.0')
        assert hn == Decimal('8.5')
        assert h25 == Decimal('0.5')

    def test_marcacion_incompleta_paga_jornada(self):
        """Marcó 3h con jornada 8.5h (< jornada/2 = 4.25) → SS implícito."""
        ef, hn, h25, h35, h100 = calcular_he_componentes(
            codigo='T',
            horas_marcadas=Decimal('3'),
            jornada_h=Decimal('8.5'),
            es_feriado=False,
            dia_semana=0,
        )
        assert ef == Decimal('8.5')
        assert hn == Decimal('8.5')
        assert h25 == CERO

    def test_ss_dia_normal(self):
        """SS en día normal → paga jornada completa, sin HE."""
        ef, hn, h25, h35, h100 = calcular_he_componentes(
            codigo='SS',
            horas_marcadas=None,
            jornada_h=Decimal('8.5'),
            es_feriado=False,
            es_ss=True,
            dia_semana=0,
        )
        assert ef == Decimal('8.5')
        assert hn == Decimal('8.5')
        assert h100 == CERO

    def test_foraneo_domingo_jornada_4h_exceso_100(self):
        """FORÁNEO domingo (jornada 4h) marcó 5h → 4 normal + 1 HE100."""
        ef, hn, h25, h35, h100 = calcular_he_componentes(
            codigo='T',
            horas_marcadas=Decimal('5'),
            jornada_h=Decimal('4'),
            es_feriado=False,
            dia_semana=6,
        )
        # 5h <= 7 → no almuerzo, ef = 5
        assert ef == Decimal('5.0')
        assert hn == Decimal('4.0')
        assert h100 == Decimal('1.0')

    def test_codigos_sin_he_no_genera_nada(self):
        """VAC, DM, FA, etc. → todo en cero."""
        for codigo in ('VAC', 'DM', 'FA', 'CHE', 'LSG', 'DS'):
            ef, hn, h25, h35, h100 = calcular_he_componentes(
                codigo=codigo,
                horas_marcadas=None,
                jornada_h=Decimal('8.5'),
                es_feriado=False,
                dia_semana=0,
            )
            assert (ef, hn, h25, h35, h100) == (CERO, CERO, CERO, CERO, CERO), (
                f'codigo={codigo} debería ser todo 0'
            )

    def test_he_bloqueado_capa_en_jornada(self):
        """he_bloqueado=True → exceso descartado, capa en jornada."""
        ef, hn, h25, h35, h100 = calcular_he_componentes(
            codigo='T',
            horas_marcadas=Decimal('12'),
            jornada_h=Decimal('8.5'),
            es_feriado=False,
            dia_semana=0,
            he_bloqueado=True,
        )
        # 12 - 1 (alm) = 11 ef, pero bloqueado → 8.5 / 8.5 / 0 / 0 / 0
        assert ef == Decimal('8.5')
        assert hn == Decimal('8.5')
        assert h25 == CERO

    def test_feriado_con_papeleta_comp_es_dia_normal(self):
        """Feriado con papeleta de compensación → trata como día normal."""
        ef, hn, h25, h35, h100 = calcular_he_componentes(
            codigo='T',
            horas_marcadas=Decimal('9'),
            jornada_h=Decimal('8.5'),
            es_feriado=True,
            dia_semana=4,
            tiene_papeleta_comp=True,
        )
        # 9-1 = 8 ef, todo normal, sin HE100
        assert h100 == CERO
        assert hn == Decimal('8.0')


# ═════════════════════════════════════════════════════════════════════════════
# obtener_jornada_diaria
# ═════════════════════════════════════════════════════════════════════════════


class TestObtenerJornadaDiaria:

    def test_local_lunes_85h(self, config):
        # personal=None → usa config
        j = obtener_jornada_diaria(None, 'LOCAL', 0, config, modo='processor')
        assert j == Decimal('8.5')

    def test_local_sabado_55h(self, config):
        j = obtener_jornada_diaria(None, 'LOCAL', 5, config, modo='processor')
        assert j == Decimal('5.5')

    def test_local_domingo_cero(self, config):
        j = obtener_jornada_diaria(None, 'LOCAL', 6, config, modo='processor')
        assert j == CERO

    def test_foraneo_domingo_4h(self, config):
        j = obtener_jornada_diaria(None, 'FORANEO', 6, config, modo='processor')
        assert j == Decimal('4.0')

    def test_foraneo_lunes_11h(self, config):
        j = obtener_jornada_diaria(None, 'FORANEO', 0, config, modo='processor')
        assert j == Decimal('11.0')

    def test_modo_ui_respeta_override_8h(self, config, personal_local):
        """Modo UI: jornada_horas=8 SE aplica como override (#5 fix)."""
        personal_local.jornada_horas = Decimal('8')
        personal_local.save()
        j = obtener_jornada_diaria(
            personal_local, 'LOCAL', 0, config, modo='ui',
        )
        assert j == Decimal('8')

    def test_modo_processor_ignora_override_8h(self, config, personal_local):
        """Modo processor: jornada_horas=8 NO override (default DB)."""
        personal_local.jornada_horas = Decimal('8')
        personal_local.save()
        j = obtener_jornada_diaria(
            personal_local, 'LOCAL', 0, config, modo='processor',
        )
        # Como override no aplica, usa config 8.5
        assert j == Decimal('8.5')


# ═════════════════════════════════════════════════════════════════════════════
# calcular_he_para_registro (integración con DB)
# ═════════════════════════════════════════════════════════════════════════════


class TestCalcularHeParaRegistro:

    def test_turno_noche_overnight(self, db, config, personal_local, importacion):
        """Entrada 22:00, salida 06:00 → 8h marcadas (cruza medianoche).

        El helper `calcular_horas_marcadas_desde_horarios` suma 1 día cuando
        salida < entrada. 22→06 = 8h; con jornada 8.5h y horas_marcadas≤7 no
        descuenta almuerzo → ef=8 todo normal.
        """
        from asistencia.models import RegistroTareo
        reg = RegistroTareo.objects.create(
            importacion=importacion,
            personal=personal_local,
            dni=personal_local.nro_doc,
            fecha=date(2026, 5, 4),   # lunes
            codigo_dia='T',
            grupo='STAFF',
            condicion='LOCAL',
            hora_entrada_real=time(22, 0),
            hora_salida_real=time(6, 0),
            fuente_codigo='RELOJ',
        )
        out = calcular_he_para_registro(reg, config, personal_local)
        assert out['horas_marcadas'] == Decimal('8.0')
        # 8h sin almuerzo (no es > 7? sí es > 7, pero NO > 7? 8>7 True. Jornada 8.5>6 True
        # → descuenta 1h → 7 ef, todo normal
        # Actualizar expectativa: 8 - 1 (almuerzo auto) = 7 ef
        assert out['horas_efectivas'] == Decimal('7.0')
        assert out['horas_normales'] == Decimal('7.0')
        assert out['he_25'] == CERO

    def test_dia_normal_con_he25(self, db, config, personal_local, importacion):
        """LOCAL lunes 07:00-18:30 = 11.5h marcadas → 10.5 ef.

        Personal default jornada_horas=8 (campo modelo). En modo='ui' el
        override se aplica → jornada=8 → norm=8, HE25=2, HE35=0.5.
        Esto valida la diferencia processor vs UI documentada en
        `obtener_jornada_diaria` (modo='ui' respeta override de 8h).
        """
        from asistencia.models import RegistroTareo
        reg = RegistroTareo.objects.create(
            importacion=importacion,
            personal=personal_local,
            dni=personal_local.nro_doc,
            fecha=date(2026, 5, 4),
            codigo_dia='T',
            grupo='STAFF',
            condicion='LOCAL',
            hora_entrada_real=time(7, 0),
            hora_salida_real=time(18, 30),
            fuente_codigo='RELOJ',
        )
        out = calcular_he_para_registro(reg, config, personal_local)
        assert out['horas_efectivas'] == Decimal('10.5')
        assert out['horas_normales'] == Decimal('8.0')
        assert out['he_25'] == Decimal('2.0')
        assert out['he_35'] == Decimal('0.5')
        assert out['he_100'] == CERO
        assert out['jornada_h'] == Decimal('8')

    def test_feriado_via_db_al_100(self, db, config, personal_local, importacion):
        """Reg con es_feriado=False pero FeriadoCalendario tiene la fecha →
        debería detectarlo y aplicar 100%."""
        from asistencia.models import FeriadoCalendario, RegistroTareo
        FeriadoCalendario.objects.create(
            fecha=date(2026, 5, 1),
            nombre='Día del Trabajo',
            tipo='NO_RECUPERABLE',
            activo=True,
        )
        reg = RegistroTareo.objects.create(
            importacion=importacion,
            personal=personal_local,
            dni=personal_local.nro_doc,
            fecha=date(2026, 5, 1),  # viernes feriado
            codigo_dia='T',
            grupo='STAFF',
            condicion='LOCAL',
            hora_entrada_real=time(8, 0),
            hora_salida_real=time(17, 0),  # 9h marcadas
            fuente_codigo='RELOJ',
            es_feriado=False,  # NO seteado en el reg, pero sí en DB
        )
        out = calcular_he_para_registro(reg, config, personal_local)
        # 9 - 1 (almuerzo) = 8 ef → todo al 100%
        assert out['horas_efectivas'] == Decimal('8.0')
        assert out['he_100'] == Decimal('8.0')
        assert out['horas_normales'] == CERO


# ═════════════════════════════════════════════════════════════════════════════
# Sets de códigos
# ═════════════════════════════════════════════════════════════════════════════


class TestCodigoSets:

    def test_codigos_sin_he_ui_extiende_canonico(self):
        """CODIGOS_SIN_HE_UI = CODIGOS_SIN_HE + extras de UI legacy."""
        assert CODIGOS_SIN_HE.issubset(CODIGOS_SIN_HE_UI)
        # Extras UI:
        for extra in ('F', 'V', 'SUB', 'B', 'LIM', 'NA'):
            assert extra in CODIGOS_SIN_HE_UI
            assert extra not in CODIGOS_SIN_HE


# ═════════════════════════════════════════════════════════════════════════════
# Regression / TODO: bug histórico de calendario._recalcular_horas con
# he_bloqueado (faltaba return tras el cap). El refactor lo corrigió porque
# delega en calcular_he_componentes (que SÍ aplica el cap). Documentamos.
# ═════════════════════════════════════════════════════════════════════════════


def test_he_bloqueado_via_componentes_ahora_capea_correctamente():
    """Antes del refactor, calendario._recalcular_horas tenía un bug
    (faltaba `return` en la rama `he_bloqueado`), por lo que el cap
    se sobrescribía y siempre se generaban HE. Ahora el wrapper delega
    en `calcular_he_componentes`, que aplica la regla correctamente.

    En la práctica el bug nunca se activó porque
    `he_requiere_solicitud=False` por default.
    """
    ef, hn, h25, h35, h100 = calcular_he_componentes(
        codigo='T',
        horas_marcadas=Decimal('12'),
        jornada_h=Decimal('8.5'),
        es_feriado=False,
        dia_semana=0,
        he_bloqueado=True,
    )
    assert h25 == CERO
    assert h35 == CERO
    assert hn == Decimal('8.5')
