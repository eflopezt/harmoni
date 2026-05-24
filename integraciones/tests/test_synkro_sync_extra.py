"""Tests adicionales para integraciones.services.synkro_sync.

Plan estabilización Q2 2026: subir cobertura del módulo de sync con Synkro
(BD SQL Server remota, modelos `managed=False`) por encima del 50%.

Los modelos PerPersona/PPersonal/PicadoPersonal/FeriadoSynkro/PermisoLicencia
viven en una connection 'synkro' que no existe en el entorno de tests, así
que se mockean vía `unittest.mock.patch` sobre los nombres importados en el
módulo `synkro_sync`.
"""
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from integraciones.services import synkro_sync as ss
from integraciones.services.synkro_sync import (
    FUENTES_REESCRIBIBLES,
    MOTIVO_CESE_MAP,
    TIPO_PERMISO_MAP,
    TIPO_TRAB_EMPLEADO,
    TIPO_TRAB_OBRERO,
    _build_personal_index_por_dni,
    _build_synkro_personal_to_dni,
    _mapear_motivo_cese,
    _normalizar_dni,
    _ultimo_cursor,
    run_sync,
    sync_feriados,
    sync_papeletas,
    sync_personal,
    sync_picados,
)


# El signal post_save de RegistroPapeleta dispara aplicar_papeleta() que
# crea RegistroTareo con TareoImportacion cacheada a nivel módulo. En tests
# eso causa orphan FKs en cleanup. Desactivamos la sincronización automática
# durante todos los tests de este módulo (el sync de Synkro no la requiere
# para validar sus métricas).
@pytest.fixture(autouse=True)
def _disable_papeleta_signal_and_reset_caches():
    from django.db.models.signals import post_save
    from asistencia.signals import badge_papeleta
    from asistencia.services import papeletas_sync as ps_mod

    post_save.disconnect(badge_papeleta, sender='tareo.RegistroPapeleta')
    # Resetear caches módulo-level para evitar PKs huérfanos cross-test
    if hasattr(ps_mod, '_imp_cache'):
        ps_mod._imp_cache['imp'] = None
    if hasattr(ps_mod, '_feriados_cache_data'):
        ps_mod._feriados_cache_data['set'] = None
        ps_mod._feriados_cache_data['year_range'] = None
    if hasattr(ps_mod, '_cerrados_cache_data'):
        ps_mod._cerrados_cache_data['set'] = None
    try:
        yield
    finally:
        post_save.connect(badge_papeleta, sender='tareo.RegistroPapeleta')


# ════════════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════════════

def _personal(**kwargs):
    """Crea un Personal con defaults válidos. Los tests modifican lo que
    necesiten via kwargs."""
    from personal.models import Personal
    defaults = {
        'nro_doc': '12345678',
        'apellidos_nombres': 'TEST APELLIDO, NOMBRE',
        'cargo': 'Operador',
        'tipo_trab': 'Empleado',
        'estado': 'Activo',
    }
    defaults.update(kwargs)
    return Personal.objects.create(**defaults)


def _make_synkro_queryset(rows):
    """Devuelve un MagicMock que se comporta como un QuerySet de Django:
    soporta .filter(...).values_list(...) y .filter(...).values(...) y
    .all() y iteración."""
    qs = MagicMock()
    # Por defecto cualquier .filter() retorna el mismo mock encadenable
    qs.filter.return_value = qs
    qs.order_by.return_value = qs
    qs.values.return_value = list(rows) if rows and isinstance(rows[0], dict) else rows
    qs.values_list.return_value = rows
    qs.all.return_value = rows
    qs.__iter__ = lambda self: iter(rows)
    qs.iterator.return_value = iter(rows)
    return qs


def _synkro_manager(rows):
    """Imita `Model.objects.using('synkro')` retornando un QuerySet falso."""
    manager = MagicMock()
    qs = _make_synkro_queryset(rows)
    manager.using = MagicMock(return_value=qs)
    return manager, qs


# ════════════════════════════════════════════════════════════════════════
# Funciones puras (sin DB ni mocks)
# ════════════════════════════════════════════════════════════════════════


class TestNormalizarDni:
    def test_none_devuelve_string_vacio(self):
        assert _normalizar_dni(None) == ''

    def test_string_vacio_devuelve_vacio(self):
        assert _normalizar_dni('') == ''

    def test_strip_espacios(self):
        assert _normalizar_dni('  12345678  ') == '12345678'

    def test_conserva_prefijo_ceros_extranjero(self):
        """Los CE/extranjeros usan prefijo '00' — debe conservarse."""
        assert _normalizar_dni('0012345') == '0012345'

    def test_acepta_int_y_lo_castea(self):
        assert _normalizar_dni(12345678) == '12345678'


class TestMapearMotivoCese:
    @pytest.mark.parametrize('texto,esperado', [
        ('Renuncia Voluntaria', 'RENUNCIA'),
        ('renuncia', 'RENUNCIA'),
        ('Mutuo Acuerdo', 'MUTUO_ACUERDO'),
        ('Jubilación', 'JUBILACION'),
        ('Vencimiento de contrato', 'VENCIMIENTO'),
        ('Termino de Contrato', 'TERMINO_CONTRATO'),
        ('Término de contrato', 'TERMINO_CONTRATO'),
        ('termino contrato', 'TERMINO_CONTRATO'),
        ('No renovación', 'NO_RENOVACION'),
        ('Despido con causa', 'DESPIDO_CAUSA'),
        ('Positivo alcotest en sangre', 'DESPIDO_CAUSA'),
        ('Cese colectivo', 'CESE_COLECTIVO'),
        ('Liquidación de empresa', 'LIQUIDACION'),
        ('Fallecimiento', 'FALLECIMIENTO'),
        ('Invalidez permanente', 'INVALIDEZ'),
        ('Abandono de trabajo', 'ABANDONO'),
        ('No inicio labores', 'OTRO'),
        ('termino de partida', 'VENCIMIENTO'),
    ])
    def test_motivos_conocidos(self, texto, esperado):
        assert _mapear_motivo_cese(texto) == esperado

    def test_texto_vacio_devuelve_vacio(self):
        assert _mapear_motivo_cese('') == ''

    def test_none_devuelve_vacio(self):
        assert _mapear_motivo_cese(None) == ''

    def test_texto_no_reconocido_devuelve_otro(self):
        assert _mapear_motivo_cese('Razón inventada xyz') == 'OTRO'

    def test_case_insensitive(self):
        assert _mapear_motivo_cese('RENUNCIA VOLUNTARIA') == 'RENUNCIA'
        assert _mapear_motivo_cese('renuncia voluntaria') == 'RENUNCIA'

    def test_match_parcial_en_oracion(self):
        """El matcher hace substring 'in' — un sustring largo aún matchea."""
        assert _mapear_motivo_cese('Se procedió a la renuncia formal') == 'RENUNCIA'


