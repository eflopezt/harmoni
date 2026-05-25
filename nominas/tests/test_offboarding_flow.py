"""
Tests del Workflow "Offboarding Trabajador".

Cubre:
  1. seed_offboarding_flow crea el FlujoTrabajo + 5 etapas + grupo Tesorería.
  2. seed_offboarding_flow es idempotente (no duplica al correr 2x).
  3. Signal post_save LiquidacionLaboral crea InstanciaFlujo al pasar a CALCULADA.
  4. Signal NO crea una segunda InstanciaFlujo si la LL ya tiene una.
  5. Signal falla silenciosamente si el flujo no existe (no rompe el cálculo).
  6. Las 5 etapas tienen los aprobadores y tiempos correctos.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import StringIO

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command

from nominas.models import LiquidacionLaboral
from personal.models import Area, Personal, SubArea
from workflows.models import EtapaFlujo, FlujoTrabajo, InstanciaFlujo


FLUJO_NOMBRE = 'Offboarding Trabajador'


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username='admin_off', email='off@a.com', password='x',
    )


@pytest.fixture
def area(db):
    return Area.objects.create(nombre='Operaciones OFFB')


@pytest.fixture
def subarea(area):
    return SubArea.objects.create(nombre='Sub OFFB', area=area)


@pytest.fixture
def worker_activo(db, subarea):
    return Personal.objects.create(
        nro_doc='50000001',
        apellidos_nombres='OFFBOARDING TEST, ANA',
        cargo='Operario',
        tipo_trab='Empleado',
        estado='Activo',
        subarea=subarea,
        fecha_alta=date(2024, 1, 15),
        sueldo_base=Decimal('3000.00'),
        regimen_pension='AFP',
        afp='Prima',
    )


@pytest.fixture
def seed_aplicado(db, admin_user):
    """Asegura que el flujo Offboarding está sembrado antes del test."""
    call_command('seed_offboarding_flow', stdout=StringIO())
    return FlujoTrabajo.objects.get(nombre=FLUJO_NOMBRE)


# ─── 1. Seed crea flujo + 5 etapas ───────────────────────────────────────────

class TestSeedCreaFlujo:
    def test_seed_crea_flujo_con_5_etapas(self, db, admin_user):
        """Tras correr el seed, el FlujoTrabajo y sus 5 etapas existen."""
        assert not FlujoTrabajo.objects.filter(nombre=FLUJO_NOMBRE).exists()

        out = StringIO()
        call_command('seed_offboarding_flow', stdout=out)

        flujo = FlujoTrabajo.objects.get(nombre=FLUJO_NOMBRE)
        assert flujo.campo_trigger == 'estado'
        assert flujo.valor_trigger == 'CALCULADA'
        assert flujo.campo_resultado == 'estado'
        assert flujo.valor_aprobado == 'CERRADA'
        assert flujo.activo is True

        # ContentType apunta a LiquidacionLaboral
        ct = flujo.content_type
        assert ct.app_label == 'nominas'
        assert ct.model == 'liquidacionlaboral'

        # 5 etapas en orden correcto con aprobadores correctos
        etapas = list(flujo.etapas.order_by('orden'))
        assert len(etapas) == 5

        assert etapas[0].nombre == 'Encuesta de salida'
        assert etapas[0].tipo_aprobador == 'USUARIO'
        assert etapas[0].tiempo_limite_horas == 72
        assert etapas[0].accion_vencimiento == 'ESPERAR'

        assert etapas[1].nombre == 'Devolución de activos'
        assert etapas[1].tipo_aprobador == 'JEFE_AREA'
        assert etapas[1].tiempo_limite_horas == 120
        assert etapas[1].accion_vencimiento == 'ESCALAR'
        assert etapas[1].requiere_comentario is True

        assert etapas[2].nombre == 'Liquidación pagada'
        assert etapas[2].tipo_aprobador == 'GRUPO_DJANGO'
        assert etapas[2].aprobador_grupo is not None
        assert etapas[2].aprobador_grupo.name == 'Tesorería'
        assert etapas[2].tiempo_limite_horas == 168
        assert etapas[2].requiere_comentario is True

        assert etapas[3].nombre == 'Carta de no adeudo'
        assert etapas[3].tipo_aprobador == 'SUPERUSER'
        assert etapas[3].accion_vencimiento == 'AUTO_APROBAR'

        assert etapas[4].nombre == 'Cierre administrativo'
        assert etapas[4].tipo_aprobador == 'SUPERUSER'
        assert etapas[4].tiempo_limite_horas == 48
        assert etapas[4].accion_vencimiento == 'AUTO_APROBAR'

    def test_seed_crea_grupo_tesoreria(self, db):
        """El grupo Tesorería se crea si no existía."""
        assert not Group.objects.filter(name='Tesorería').exists()
        call_command('seed_offboarding_flow', stdout=StringIO())
        assert Group.objects.filter(name='Tesorería').exists()


# ─── 2. Idempotencia ─────────────────────────────────────────────────────────

class TestSeedIdempotente:
    def test_seed_dos_veces_no_duplica(self, db):
        """Correr el seed 2 veces deja exactamente 1 flujo + 5 etapas."""
        call_command('seed_offboarding_flow', stdout=StringIO())
        call_command('seed_offboarding_flow', stdout=StringIO())

        flujos = FlujoTrabajo.objects.filter(nombre=FLUJO_NOMBRE)
        assert flujos.count() == 1
        assert flujos.first().etapas.count() == 5

    def test_seed_no_recrea_grupo_existente(self, db):
        """Si Tesorería ya existe, el seed la reutiliza sin duplicar."""
        grupo_pre = Group.objects.create(name='Tesorería')
        call_command('seed_offboarding_flow', stdout=StringIO())
        assert Group.objects.filter(name='Tesorería').count() == 1
        # Misma PK = mismo grupo
        flujo = FlujoTrabajo.objects.get(nombre=FLUJO_NOMBRE)
        etapa_tesoreria = flujo.etapas.get(orden=3)
        assert etapa_tesoreria.aprobador_grupo_id == grupo_pre.pk

    def test_seed_dry_run_no_persiste(self, db):
        """--dry-run no crea nada en BD."""
        call_command('seed_offboarding_flow', '--dry-run', stdout=StringIO())
        assert not FlujoTrabajo.objects.filter(nombre=FLUJO_NOMBRE).exists()
        assert not Group.objects.filter(name='Tesorería').exists()


# ─── 3. Signal: dispara workflow al pasar a CALCULADA ────────────────────────

class TestSignalDisparaWorkflow:
    def test_signal_crea_instancia_al_calcular(self, worker_activo, seed_aplicado, admin_user):
        """LL.calcular() → estado=CALCULADA → signal crea InstanciaFlujo."""
        liq = LiquidacionLaboral.objects.create(
            personal=worker_activo,
            fecha_cese=date(2026, 3, 31),
            motivo_cese='RENUNCIA',
        )
        # En la creación el signal aún no dispara (estado=BORRADOR)
        assert liq.instancia_flujo is None

        liq.calcular()  # → CALCULADA → dispara signal

        liq.refresh_from_db()
        assert liq.estado == 'CALCULADA'
        assert liq.instancia_flujo is not None
        assert liq.instancia_flujo.flujo == seed_aplicado
        assert liq.instancia_flujo.estado == 'EN_PROCESO'
        # La primera etapa es "Encuesta de salida"
        assert liq.instancia_flujo.etapa_actual.orden == 1
        assert liq.instancia_flujo.etapa_actual.nombre == 'Encuesta de salida'
        # Metadata útil
        assert liq.instancia_flujo.metadata.get('liquidacion_id') == liq.pk


# ─── 4. Idempotencia del signal ──────────────────────────────────────────────

class TestSignalIdempotente:
    def test_signal_no_duplica_instancia(self, worker_activo, seed_aplicado):
        """Si LL ya tiene instancia_flujo, el signal NO crea una segunda."""
        liq = LiquidacionLaboral.objects.create(
            personal=worker_activo,
            fecha_cese=date(2026, 3, 31),
            motivo_cese='RENUNCIA',
        )
        liq.calcular()
        instancia_inicial = liq.instancia_flujo
        assert instancia_inicial is not None

        # Forzar otro save con estado CALCULADA — no debe crear otra
        liq.observaciones = 'editado'
        liq.save()

        liq.refresh_from_db()
        # Sigue siendo la misma instancia
        assert liq.instancia_flujo_id == instancia_inicial.pk
        # Solo hay 1 instancia para este objeto
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(LiquidacionLaboral)
        assert InstanciaFlujo.objects.filter(
            content_type=ct, object_id=liq.pk,
        ).count() == 1


# ─── 5. Falla silenciosa si flujo no existe ──────────────────────────────────

class TestSignalFallaSilenciosa:
    def test_signal_no_crashea_sin_flujo_sembrado(self, worker_activo, admin_user, caplog):
        """Si "Offboarding Trabajador" no está en BD, el signal solo logea warning."""
        # Verificación previa — el seed NO se corrió en este test
        assert not FlujoTrabajo.objects.filter(nombre=FLUJO_NOMBRE).exists()

        # Esto no debe lanzar excepción
        liq = LiquidacionLaboral.objects.create(
            personal=worker_activo,
            fecha_cese=date(2026, 3, 31),
            motivo_cese='RENUNCIA',
        )
        liq.calcular()

        # La liquidación quedó calculada OK
        liq.refresh_from_db()
        assert liq.estado == 'CALCULADA'
        # Pero sin instancia_flujo
        assert liq.instancia_flujo is None

    def test_signal_no_crashea_si_estado_distinto(self, worker_activo, seed_aplicado):
        """Save con estado != CALCULADA no dispara nada, sin error."""
        liq = LiquidacionLaboral.objects.create(
            personal=worker_activo,
            fecha_cese=date(2026, 3, 31),
            motivo_cese='RENUNCIA',
        )
        # estado='BORRADOR' tras create — signal no dispara
        assert liq.instancia_flujo is None
        # Forzar otro save sin pasar a CALCULADA
        liq.observaciones = 'nota'
        liq.save()
        liq.refresh_from_db()
        assert liq.instancia_flujo is None
