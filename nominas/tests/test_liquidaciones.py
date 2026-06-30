"""
Tests Sprint 1 — LiquidacionLaboral.

Cubre:
- Creación manual + cálculo de conceptos (vacaciones, gratif, CTS, sueldo).
- Signal post_save Personal: auto-genera al cesar.
- Idempotencia: cesar 2 veces no duplica.
- Indemnización por despido arbitrario (DESPIDO_ARB).
- Descuento de préstamo pendiente.
- API endpoint /nominas/api/liquidacion/<personal_id>/.
- Vista de detalle + aprobación.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from personal.models import Area, Personal, SubArea
from nominas.models import LiquidacionLaboral


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser(
        username='admin_liq', password='x', email='liq@a.com',
    )


@pytest.fixture
def client_logged(client, admin_user):
    client.force_login(admin_user)
    return client


@pytest.fixture
def area(db):
    return Area.objects.create(nombre='Operaciones LIQ')


@pytest.fixture
def subarea(area):
    return SubArea.objects.create(nombre='Sub LIQ', area=area)


@pytest.fixture
def worker_activo(db, subarea):
    """Trabajador activo, sueldo S/3000, alta 2024-01-15."""
    return Personal.objects.create(
        nro_doc='40000001',
        apellidos_nombres='TEST LIQUIDACION, JUAN',
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
def worker_cesado(db, subarea):
    """Trabajador YA cesado al crear: 31 marzo 2026, motivo renuncia."""
    return Personal.objects.create(
        nro_doc='40000002',
        apellidos_nombres='TEST CESADO, PEDRO',
        cargo='Mozo',
        tipo_trab='Empleado',
        estado='Cesado',
        subarea=subarea,
        fecha_alta=date(2024, 1, 15),
        fecha_cese=date(2026, 3, 31),
        motivo_cese='RENUNCIA',
        sueldo_base=Decimal('3000.00'),
        regimen_pension='AFP',
        afp='Prima',
    )


# ─── 1. Modelo + cálculo manual ──────────────────────────────────────────────

class TestModelo:
    def test_crear_liquidacion_manual(self, worker_activo):
        """Permite crear una LiquidacionLaboral directamente."""
        liq = LiquidacionLaboral.objects.create(
            personal=worker_activo,
            fecha_cese=date(2026, 3, 31),
            motivo_cese='RENUNCIA',
        )
        assert liq.pk is not None
        assert liq.estado == 'BORRADOR'
        assert liq.total_bruto == Decimal('0.00')
        assert 'TEST LIQUIDACION' in str(liq)

    def test_calcular_persiste_conceptos(self, worker_activo):
        """calcular() llena gratif/CTS/sueldo y suma totales."""
        liq = LiquidacionLaboral.objects.create(
            personal=worker_activo,
            fecha_cese=date(2026, 3, 31),
            motivo_cese='RENUNCIA',
        )
        liq.calcular()

        # Sueldo del mes (31 días de marzo) = 3000/30 * 31 = 3100
        assert liq.sueldo_mes_curso == Decimal('3100.00')

        # Gratificación trunca 3/6 sueldo = 1500 (engine devuelve gratif_bruto)
        assert liq.gratif_trunca == Decimal('1500.00')

        # CTS trunca: base = (3000 + 0 + 500) / 12 * 5 = 1458.33
        assert liq.cts_trunca > Decimal('1400.00')
        assert liq.cts_trunca < Decimal('1500.00')

        # Estado pasa a CALCULADA
        assert liq.estado == 'CALCULADA'

        # Total bruto > 0
        assert liq.total_bruto > Decimal('0')
        # Descuento AFP/ONP sobre conceptos afectos (sueldo mes + gratif trunca)
        assert liq.descuento_pension > Decimal('0')
        # Neto = bruto − descuentos (incluye AFP/ONP)
        assert liq.total_neto == liq.total_bruto - liq.descuento_pension


# ─── 1b. Embargo / pensión judicial al cese ──────────────────────────────────

class TestEmbargoLiquidacion:
    def test_embargo_aprobado_se_descuenta(self, worker_activo):
        """Un embargo APROBADO vigente puebla liq.embargo y reduce el neto.

        Antes liq.embargo quedaba siempre en 0 → el cesado no lo veía descontado.
        """
        from descuentos.models import DescuentoPlanilla
        DescuentoPlanilla.objects.create(
            personal=worker_activo,
            causal='EMBARGO_JUDICIAL',
            detalle='Embargo por orden judicial',
            monto_total=Decimal('5000.00'),
            num_cuotas=10,            # cuota 500/mes
            estado='APROBADO',
            requiere_consentimiento=False,
        )
        liq = LiquidacionLaboral.objects.create(
            personal=worker_activo,
            fecha_cese=date(2026, 6, 30),
            motivo_cese='RENUNCIA',
        )
        liq.calcular()

        # El embargo se pobla, capado por el tope legal (≤ cuota mensual).
        assert liq.embargo > Decimal('0')
        assert liq.embargo <= Decimal('500.00')
        # El neto refleja el embargo además del descuento pensionario.
        assert liq.total_neto == (
            liq.total_bruto - liq.descuento_pension - liq.embargo
            - liq.prestamos_pendientes - liq.adelantos_pendientes
            - liq.otros_descuentos
        )

    def test_sin_embargo_queda_en_cero(self, worker_activo):
        liq = LiquidacionLaboral.objects.create(
            personal=worker_activo,
            fecha_cese=date(2026, 6, 30),
            motivo_cese='RENUNCIA',
        )
        liq.calcular()
        assert liq.embargo == Decimal('0.00')


# ─── 2. Signal: auto-genera al cesar ─────────────────────────────────────────

class TestSignalAutoGenera:
    def test_signal_genera_liquidacion_al_cesar(self, worker_activo):
        """Cambiar estado a 'Cesado' con fecha_cese → genera LiquidacionLaboral."""
        # Sin liquidación aún
        assert not LiquidacionLaboral.objects.filter(personal=worker_activo).exists()

        # Cesar
        worker_activo.estado      = 'Cesado'
        worker_activo.fecha_cese  = date(2026, 6, 30)
        worker_activo.motivo_cese = 'RENUNCIA'
        worker_activo.save()

        # La liquidación debe existir y estar calculada
        liq = LiquidacionLaboral.objects.get(personal=worker_activo)
        assert liq.estado == 'CALCULADA'
        assert liq.fecha_cese == date(2026, 6, 30)
        assert liq.total_bruto > Decimal('0')
        # Sueldo mes (30 días junio) = 3000
        assert liq.sueldo_mes_curso == Decimal('3000.00')
        # Junio = 6 meses gratif (S1 completo) → 3000
        assert liq.gratif_trunca == Decimal('3000.00')

    def test_signal_no_dispara_si_no_cesado(self, worker_activo):
        """Editar otros campos sin estado='Cesado' NO genera liquidación."""
        worker_activo.cargo = 'Otro Cargo'
        worker_activo.save()
        assert not LiquidacionLaboral.objects.filter(personal=worker_activo).exists()

    def test_signal_no_dispara_si_sin_fecha_cese(self, worker_activo):
        """estado='Cesado' SIN fecha_cese → no se crea liquidación."""
        worker_activo.estado = 'Cesado'
        worker_activo.fecha_cese = None
        worker_activo.save()
        assert not LiquidacionLaboral.objects.filter(personal=worker_activo).exists()


# ─── 3. Idempotencia ─────────────────────────────────────────────────────────

class TestIdempotencia:
    def test_cesar_dos_veces_no_duplica(self, worker_activo):
        """Guardar el Personal cesado dos veces no crea liquidación duplicada."""
        worker_activo.estado      = 'Cesado'
        worker_activo.fecha_cese  = date(2026, 6, 30)
        worker_activo.motivo_cese = 'RENUNCIA'
        worker_activo.save()
        liq_id_1 = LiquidacionLaboral.objects.get(personal=worker_activo).pk

        # Segundo save (idempotente)
        worker_activo.save()
        liq_id_2 = LiquidacionLaboral.objects.get(personal=worker_activo).pk

        assert liq_id_1 == liq_id_2
        assert LiquidacionLaboral.objects.filter(personal=worker_activo).count() == 1

    def test_recalcular_no_duplica(self, worker_cesado):
        """calcular() varias veces sobre la misma liquidación no duplica."""
        # worker_cesado dispara el signal y ya tiene liquidación.
        liq = LiquidacionLaboral.objects.get(personal=worker_cesado)
        liq.calcular()
        liq.calcular()
        liq.calcular()
        assert LiquidacionLaboral.objects.filter(personal=worker_cesado).count() == 1


# ─── 4. Indemnización por despido arbitrario ─────────────────────────────────

class TestIndemnizacion:
    def test_despido_arbitrario_calcula_indemnizacion(self, worker_activo):
        """
        Motivo DESPIDO_ARB con ~2 años → indemnización ≈ 1.5 × 2 × sueldo = 9000.
        Worker tiene alta 2024-01-15. Fecha cese 2026-01-31 → ~2 años + 16 días.
        """
        liq = LiquidacionLaboral.objects.create(
            personal=worker_activo,
            fecha_cese=date(2026, 1, 31),
            motivo_cese='DESPIDO_ARB',
        )
        liq.calcular()

        # 2 años completos × 1.5 × 3000 = 9000 (+ unos pocos por días restantes)
        assert liq.indemnizacion >= Decimal('9000.00')
        assert liq.indemnizacion < Decimal('9500.00')

    def test_renuncia_no_calcula_indemnizacion(self, worker_activo):
        """Motivo RENUNCIA → indemnización = 0."""
        liq = LiquidacionLaboral.objects.create(
            personal=worker_activo,
            fecha_cese=date(2026, 1, 31),
            motivo_cese='RENUNCIA',
        )
        liq.calcular()
        assert liq.indemnizacion == Decimal('0.00')

    def test_indemnizacion_tope_12_sueldos(self, subarea):
        """Tope = 12 sueldos. Trabajador con 15 años → tope debe aplicarse."""
        old_worker = Personal.objects.create(
            nro_doc='40000003',
            apellidos_nombres='VETERANO, ROCIO',
            cargo='Senior',
            tipo_trab='Empleado',
            estado='Activo',
            subarea=subarea,
            fecha_alta=date(2010, 1, 1),
            sueldo_base=Decimal('2000.00'),
            regimen_pension='AFP',
            afp='Prima',
        )
        liq = LiquidacionLaboral.objects.create(
            personal=old_worker,
            fecha_cese=date(2026, 1, 31),
            motivo_cese='DESPIDO_ARB',
        )
        liq.calcular()
        # 15+ años × 1.5 × 2000 = 45000, pero tope = 12 × 2000 = 24000
        assert liq.indemnizacion == Decimal('24000.00')


# ─── 5. Descuento de préstamo pendiente ──────────────────────────────────────

class TestDescuentos:
    def test_prestamo_pendiente_se_descuenta(self, worker_activo):
        """Préstamo EN_CURSO con saldo se descuenta en la liquidación."""
        from prestamos.models import Prestamo, TipoPrestamo
        tipo = TipoPrestamo.objects.create(
            nombre='Anticipo Test', codigo='anticipo-test', max_cuotas=12,
        )
        prestamo = Prestamo.objects.create(
            personal=worker_activo,
            tipo=tipo,
            monto_solicitado=Decimal('1000.00'),
            monto_aprobado=Decimal('1000.00'),
            num_cuotas=10,
            estado='EN_CURSO',
            fecha_solicitud=date(2026, 1, 1),
        )
        # Sin cuotas pagadas, saldo_pendiente = monto_efectivo = 1000

        liq = LiquidacionLaboral.objects.create(
            personal=worker_activo,
            fecha_cese=date(2026, 3, 31),
            motivo_cese='RENUNCIA',
        )
        liq.calcular()

        assert liq.prestamos_pendientes == Decimal('1000.00')
        # Neto = bruto - 1000 - AFP/ONP
        assert liq.total_neto == liq.total_bruto - Decimal('1000.00') - liq.descuento_pension

    def test_descuentos_manuales_no_se_sobrescriben_via_otros(self, worker_activo):
        """Descuentos manuales (embargo, otros) persisten tras calcular()."""
        liq = LiquidacionLaboral.objects.create(
            personal=worker_activo,
            fecha_cese=date(2026, 3, 31),
            motivo_cese='RENUNCIA',
            embargo=Decimal('500.00'),
            otros_descuentos=Decimal('150.00'),
        )
        liq.calcular()
        assert liq.embargo == Decimal('500.00')
        assert liq.otros_descuentos == Decimal('150.00')
        # Neto incluye estos descuentos + AFP/ONP
        assert liq.total_neto == liq.total_bruto - Decimal('650.00') - liq.descuento_pension


# ─── 6. API endpoint ─────────────────────────────────────────────────────────

class TestAPI:
    def test_api_liquidacion_no_cesado_400(self, client_logged, worker_activo):
        """GET API con trabajador activo → 400 + {error: 'no_cesado'}."""
        resp = client_logged.get(f'/nominas/api/liquidacion/{worker_activo.pk}/')
        assert resp.status_code == 400
        assert resp.json() == {'error': 'no_cesado'}

    def test_api_liquidacion_cesado_ok(self, client_logged, worker_cesado):
        """GET API con trabajador cesado → 200 + JSON con conceptos."""
        resp = client_logged.get(f'/nominas/api/liquidacion/{worker_cesado.pk}/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['personal_id']     == worker_cesado.pk
        assert data['personal_nombre'] == worker_cesado.apellidos_nombres
        assert data['estado']          in ('CALCULADA', 'APROBADA')
        assert Decimal(data['sueldo_mes_curso']) > Decimal('0')
        assert Decimal(data['total_bruto'])      > Decimal('0')
        assert 'gratif_trunca' in data
        assert 'cts_trunca'    in data

    def test_api_requiere_staff(self, client, worker_cesado):
        """Sin login → redirect a admin login."""
        resp = client.get(f'/nominas/api/liquidacion/{worker_cesado.pk}/')
        # staff_member_required redirige (302)
        assert resp.status_code in (302, 401, 403)


# ─── 7. Vista detalle + aprobación ───────────────────────────────────────────

class TestVistaDetalle:
    def test_detalle_renderiza(self, client_logged, worker_cesado):
        """GET /nominas/liquidacion/<id>/ retorna 200 con conceptos en HTML."""
        liq = LiquidacionLaboral.objects.get(personal=worker_cesado)
        url = reverse('nominas_liquidacion_laboral_detalle', args=[liq.pk])
        resp = client_logged.get(url)
        assert resp.status_code == 200
        assert b'Liquidaci' in resp.content
        assert b'Sueldo del mes en curso' in resp.content
        assert b'Aprobar' in resp.content

    def test_aprobar_cambia_estado(self, client_logged, worker_cesado, admin_user):
        """POST /aprobar/ cambia estado a APROBADA y registra aprobada_por."""
        liq = LiquidacionLaboral.objects.get(personal=worker_cesado)
        url = reverse('nominas_liquidacion_laboral_aprobar', args=[liq.pk])
        resp = client_logged.post(url)
        # Redirige al detalle
        assert resp.status_code == 302
        liq.refresh_from_db()
        assert liq.estado       == 'APROBADA'
        assert liq.aprobada_por == admin_user

    def test_aprobar_ya_aprobada_idempotente(self, client_logged, worker_cesado, admin_user):
        """Aprobar 2 veces no crashea ni regresa el estado."""
        liq = LiquidacionLaboral.objects.get(personal=worker_cesado)
        liq.estado = 'APROBADA'
        liq.aprobada_por = admin_user
        liq.save()

        url = reverse('nominas_liquidacion_laboral_aprobar', args=[liq.pk])
        resp = client_logged.post(url)
        assert resp.status_code == 302
        liq.refresh_from_db()
        assert liq.estado == 'APROBADA'