class TestConstantes:
    def test_tipo_permiso_map_cubre_todos_los_ids_synkro(self):
        """Documenta el mapeo Synkro→Harmoni de tipos de permiso."""
        assert TIPO_PERMISO_MAP[1] == 'DESCANSO_MEDICO'
        assert TIPO_PERMISO_MAP[4] == 'VACACIONES'
        assert TIPO_PERMISO_MAP[15] is None  # FR — se ignora
        # Asegurar todas las claves esperadas
        assert set(TIPO_PERMISO_MAP.keys()) == set(range(1, 18))

    def test_tipo_trabajador_constantes(self):
        assert TIPO_TRAB_EMPLEADO == 3
        assert TIPO_TRAB_OBRERO == 2

    def test_fuentes_reescribibles_incluye_reloj_y_falta_auto(self):
        assert 'RELOJ' in FUENTES_REESCRIBIBLES
        assert 'FALTA_AUTO' in FUENTES_REESCRIBIBLES
        # Las protegidas NO deben estar
        assert 'MANUAL' not in FUENTES_REESCRIBIBLES
        assert 'PAPELETA' not in FUENTES_REESCRIBIBLES
        assert 'EXCEL' not in FUENTES_REESCRIBIBLES

    def test_motivo_cese_map_es_lista_de_tuplas(self):
        assert isinstance(MOTIVO_CESE_MAP, list)
        for needle, canon in MOTIVO_CESE_MAP:
            assert isinstance(needle, str)
            assert isinstance(canon, str)


# ════════════════════════════════════════════════════════════════════════
# Funciones que tocan la BD 'default' (Personal de Harmoni)
# ════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestBuildPersonalIndexPorDni:
    def test_devuelve_dict_dni_a_id(self):
        p1 = _personal(nro_doc='10000001')
        p2 = _personal(nro_doc='10000002', apellidos_nombres='OTRO, X')
        idx = _build_personal_index_por_dni()
        assert idx['10000001'] == p1.id
        assert idx['10000002'] == p2.id

    def test_excluye_dni_vacio(self):
        # nro_doc tiene unique=True; el ORM no permite múltiples '' pero sí None
        # solo no debe explotar si existen filas con nro_doc nulo
        p1 = _personal(nro_doc='10000003')
        idx = _build_personal_index_por_dni()
        assert idx == {'10000003': p1.id}

    def test_normaliza_strip(self):
        # Insertamos con espacios intencionales — el index normaliza
        p = _personal(nro_doc=' 12345678 ')
        idx = _build_personal_index_por_dni()
        # Después de strip, la key es '12345678'
        assert idx['12345678'] == p.id


@pytest.mark.django_db
class TestBuildSynkroPersonalToDni:
    def test_join_personas_y_personal(self):
        """Simula los QuerySets de PPersonal y PerPersona."""
        # PPersonal.objects.using('synkro').filter(...).values_list('id_personal', 'id_persona')
        pp_rows = [(100, 200), (101, 201)]
        # PerPersona.objects.using('synkro').filter(...).values_list('id_persona', 'dni')
        per_rows = [(200, '11111111'), (201, '22222222')]

        with patch.object(ss, 'PPersonal') as pp_mock, \
             patch.object(ss, 'PerPersona') as per_mock:
            pp_qs = MagicMock()
            pp_qs.filter.return_value = pp_qs
            pp_qs.values_list.return_value = pp_rows
            pp_mock.objects.using.return_value = pp_qs

            per_qs = MagicMock()
            per_qs.filter.return_value = per_qs
            per_qs.values_list.return_value = per_rows
            per_mock.objects.using.return_value = per_qs

            result = _build_synkro_personal_to_dni(solo_empleados=True)

        assert result == {100: '11111111', 101: '22222222'}

    def test_solo_empleados_filtra_obreros(self):
        """Cuando solo_empleados=True, .filter(id_tipo_trabajador=3) se llama."""
        with patch.object(ss, 'PPersonal') as pp_mock, \
             patch.object(ss, 'PerPersona') as per_mock:
            pp_qs = MagicMock()
            pp_qs.filter.return_value = pp_qs
            pp_qs.values_list.return_value = []
            pp_mock.objects.using.return_value = pp_qs

            per_qs = MagicMock()
            per_qs.filter.return_value = per_qs
            per_qs.values_list.return_value = []
            per_mock.objects.using.return_value = per_qs

            _build_synkro_personal_to_dni(solo_empleados=True)

            pp_qs.filter.assert_called_once_with(
                id_tipo_trabajador=TIPO_TRAB_EMPLEADO,
            )

    def test_solo_empleados_false_no_filtra(self):
        with patch.object(ss, 'PPersonal') as pp_mock, \
             patch.object(ss, 'PerPersona') as per_mock:
            pp_qs = MagicMock()
            pp_qs.values_list.return_value = []
            pp_mock.objects.using.return_value = pp_qs

            per_qs = MagicMock()
            per_qs.filter.return_value = per_qs
            per_qs.values_list.return_value = []
            per_mock.objects.using.return_value = per_qs

            _build_synkro_personal_to_dni(solo_empleados=False)

            # No se llamó .filter() porque solo_empleados es False
            pp_qs.filter.assert_not_called()

    def test_dni_faltante_en_per_persona_queda_vacio(self):
        """Si un id_persona de PPersonal no está en PerPersona, dni → ''."""
        pp_rows = [(100, 200), (101, 201)]
        per_rows = [(200, '11111111')]  # falta el 201

        with patch.object(ss, 'PPersonal') as pp_mock, \
             patch.object(ss, 'PerPersona') as per_mock:
            pp_qs = MagicMock()
            pp_qs.filter.return_value = pp_qs
            pp_qs.values_list.return_value = pp_rows
            pp_mock.objects.using.return_value = pp_qs

            per_qs = MagicMock()
            per_qs.filter.return_value = per_qs
            per_qs.values_list.return_value = per_rows
            per_mock.objects.using.return_value = per_qs

            result = _build_synkro_personal_to_dni()

        assert result == {100: '11111111', 101: ''}


# ════════════════════════════════════════════════════════════════════════
# sync_feriados
# ════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestSyncFeriados:
    def test_crea_feriados_nuevos(self):
        from asistencia.models import FeriadoCalendario
        # Mock FeriadoSynkro.objects.using('synkro').all()
        feriados_syk = [
            MagicMock(fecha=date(2026, 7, 28), descripcion='Fiestas Patrias'),
            MagicMock(fecha=date(2026, 7, 29), descripcion='Día del Ejército'),
        ]
        with patch.object(ss, 'FeriadoSynkro') as fs_mock:
            qs = MagicMock()
            qs.all.return_value = feriados_syk
            fs_mock.objects.using.return_value = qs

            creados = sync_feriados()

        assert creados == 2
        assert FeriadoCalendario.objects.filter(fecha=date(2026, 7, 28)).exists()
        assert FeriadoCalendario.objects.filter(fecha=date(2026, 7, 29)).exists()

    def test_no_duplica_feriados_existentes(self):
        from asistencia.models import FeriadoCalendario
        FeriadoCalendario.objects.create(
            fecha=date(2026, 7, 28), nombre='Fiestas Patrias YA', activo=True,
        )
        feriados_syk = [
            MagicMock(fecha=date(2026, 7, 28), descripcion='Fiestas Patrias'),
            MagicMock(fecha=date(2026, 7, 29), descripcion='Día del Ejército'),
        ]
        with patch.object(ss, 'FeriadoSynkro') as fs_mock:
            qs = MagicMock()
            qs.all.return_value = feriados_syk
            fs_mock.objects.using.return_value = qs

            creados = sync_feriados()

        # Solo crea uno (el 29) — el 28 ya existía
        assert creados == 1
        assert FeriadoCalendario.objects.count() == 2

    def test_descripcion_vacia_usa_default(self):
        from asistencia.models import FeriadoCalendario
        feriados_syk = [
            MagicMock(fecha=date(2026, 5, 1), descripcion=None),
        ]
        with patch.object(ss, 'FeriadoSynkro') as fs_mock:
            qs = MagicMock()
            qs.all.return_value = feriados_syk
            fs_mock.objects.using.return_value = qs

            sync_feriados()

        fer = FeriadoCalendario.objects.get(fecha=date(2026, 5, 1))
        assert fer.nombre == 'Feriado'

    def test_truncar_nombre_a_150_chars(self):
        from asistencia.models import FeriadoCalendario
        nombre_largo = 'X' * 300
        feriados_syk = [
            MagicMock(fecha=date(2026, 6, 29), descripcion=nombre_largo),
        ]
        with patch.object(ss, 'FeriadoSynkro') as fs_mock:
            qs = MagicMock()
            qs.all.return_value = feriados_syk
            fs_mock.objects.using.return_value = qs
            sync_feriados()

        fer = FeriadoCalendario.objects.get(fecha=date(2026, 6, 29))
        assert len(fer.nombre) == 150

    def test_sin_feriados_synkro_retorna_cero(self):
        with patch.object(ss, 'FeriadoSynkro') as fs_mock:
            qs = MagicMock()
            qs.all.return_value = []
            fs_mock.objects.using.return_value = qs

            creados = sync_feriados()

        assert creados == 0


# ════════════════════════════════════════════════════════════════════════
# sync_personal
# ════════════════════════════════════════════════════════════════════════


def _make_pp_qs_values(rows):
    """Helper: rows es lista de dicts → mock que soporta
    .filter().values(...)"""
    qs = MagicMock()
    qs.filter.return_value = qs
    qs.values.return_value = rows
    return qs


@pytest.mark.django_db
class TestSyncPersonal:
    def test_crea_personal_nuevo_desde_synkro(self):
        from personal.models import Personal
        pp_rows = [
            {
                'id_personal': 100, 'id_persona': 200, 'estado': True,
                'fecha_ingreso': date(2025, 1, 15),
                'fecha_termino_contrato': None,
                'motivo_cese': '',
            },
        ]
        per_rows = [
            {
                'id_persona': 200, 'dni': '99887766',
                'a_paterno': 'MARQUEZ', 'a_materno': 'LOPEZ',
                'nombres': 'JUAN CARLOS', 'nombre_completo': '',
                'celular': '987654321',
            },
        ]
        with patch.object(ss, 'PPersonal') as pp_mock, \
             patch.object(ss, 'PerPersona') as per_mock:
            pp_qs = MagicMock()
            pp_qs.filter.return_value = pp_qs
            pp_qs.values.return_value = pp_rows
            pp_mock.objects.using.return_value = pp_qs

            per_qs = MagicMock()
            per_qs.filter.return_value = per_qs
            per_qs.values.return_value = per_rows
            per_mock.objects.using.return_value = per_qs

            result = sync_personal()

        assert result['altas_creadas'] == 1
        nuevo = Personal.objects.get(nro_doc='99887766')
        assert nuevo.fecha_alta == date(2025, 1, 15)
        assert nuevo.celular == '987654321'
        assert nuevo.estado == 'Activo'

    def test_omite_alta_sin_fecha_ingreso(self):
        pp_rows = [
            {
                'id_personal': 100, 'id_persona': 200, 'estado': True,
                'fecha_ingreso': None,  # ← sin fecha_ingreso
                'fecha_termino_contrato': None, 'motivo_cese': '',
            },
        ]
        per_rows = [
            {
                'id_persona': 200, 'dni': '11122233',
                'a_paterno': 'X', 'a_materno': 'Y', 'nombres': 'Z',
                'nombre_completo': '', 'celular': '',
            },
        ]
        with patch.object(ss, 'PPersonal') as pp_mock, \
             patch.object(ss, 'PerPersona') as per_mock:
            pp_qs = MagicMock()
            pp_qs.filter.return_value = pp_qs
            pp_qs.values.return_value = pp_rows
            pp_mock.objects.using.return_value = pp_qs

            per_qs = MagicMock()
            per_qs.filter.return_value = per_qs
            per_qs.values.return_value = per_rows
            per_mock.objects.using.return_value = per_qs

            result = sync_personal()

        assert result['altas_creadas'] == 0
        assert result['altas_omitidas_sin_datos'] == 1

    def test_omite_alta_sin_nombre(self):
        pp_rows = [
            {
                'id_personal': 100, 'id_persona': 200, 'estado': True,
                'fecha_ingreso': date(2025, 1, 1),
                'fecha_termino_contrato': None, 'motivo_cese': '',
            },
        ]
        per_rows = [
            {
                'id_persona': 200, 'dni': '33344455',
                'a_paterno': '', 'a_materno': '', 'nombres': '',
                'nombre_completo': '', 'celular': '',
            },
        ]
        with patch.object(ss, 'PPersonal') as pp_mock, \
             patch.object(ss, 'PerPersona') as per_mock:
            pp_qs = MagicMock()
            pp_qs.filter.return_value = pp_qs
            pp_qs.values.return_value = pp_rows
            pp_mock.objects.using.return_value = pp_qs

            per_qs = MagicMock()
            per_qs.filter.return_value = per_qs
            per_qs.values.return_value = per_rows
            per_mock.objects.using.return_value = per_qs

            result = sync_personal()
        assert result['altas_omitidas_sin_datos'] == 1

    def test_actualiza_cese_con_fecha_termino(self):
        from personal.models import Personal
        existente = _personal(
            nro_doc='55566677', estado='Activo', fecha_cese=None,
        )
        pp_rows = [
            {
                'id_personal': 100, 'id_persona': 200, 'estado': False,
                'fecha_ingreso': date(2024, 1, 1),
                'fecha_termino_contrato': date(2026, 5, 20),
                'motivo_cese': 'Renuncia voluntaria',
            },
        ]
        per_rows = [
            {
                'id_persona': 200, 'dni': '55566677',
                'a_paterno': 'X', 'a_materno': 'Y', 'nombres': 'Z',
                'nombre_completo': 'X Y, Z', 'celular': '',
            },
        ]
        with patch.object(ss, 'PPersonal') as pp_mock, \
             patch.object(ss, 'PerPersona') as per_mock:
            pp_qs = MagicMock()
            pp_qs.filter.return_value = pp_qs
            pp_qs.values.return_value = pp_rows
            pp_mock.objects.using.return_value = pp_qs

            per_qs = MagicMock()
            per_qs.filter.return_value = per_qs
            per_qs.values.return_value = per_rows
            per_mock.objects.using.return_value = per_qs

            result = sync_personal()

        existente.refresh_from_db()
        assert result['ceses_actualizados'] == 1
        assert existente.fecha_cese == date(2026, 5, 20)
        assert existente.motivo_cese == 'RENUNCIA'
        assert existente.estado == 'Cesado'

    def test_actualiza_fecha_ingreso_si_estaba_vacia(self):
        from personal.models import Personal
        existente = _personal(
            nro_doc='77788899', fecha_alta=None,
        )
        pp_rows = [
            {
                'id_personal': 100, 'id_persona': 200, 'estado': True,
                'fecha_ingreso': date(2024, 3, 15),
                'fecha_termino_contrato': None, 'motivo_cese': '',
            },
        ]
        per_rows = [
            {
                'id_persona': 200, 'dni': '77788899',
                'a_paterno': '', 'a_materno': '', 'nombres': '',
                'nombre_completo': 'EXISTENTE NOMBRE', 'celular': '',
            },
        ]
        with patch.object(ss, 'PPersonal') as pp_mock, \
             patch.object(ss, 'PerPersona') as per_mock:
            pp_qs = MagicMock()
            pp_qs.filter.return_value = pp_qs
            pp_qs.values.return_value = pp_rows
            pp_mock.objects.using.return_value = pp_qs

            per_qs = MagicMock()
            per_qs.filter.return_value = per_qs
            per_qs.values.return_value = per_rows
            per_mock.objects.using.return_value = per_qs

            result = sync_personal()

        existente.refresh_from_db()
        assert result['ingreso_actualizado'] == 1
        assert existente.fecha_alta == date(2024, 3, 15)

    def test_no_sobrescribe_fecha_alta_existente(self):
        from personal.models import Personal
        fecha_original = date(2020, 1, 1)
        existente = _personal(
            nro_doc='66677788', fecha_alta=fecha_original,
        )
        pp_rows = [
            {
                'id_personal': 100, 'id_persona': 200, 'estado': True,
                'fecha_ingreso': date(2024, 3, 15),  # Synkro tiene otra fecha
                'fecha_termino_contrato': None, 'motivo_cese': '',
            },
        ]
        per_rows = [
            {
                'id_persona': 200, 'dni': '66677788',
                'a_paterno': '', 'a_materno': '', 'nombres': '',
                'nombre_completo': 'EXISTE', 'celular': '',
            },
        ]
        with patch.object(ss, 'PPersonal') as pp_mock, \
             patch.object(ss, 'PerPersona') as per_mock:
            pp_qs = MagicMock()
            pp_qs.filter.return_value = pp_qs
            pp_qs.values.return_value = pp_rows
            pp_mock.objects.using.return_value = pp_qs

            per_qs = MagicMock()
            per_qs.filter.return_value = per_qs
            per_qs.values.return_value = per_rows
            per_mock.objects.using.return_value = per_qs

            sync_personal()

        existente.refresh_from_db()
        # No se sobrescribió la fecha original
        assert existente.fecha_alta == fecha_original

    def test_dni_vacio_se_ignora(self):
        pp_rows = [
            {
                'id_personal': 100, 'id_persona': 200, 'estado': True,
                'fecha_ingreso': date(2025, 1, 1),
                'fecha_termino_contrato': None, 'motivo_cese': '',
            },
        ]
        per_rows = [
            {
                'id_persona': 200, 'dni': '',  # vacío
                'a_paterno': 'X', 'a_materno': 'Y', 'nombres': 'Z',
                'nombre_completo': 'X Y, Z', 'celular': '',
            },
        ]
        with patch.object(ss, 'PPersonal') as pp_mock, \
             patch.object(ss, 'PerPersona') as per_mock:
            pp_qs = MagicMock()
            pp_qs.filter.return_value = pp_qs
            pp_qs.values.return_value = pp_rows
            pp_mock.objects.using.return_value = pp_qs

            per_qs = MagicMock()
            per_qs.filter.return_value = per_qs
            per_qs.values.return_value = per_rows
            per_mock.objects.using.return_value = per_qs

            result = sync_personal()

        assert result['altas_creadas'] == 0
        assert result['altas_omitidas_sin_datos'] == 0

    def test_construye_nombre_desde_apellidos_si_no_hay_nombre_completo(self):
        from personal.models import Personal
        pp_rows = [
            {
                'id_personal': 100, 'id_persona': 200, 'estado': True,
                'fecha_ingreso': date(2025, 1, 1),
                'fecha_termino_contrato': None, 'motivo_cese': '',
            },
        ]
        per_rows = [
            {
                'id_persona': 200, 'dni': '12121212',
                'a_paterno': 'GARCIA', 'a_materno': 'PEREZ',
                'nombres': 'MARIA ROSA',
                'nombre_completo': '',  # vacío → construir desde apellidos
                'celular': '',
            },
        ]
        with patch.object(ss, 'PPersonal') as pp_mock, \
             patch.object(ss, 'PerPersona') as per_mock:
            pp_qs = MagicMock()
            pp_qs.filter.return_value = pp_qs
            pp_qs.values.return_value = pp_rows
            pp_mock.objects.using.return_value = pp_qs

            per_qs = MagicMock()
            per_qs.filter.return_value = per_qs
            per_qs.values.return_value = per_rows
            per_mock.objects.using.return_value = per_qs

            sync_personal()

        nuevo = Personal.objects.get(nro_doc='12121212')
        assert nuevo.apellidos_nombres == 'GARCIA PEREZ, MARIA ROSA'


# ════════════════════════════════════════════════════════════════════════
# sync_papeletas
# ════════════════════════════════════════════════════════════════════════


def _make_permiso(**kwargs):
    """Construye un mock con atributos típicos de PermisoLicencia."""
    defaults = {
        'id_permiso': 1,
        'id_personal': 100,
        'id_tipo_permiso': 4,  # VACACIONES
        'fecha_inicio': date(2026, 5, 1),
        'fecha_fin': date(2026, 5, 5),
        'detalle': 'Vacaciones anuales',
        'fecha_registro': datetime(2026, 4, 15, 10, 0),
        'fecha_modifica': datetime(2026, 4, 15, 10, 0),
    }
    defaults.update(kwargs)
    return MagicMock(**defaults)


def _permiso_qs(permisos):
    """QuerySet mock que soporta toda la cadena:
    .using('synkro').all().filter().order_by().iterator(chunk_size=...)"""
    qs = MagicMock()
    qs.all.return_value = qs
    qs.filter.return_value = qs
    qs.order_by.return_value = qs
    qs.iterator.return_value = iter(permisos)
    return qs


def _picado_qs(picados):
    """QuerySet mock para PicadoPersonal:
    .using('synkro').filter(...).order_by(...).iterator(chunk_size=...)"""
    qs = MagicMock()
    qs.all.return_value = qs
    qs.filter.return_value = qs
    qs.order_by.return_value = qs
    qs.iterator.return_value = iter(picados)
    return qs


@pytest.mark.django_db
class TestSyncPapeletas:
    def test_crea_papeleta_nueva(self):
        from asistencia.models import RegistroPapeleta
        p = _personal(nro_doc='30000001')

        permiso = _make_permiso(
            id_permiso=42, id_personal=100, id_tipo_permiso=4,
            fecha_inicio=date(2026, 5, 1), fecha_fin=date(2026, 5, 5),
            detalle='Vacaciones',
        )
        with patch.object(ss, 'PermisoLicencia') as pl_mock:
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.all.return_value = qs
            qs.order_by.return_value = qs
            qs.iterator.return_value = iter([permiso])
            pl_mock.objects.using.return_value = qs

            personal_dni_map = {100: '30000001'}
            personal_idx = {'30000001': p.id}

            result = sync_papeletas(None, personal_dni_map, personal_idx)

        assert result['creadas'] == 1
        assert result['actualizadas'] == 0
        assert result['omitidas'] == 0
        assert result['no_encontradas'] == 0
        pap = RegistroPapeleta.objects.get(personal_id=p.id)
        assert pap.tipo_permiso == 'VACACIONES'
        assert pap.fecha_inicio == date(2026, 5, 1)
        assert pap.fecha_fin == date(2026, 5, 5)
        assert pap.dias_habiles == 5
        assert pap.origen == 'IMPORTACION'
        assert 'SYNKRO#42' in pap.observaciones

    def test_tipo_permiso_no_mapeado_omite(self):
        # IdTipoPermiso=15 (FR) → None en TIPO_PERMISO_MAP → omitida
        p = _personal(nro_doc='30000002')
        permiso = _make_permiso(
            id_permiso=43, id_personal=100, id_tipo_permiso=15,
        )
        with patch.object(ss, 'PermisoLicencia') as pl_mock:
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.all.return_value = qs
            qs.order_by.return_value = qs
            qs.iterator.return_value = iter([permiso])
            pl_mock.objects.using.return_value = qs

            result = sync_papeletas(None, {100: '30000002'}, {'30000002': p.id})

        assert result['omitidas'] == 1
        assert result['creadas'] == 0

    def test_tipo_permiso_desconocido_omite(self):
        p = _personal(nro_doc='30000010')
        permiso = _make_permiso(
            id_permiso=99, id_personal=100, id_tipo_permiso=999,  # no en map
        )
        with patch.object(ss, 'PermisoLicencia') as pl_mock:
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.all.return_value = qs
            qs.order_by.return_value = qs
            qs.iterator.return_value = iter([permiso])
            pl_mock.objects.using.return_value = qs

            result = sync_papeletas(None, {100: '30000010'}, {'30000010': p.id})

        assert result['omitidas'] == 1

    def test_dni_no_encontrado_en_mapa(self):
        permiso = _make_permiso(id_personal=999)  # no en dni_map
        with patch.object(ss, 'PermisoLicencia') as pl_mock:
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.all.return_value = qs
            qs.order_by.return_value = qs
            qs.iterator.return_value = iter([permiso])
            pl_mock.objects.using.return_value = qs

            result = sync_papeletas(None, {}, {})
        assert result['no_encontradas'] == 1

    def test_dni_no_encontrado_en_personal_harmoni(self):
        permiso = _make_permiso(id_personal=100)
        with patch.object(ss, 'PermisoLicencia') as pl_mock:
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.all.return_value = qs
            qs.order_by.return_value = qs
            qs.iterator.return_value = iter([permiso])
            pl_mock.objects.using.return_value = qs

            # dni_map sí lo tiene pero personal_idx no
            result = sync_papeletas(None, {100: '99999999'}, {})
        assert result['no_encontradas'] == 1

    def test_fechas_invertidas_omite(self):
        p = _personal(nro_doc='30000003')
        permiso = _make_permiso(
            id_permiso=44, id_personal=100, id_tipo_permiso=4,
            fecha_inicio=date(2026, 5, 10),
            fecha_fin=date(2026, 5, 1),  # ← invertidas
        )
        with patch.object(ss, 'PermisoLicencia') as pl_mock:
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.all.return_value = qs
            qs.order_by.return_value = qs
            qs.iterator.return_value = iter([permiso])
            pl_mock.objects.using.return_value = qs

            result = sync_papeletas(None, {100: '30000003'}, {'30000003': p.id})

        assert result['omitidas'] == 1
        assert result['creadas'] == 0

    def test_max_cursor_es_el_mayor_timestamp(self):
        p = _personal(nro_doc='30000004')
        ts1 = datetime(2026, 4, 1, 10, 0)
        ts2 = datetime(2026, 4, 20, 14, 0)
        ts3 = datetime(2026, 4, 15, 9, 0)
        permisos = [
            _make_permiso(id_permiso=1, id_personal=100, id_tipo_permiso=4,
                          fecha_registro=ts1, fecha_modifica=None),
            _make_permiso(id_permiso=2, id_personal=100, id_tipo_permiso=4,
                          fecha_inicio=date(2026, 6, 1), fecha_fin=date(2026, 6, 2),
                          fecha_registro=ts3, fecha_modifica=ts2),
        ]
        with patch.object(ss, 'PermisoLicencia') as pl_mock:
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.all.return_value = qs
            qs.order_by.return_value = qs
            qs.iterator.return_value = iter(permisos)
            pl_mock.objects.using.return_value = qs

            result = sync_papeletas(None, {100: '30000004'}, {'30000004': p.id})

        assert result['max_cursor'] == ts2

    def test_cursor_desde_aplica_filtro(self):
        cursor = datetime(2026, 4, 1, 0, 0)
        with patch.object(ss, 'PermisoLicencia') as pl_mock:
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.all.return_value = qs
            qs.order_by.return_value = qs
            qs.iterator.return_value = iter([])
            pl_mock.objects.using.return_value = qs

            sync_papeletas(cursor, {}, {})
            # Se aplicó filter por cursor
            assert qs.filter.called

    def test_actualiza_papeleta_existente_si_cambia(self):
        from asistencia.models import RegistroPapeleta
        p = _personal(nro_doc='30000005')
        # Crear papeleta pre-existente con marca SYNKRO#77
        RegistroPapeleta.objects.create(
            personal=p, dni='30000005', tipo_permiso='VACACIONES',
            fecha_inicio=date(2026, 5, 1), fecha_fin=date(2026, 5, 3),
            dias_habiles=3, estado='APROBADA', origen='IMPORTACION',
            observaciones='SYNKRO#77 | sync auto',
        )
        permiso = _make_permiso(
            id_permiso=77, id_personal=100, id_tipo_permiso=4,
            fecha_inicio=date(2026, 5, 1),
            fecha_fin=date(2026, 5, 7),  # cambio en fecha_fin
            detalle='Cambiado',
        )
        with patch.object(ss, 'PermisoLicencia') as pl_mock:
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.all.return_value = qs
            qs.order_by.return_value = qs
            qs.iterator.return_value = iter([permiso])
            pl_mock.objects.using.return_value = qs

            result = sync_papeletas(None, {100: '30000005'}, {'30000005': p.id})

        assert result['actualizadas'] == 1
        pap = RegistroPapeleta.objects.get(observaciones__contains='SYNKRO#77')
        assert pap.fecha_fin == date(2026, 5, 7)
        assert pap.detalle == 'Cambiado'
        assert pap.dias_habiles == 7

    def test_no_actualiza_si_no_hay_cambios(self):
        from asistencia.models import RegistroPapeleta
        p = _personal(nro_doc='30000006')
        RegistroPapeleta.objects.create(
            personal=p, dni='30000006', tipo_permiso='VACACIONES',
            fecha_inicio=date(2026, 5, 1), fecha_fin=date(2026, 5, 3),
            detalle='Igual', dias_habiles=3,
            estado='APROBADA', origen='IMPORTACION',
            observaciones='SYNKRO#88 | sync auto',
        )
        permiso = _make_permiso(
            id_permiso=88, id_personal=100, id_tipo_permiso=4,
            fecha_inicio=date(2026, 5, 1), fecha_fin=date(2026, 5, 3),
            detalle='Igual',
        )
        with patch.object(ss, 'PermisoLicencia') as pl_mock:
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.all.return_value = qs
            qs.order_by.return_value = qs
            qs.iterator.return_value = iter([permiso])
            pl_mock.objects.using.return_value = qs

            result = sync_papeletas(None, {100: '30000006'}, {'30000006': p.id})

        assert result['actualizadas'] == 0
        assert result['omitidas'] == 1

    def test_dias_habiles_calculado_correctamente(self):
        from asistencia.models import RegistroPapeleta
        p = _personal(nro_doc='30000007')
        permiso = _make_permiso(
            id_permiso=200, id_personal=100, id_tipo_permiso=4,
            fecha_inicio=date(2026, 5, 1),
            fecha_fin=date(2026, 5, 1),  # mismo día
        )
        with patch.object(ss, 'PermisoLicencia') as pl_mock:
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.all.return_value = qs
            qs.order_by.return_value = qs
            qs.iterator.return_value = iter([permiso])
            pl_mock.objects.using.return_value = qs

            sync_papeletas(None, {100: '30000007'}, {'30000007': p.id})

        pap = RegistroPapeleta.objects.get(observaciones__contains='SYNKRO#200')
        # 1 día: max(1, 0+1) = 1
        assert pap.dias_habiles == 1


# ════════════════════════════════════════════════════════════════════════
# sync_picados (mockea PicadoPersonal + cache de FeriadoCalendario)
# ════════════════════════════════════════════════════════════════════════


def _picado(id_picado, id_personal, fecha):
    """Construye un picado mock con .id_personal, .fecha, .fecha_sin_ms"""
    p = MagicMock()
    p.id_picado = id_picado
    p.id_personal = id_personal
    p.fecha = fecha
    p.fecha_sin_ms = fecha.date()
    return p


@pytest.mark.django_db
class TestSyncPicados:
    def test_sin_picados_retorna_cero(self):
        with patch.object(ss, 'PicadoPersonal') as pp_mock:
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.all.return_value = qs
            qs.order_by.return_value = qs
            qs.iterator.return_value = iter([])
            pp_mock.objects.using.return_value = qs

            result = sync_picados(None, {}, {})

        assert result['creados'] == 0
        assert result['actualizados'] == 0
        assert result['no_encontrados'] == 0
        assert result['omitidos_cerrado'] == 0

    def test_crea_registro_tareo_nuevo(self):
        from asistencia.models import RegistroTareo
        p = _personal(nro_doc='40000001', cargo='Operador',
                      tipo_trab='Empleado')
        # 2 picados el mismo día (entrada+salida)
        picados = [
            _picado(1, 500, datetime(2026, 5, 20, 8, 0)),
            _picado(2, 500, datetime(2026, 5, 20, 17, 0)),
        ]
        with patch.object(ss, 'PicadoPersonal') as pp_mock:
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.all.return_value = qs
            qs.order_by.return_value = qs
            qs.iterator.return_value = iter(picados)
            pp_mock.objects.using.return_value = qs

            result = sync_picados(None, {500: '40000001'}, {'40000001': p.id})

        assert result['creados'] == 1
        reg = RegistroTareo.objects.get(personal=p, fecha=date(2026, 5, 20))
        assert reg.hora_entrada_real.strftime('%H:%M') == '08:00'
        assert reg.hora_salida_real.strftime('%H:%M') == '17:00'
        assert reg.fuente_codigo == 'RELOJ'
        assert reg.codigo_dia == 'A'

    def test_dni_no_encontrado_no_crea(self):
        picados = [_picado(1, 999, datetime(2026, 5, 20, 8, 0))]
        with patch.object(ss, 'PicadoPersonal') as pp_mock:
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.all.return_value = qs
            qs.order_by.return_value = qs
            qs.iterator.return_value = iter(picados)
            pp_mock.objects.using.return_value = qs
            result = sync_picados(None, {}, {})
        assert result['no_encontrados'] == 1

    def test_personal_inexistente_en_harmoni_skip(self):
        picados = [_picado(1, 500, datetime(2026, 5, 20, 8, 0))]
        with patch.object(ss, 'PicadoPersonal') as pp_mock:
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.all.return_value = qs
            qs.order_by.return_value = qs
            qs.iterator.return_value = iter(picados)
            pp_mock.objects.using.return_value = qs
            # dni_map dice 99999999 pero no hay Personal con ese id
            result = sync_picados(None, {500: '99999999'}, {'99999999': 9999999})
        assert result['no_encontrados'] == 1

    def test_omite_periodo_cerrado(self):
        from cierre.models import PeriodoCierre
        p = _personal(nro_doc='40000003')
        PeriodoCierre.objects.create(
            anio=2026, mes=5, estado='CERRADO',
        )
        picados = [_picado(1, 500, datetime(2026, 5, 20, 8, 0))]
        with patch.object(ss, 'PicadoPersonal') as pp_mock:
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.all.return_value = qs
            qs.order_by.return_value = qs
            qs.iterator.return_value = iter(picados)
            pp_mock.objects.using.return_value = qs

            result = sync_picados(None, {500: '40000003'}, {'40000003': p.id})

        assert result['omitidos_cerrado'] == 1
        assert result['creados'] == 0

    def test_fecha_antes_de_alta_se_ignora(self):
        from asistencia.models import RegistroTareo
        p = _personal(nro_doc='40000004', fecha_alta=date(2026, 6, 1))
        # Picado en mayo, antes de fecha_alta
        picados = [_picado(1, 500, datetime(2026, 5, 20, 8, 0))]
        with patch.object(ss, 'PicadoPersonal') as pp_mock:
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.all.return_value = qs
            qs.order_by.return_value = qs
            qs.iterator.return_value = iter(picados)
            pp_mock.objects.using.return_value = qs

            result = sync_picados(None, {500: '40000004'}, {'40000004': p.id})

        assert result['creados'] == 0
        assert not RegistroTareo.objects.filter(personal=p).exists()

    def test_fecha_despues_de_cese_se_ignora(self):
        from asistencia.models import RegistroTareo
        p = _personal(nro_doc='40000005',
                      fecha_alta=date(2020, 1, 1),
                      fecha_cese=date(2026, 5, 1),
                      estado='Cesado')
        # Picado después del cese
        picados = [_picado(1, 500, datetime(2026, 5, 20, 8, 0))]
        with patch.object(ss, 'PicadoPersonal') as pp_mock:
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.all.return_value = qs
            qs.order_by.return_value = qs
            qs.iterator.return_value = iter(picados)
            pp_mock.objects.using.return_value = qs
            result = sync_picados(None, {500: '40000005'}, {'40000005': p.id})

        assert result['creados'] == 0
        assert not RegistroTareo.objects.filter(personal=p).exists()

    def test_picado_unico_codigo_ss_sin_salida(self):
        from asistencia.models import RegistroTareo
        p = _personal(nro_doc='40000006')
        # Solo 1 picado (entrada, sin salida)
        picados = [_picado(1, 500, datetime(2026, 5, 20, 8, 0))]
        with patch.object(ss, 'PicadoPersonal') as pp_mock:
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.all.return_value = qs
            qs.order_by.return_value = qs
            qs.iterator.return_value = iter(picados)
            pp_mock.objects.using.return_value = qs

            sync_picados(None, {500: '40000006'}, {'40000006': p.id})

        reg = RegistroTareo.objects.get(personal=p, fecha=date(2026, 5, 20))
        assert reg.hora_salida_real is None
        assert reg.codigo_dia == 'SS'

    def test_actualiza_registro_existente_fuente_reescribible(self):
        from asistencia.models import RegistroTareo, TareoImportacion
        p = _personal(nro_doc='40000007')
        imp = TareoImportacion.objects.create(
            tipo='RELOJ', archivo_nombre='prev',
            periodo_inicio=date(2026, 5, 1), periodo_fin=date(2026, 5, 31),
        )
        RegistroTareo.objects.create(
            importacion=imp, personal=p, dni='40000007',
            grupo='STAFF', condicion='LOCAL',
            fecha=date(2026, 5, 20), dia_semana=2,
            fuente_codigo='FALTA_AUTO', codigo_dia='FA',
        )
        picados = [
            _picado(1, 500, datetime(2026, 5, 20, 8, 0)),
            _picado(2, 500, datetime(2026, 5, 20, 17, 0)),
        ]
        with patch.object(ss, 'PicadoPersonal') as pp_mock:
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.all.return_value = qs
            qs.order_by.return_value = qs
            qs.iterator.return_value = iter(picados)
            pp_mock.objects.using.return_value = qs

            result = sync_picados(None, {500: '40000007'}, {'40000007': p.id})

        assert result['actualizados'] == 1
        reg = RegistroTareo.objects.get(personal=p, fecha=date(2026, 5, 20))
        assert reg.fuente_codigo == 'RELOJ'
        assert reg.codigo_dia == 'A'  # ya no es 'FA'

    def test_no_sobrescribe_fuente_manual(self):
        from asistencia.models import RegistroTareo, TareoImportacion
        p = _personal(nro_doc='40000008')
        imp = TareoImportacion.objects.create(
            tipo='RELOJ', archivo_nombre='prev',
            periodo_inicio=date(2026, 5, 1), periodo_fin=date(2026, 5, 31),
        )
        from datetime import time as dt_time
        reg = RegistroTareo.objects.create(
            importacion=imp, personal=p, dni='40000008',
            grupo='STAFF', condicion='LOCAL',
            fecha=date(2026, 5, 20), dia_semana=2,
            fuente_codigo='MANUAL', codigo_dia='VAC',
            hora_entrada_real=dt_time(10, 0),
        )
        picados = [
            _picado(1, 500, datetime(2026, 5, 20, 8, 0)),
            _picado(2, 500, datetime(2026, 5, 20, 17, 0)),
        ]
        with patch.object(ss, 'PicadoPersonal') as pp_mock:
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.all.return_value = qs
            qs.order_by.return_value = qs
            qs.iterator.return_value = iter(picados)
            pp_mock.objects.using.return_value = qs

            result = sync_picados(None, {500: '40000008'}, {'40000008': p.id})

        assert result['actualizados'] == 0
        reg.refresh_from_db()
        assert reg.fuente_codigo == 'MANUAL'
        assert reg.codigo_dia == 'VAC'

    def test_no_sobrescribe_fuente_papeleta_con_ref(self):
        from asistencia.models import RegistroTareo, TareoImportacion
        p = _personal(nro_doc='40000009')
        imp = TareoImportacion.objects.create(
            tipo='RELOJ', archivo_nombre='prev',
            periodo_inicio=date(2026, 5, 1), periodo_fin=date(2026, 5, 31),
        )
        reg = RegistroTareo.objects.create(
            importacion=imp, personal=p, dni='40000009',
            grupo='STAFF', condicion='LOCAL',
            fecha=date(2026, 5, 20), dia_semana=2,
            fuente_codigo='PAPELETA', codigo_dia='VAC',
            papeleta_ref='PAP#42',
        )
        picados = [
            _picado(1, 500, datetime(2026, 5, 20, 8, 0)),
            _picado(2, 500, datetime(2026, 5, 20, 17, 0)),
        ]
        with patch.object(ss, 'PicadoPersonal') as pp_mock:
            qs = MagicMock()
            qs.filter.return_value = qs
            qs.all.return_value = qs
            qs.order_by.return_value = qs
            qs.iterator.return_value = iter(picados)
            pp_mock.objects.using.return_value = qs
            result = sync_picados(None, {500: '40000009'}, {'40000009': p.id})

        assert result['actualizados'] == 0
        reg.refresh_from_db()
        assert reg.fuente_codigo == 'PAPELETA'


# ════════════════════════════════════════════════════════════════════════
# _ultimo_cursor + run_sync (orquestador)
# ════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestUltimoCursor:
    def test_sin_logs_retorna_nones(self):
        cur_pap, cur_pic = _ultimo_cursor()
        assert cur_pap is None
        assert cur_pic is None

    def test_retorna_cursor_del_ultimo_log_ok(self):
        from integraciones.models import SyncSynkroLog
        cur_pap = timezone.now() - timedelta(hours=2)
        cur_pic = timezone.now() - timedelta(hours=1)
        SyncSynkroLog.objects.create(
            estado='OK', origen='AUTO',
            cursor_papeletas=cur_pap, cursor_picados=cur_pic,
        )
        cp, cpc = _ultimo_cursor()
        # Comparación por valor (ya que ambos son datetimes con tz)
        assert cp == cur_pap
        assert cpc == cur_pic

    def test_ignora_logs_no_ok(self):
        from integraciones.models import SyncSynkroLog
        # Crear un log OK más viejo
        cur_viejo = timezone.now() - timedelta(days=2)
        SyncSynkroLog.objects.create(
            estado='OK', origen='AUTO',
            cursor_papeletas=cur_viejo, cursor_picados=cur_viejo,
        )
        # Y un log ERROR más reciente
        SyncSynkroLog.objects.create(
            estado='ERROR', origen='AUTO',
            cursor_papeletas=timezone.now(),
            cursor_picados=timezone.now(),
        )
        cp, _ = _ultimo_cursor()
        # Debe traer el del OK viejo, no el del ERROR
        assert cp == cur_viejo


@pytest.mark.django_db
class TestRunSync:
    def test_run_sync_completo_crea_log_ok(self):
        from integraciones.models import SyncSynkroLog
        # Mockear las cuatro funciones internas
        with patch.object(ss, 'sync_personal', return_value={
                'altas_creadas': 0, 'altas_omitidas_sin_datos': 0,
                'ceses_actualizados': 0, 'ingreso_actualizado': 0,
                'sin_cambios': 0,
             }), \
             patch.object(ss, '_build_personal_index_por_dni',
                          return_value={}), \
             patch.object(ss, '_build_synkro_personal_to_dni',
                          return_value={}), \
             patch.object(ss, 'sync_feriados', return_value=3), \
             patch.object(ss, 'sync_papeletas', return_value={
                'creadas': 1, 'actualizadas': 2, 'omitidas': 0,
                'no_encontradas': 0, 'max_cursor': None,
             }), \
             patch.object(ss, 'sync_picados', return_value={
                'creados': 5, 'actualizados': 3, 'no_encontrados': 0,
                'omitidos_cerrado': 0, 'max_cursor': None,
             }):
            log = run_sync(origen='MANUAL')

        assert isinstance(log, SyncSynkroLog)
        assert log.estado == 'OK'
        assert log.feriados_creados == 3
        assert log.papeletas_creadas == 1
        assert log.papeletas_actualizadas == 2
        assert log.registros_tareo_creados == 5
        assert log.registros_tareo_actualizados == 3
        assert log.origen == 'MANUAL'
        assert log.finalizado_en is not None
        assert log.duracion_segundos >= 0

    def test_run_sync_falla_marca_error_y_guarda_mensaje(self):
        from integraciones.models import SyncSynkroLog
        with patch.object(ss, 'sync_personal',
                          side_effect=RuntimeError('Synkro DB caída')):
            log = run_sync(origen='AUTO')

        assert log.estado == 'ERROR'
        assert 'RuntimeError' in log.error_mensaje
        assert 'Synkro DB caída' in log.error_mensaje
        assert log.finalizado_en is not None

    def test_run_sync_usa_origen_default_auto(self):
        with patch.object(ss, 'sync_personal',
                          side_effect=RuntimeError('boom')):
            log = run_sync()
        assert log.origen == 'AUTO'

    def test_run_sync_propaga_cursor_a_log(self):
        cursor_pap = timezone.now() - timedelta(hours=1)
        cursor_pic = timezone.now() - timedelta(minutes=30)
        with patch.object(ss, 'sync_personal', return_value={
                'altas_creadas': 0, 'altas_omitidas_sin_datos': 0,
                'ceses_actualizados': 0, 'ingreso_actualizado': 0,
                'sin_cambios': 0,
             }), \
             patch.object(ss, '_build_personal_index_por_dni',
                          return_value={}), \
             patch.object(ss, '_build_synkro_personal_to_dni',
                          return_value={}), \
             patch.object(ss, 'sync_feriados', return_value=0), \
             patch.object(ss, 'sync_papeletas', return_value={
                'creadas': 0, 'actualizadas': 0, 'omitidas': 0,
                'no_encontradas': 0, 'max_cursor': cursor_pap,
             }), \
             patch.object(ss, 'sync_picados', return_value={
                'creados': 0, 'actualizados': 0, 'no_encontrados': 0,
                'omitidos_cerrado': 0, 'max_cursor': cursor_pic,
             }):
            log = run_sync(origen='CLI')

        assert log.cursor_papeletas == cursor_pap
        assert log.cursor_picados == cursor_pic
        # detalle contiene los sub-resultados serializados
        assert 'papeletas' in log.detalle
        assert 'picados' in log.detalle
        assert 'feriados' in log.detalle
        assert 'personal' in log.detalle
