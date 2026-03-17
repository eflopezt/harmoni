"""
Tests for the Analytics module — KPISnapshot, AlertaRRHH, DashboardWidget.

Uses pytest with Django TestCase.
"""
import pytest
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from analytics.models import KPISnapshot, AlertaRRHH, DashboardWidget


# ═══════════════════════════════════════════════════════════════════
# KPISnapshot
# ═══════════════════════════════════════════════════════════════════

class TestKPISnapshotCreation(TestCase):
    """Test creation and basic behaviour of KPISnapshot."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='admin_kpi', password='test1234'
        )

    def test_create_snapshot_with_defaults(self):
        """A snapshot created with only the required 'periodo' should have 0-defaults."""
        snap = KPISnapshot.objects.create(periodo=date(2026, 1, 1))
        assert snap.total_empleados == 0
        assert snap.altas_mes == 0
        assert snap.bajas_mes == 0
        assert snap.tasa_rotacion == Decimal('0')
        assert snap.tasa_asistencia == Decimal('0')
        assert snap.costo_nomina_bruto == Decimal('0')

    def test_create_snapshot_with_metrics(self):
        """Create a fully populated snapshot and verify all fields persist."""
        snap = KPISnapshot.objects.create(
            periodo=date(2026, 2, 1),
            total_empleados=150,
            empleados_staff=100,
            empleados_rco=50,
            altas_mes=5,
            bajas_mes=2,
            tasa_rotacion=Decimal('1.33'),
            tasa_rotacion_voluntaria=Decimal('0.67'),
            tasa_asistencia=Decimal('96.50'),
            total_he_mes=Decimal('320.00'),
            promedio_he_persona=Decimal('4.57'),
            dias_vacaciones_pendientes=1200,
            promedio_dias_pendientes=Decimal('8.0'),
            horas_capacitacion_mes=Decimal('48.00'),
            empleados_capacitados=30,
            cobertura_capacitacion=Decimal('20.00'),
            costo_nomina_bruto=Decimal('750000.00'),
            costo_promedio_empleado=Decimal('5000.00'),
            generado_por=self.user,
        )
        snap.refresh_from_db()
        assert snap.total_empleados == 150
        assert snap.empleados_staff == 100
        assert snap.empleados_rco == 50
        assert snap.tasa_rotacion == Decimal('1.33')
        assert snap.tasa_asistencia == Decimal('96.50')
        assert snap.total_he_mes == Decimal('320.00')
        assert snap.costo_nomina_bruto == Decimal('750000.00')
        assert snap.generado_por == self.user

    def test_str_representation(self):
        snap = KPISnapshot.objects.create(periodo=date(2026, 3, 1))
        assert str(snap) == 'KPI 2026-03'

    def test_unique_periodo_constraint(self):
        """Only one snapshot per periodo is allowed."""
        KPISnapshot.objects.create(periodo=date(2026, 1, 1))
        with pytest.raises(IntegrityError):
            KPISnapshot.objects.create(periodo=date(2026, 1, 1))

    def test_ordering_by_periodo_descending(self):
        """Snapshots are ordered by periodo descending (most recent first)."""
        KPISnapshot.objects.create(periodo=date(2025, 12, 1))
        KPISnapshot.objects.create(periodo=date(2026, 1, 1))
        KPISnapshot.objects.create(periodo=date(2026, 2, 1))
        periodos = list(KPISnapshot.objects.values_list('periodo', flat=True))
        assert periodos == [date(2026, 2, 1), date(2026, 1, 1), date(2025, 12, 1)]

    def test_generado_por_set_null_on_user_delete(self):
        """Deleting the user who generated the snapshot sets generado_por to NULL."""
        snap = KPISnapshot.objects.create(
            periodo=date(2026, 4, 1), generado_por=self.user
        )
        self.user.delete()
        snap.refresh_from_db()
        assert snap.generado_por is None

    def test_creado_en_auto_populated(self):
        snap = KPISnapshot.objects.create(periodo=date(2026, 5, 1))
        assert snap.creado_en is not None


# ═══════════════════════════════════════════════════════════════════
# AlertaRRHH
# ═══════════════════════════════════════════════════════════════════

class TestAlertaRRHH(TestCase):
    """Test creation, severity, and resolution of AlertaRRHH."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='admin_alerts', password='test1234'
        )

    def _create_alerta(self, **kwargs):
        defaults = {
            'titulo': 'Test alert',
            'descripcion': 'Some description',
            'categoria': 'ROTACION',
            'severidad': 'INFO',
        }
        defaults.update(kwargs)
        return AlertaRRHH.objects.create(**defaults)

    def test_create_alerta_defaults(self):
        """New alerts default to estado=ACTIVA and severidad=INFO."""
        alerta = self._create_alerta()
        assert alerta.estado == 'ACTIVA'
        assert alerta.severidad == 'INFO'
        assert alerta.creado_en is not None

    def test_str_representation(self):
        alerta = self._create_alerta(
            titulo='Rotacion alta en TI', severidad='CRITICAL'
        )
        assert str(alerta) == '[CRITICAL] Rotacion alta en TI'

    def test_all_severity_levels(self):
        """All three severity levels are valid."""
        for sev in ('INFO', 'WARN', 'CRITICAL'):
            alerta = self._create_alerta(severidad=sev, titulo=f'Alert {sev}')
            assert alerta.severidad == sev

    def test_all_categoria_choices(self):
        """All category choices are accepted."""
        categorias = [
            'ROTACION', 'ASISTENCIA', 'DOCUMENTOS', 'VACACIONES',
            'CAPACITACION', 'DISCIPLINARIA', 'CONTRATOS', 'OTRO',
        ]
        for cat in categorias:
            alerta = self._create_alerta(categoria=cat, titulo=f'Alert {cat}')
            assert alerta.categoria == cat

    def test_resolve_alerta(self):
        """Resolving an alert sets estado, resuelta_por, fecha_resolucion, and notas."""
        alerta = self._create_alerta()
        now = timezone.now()
        alerta.estado = 'RESUELTA'
        alerta.resuelta_por = self.user
        alerta.fecha_resolucion = now
        alerta.notas_resolucion = 'Fixed the issue'
        alerta.save()
        alerta.refresh_from_db()
        assert alerta.estado == 'RESUELTA'
        assert alerta.resuelta_por == self.user
        assert alerta.fecha_resolucion is not None
        assert alerta.notas_resolucion == 'Fixed the issue'

    def test_discard_alerta(self):
        """Discarding an alert sets estado to DESCARTADA."""
        alerta = self._create_alerta()
        alerta.estado = 'DESCARTADA'
        alerta.save()
        alerta.refresh_from_db()
        assert alerta.estado == 'DESCARTADA'

    def test_valor_actual_y_umbral(self):
        """valor_actual and valor_umbral store threshold comparisons."""
        alerta = self._create_alerta(
            valor_actual=Decimal('15.50'),
            valor_umbral=Decimal('10.00'),
        )
        assert alerta.valor_actual == Decimal('15.50')
        assert alerta.valor_umbral == Decimal('10.00')

    def test_ordering_by_creado_en_descending(self):
        """Alerts ordered by creado_en descending (newest first)."""
        a1 = self._create_alerta(titulo='First')
        a2 = self._create_alerta(titulo='Second')
        ids = list(AlertaRRHH.objects.values_list('id', flat=True))
        assert ids == [a2.id, a1.id]

    def test_filter_active_alerts(self):
        """Filter only active alerts."""
        self._create_alerta(titulo='Active 1')
        self._create_alerta(titulo='Active 2')
        resolved = self._create_alerta(titulo='Resolved', estado='RESUELTA')
        activas = AlertaRRHH.objects.filter(estado='ACTIVA')
        assert activas.count() == 2
        assert resolved not in activas

    def test_filter_by_categoria(self):
        self._create_alerta(titulo='Rot 1', categoria='ROTACION')
        self._create_alerta(titulo='Vac 1', categoria='VACACIONES')
        rot = AlertaRRHH.objects.filter(categoria='ROTACION')
        assert rot.count() == 1

    def test_filter_by_severidad(self):
        self._create_alerta(titulo='Info', severidad='INFO')
        self._create_alerta(titulo='Crit', severidad='CRITICAL')
        critical = AlertaRRHH.objects.filter(severidad='CRITICAL')
        assert critical.count() == 1


# ═══════════════════════════════════════════════════════════════════
# DashboardWidget
# ═══════════════════════════════════════════════════════════════════

class TestDashboardWidget(TestCase):
    """Test DashboardWidget creation and configuration."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='dashboard_user', password='test1234'
        )

    def test_create_widget(self):
        widget = DashboardWidget.objects.create(
            user=self.user,
            titulo='Headcount por Area',
            chart_type='bar',
            data_source='areas',
            config_json={
                'labels': ['TI', 'RRHH', 'Finanzas'],
                'values': [30, 15, 20],
                'colors': ['#FF6384', '#36A2EB', '#FFCE56'],
            },
        )
        assert widget.activo is True
        assert widget.posicion == 0
        assert widget.chart_type == 'bar'
        assert widget.config_json['labels'] == ['TI', 'RRHH', 'Finanzas']

    def test_str_representation(self):
        widget = DashboardWidget.objects.create(
            user=self.user,
            titulo='Rotacion Mensual',
            chart_type='line',
            data_source='headcount',
        )
        assert str(widget) == 'Rotacion Mensual (dashboard_user)'

    def test_ordering_by_position(self):
        """Widgets are ordered by posicion then by creado_en desc."""
        w1 = DashboardWidget.objects.create(
            user=self.user, titulo='W1', chart_type='bar',
            data_source='a', posicion=2,
        )
        w2 = DashboardWidget.objects.create(
            user=self.user, titulo='W2', chart_type='bar',
            data_source='b', posicion=1,
        )
        w3 = DashboardWidget.objects.create(
            user=self.user, titulo='W3', chart_type='bar',
            data_source='c', posicion=1,
        )
        titulos = list(
            DashboardWidget.objects.values_list('titulo', flat=True)
        )
        # posicion=1 first (w3 before w2 by creado_en desc), then posicion=2
        assert titulos == ['W3', 'W2', 'W1']

    def test_deactivate_widget(self):
        widget = DashboardWidget.objects.create(
            user=self.user, titulo='To Deactivate',
            chart_type='doughnut', data_source='genero',
        )
        widget.activo = False
        widget.save()
        widget.refresh_from_db()
        assert widget.activo is False

    def test_config_json_defaults_to_empty_dict(self):
        widget = DashboardWidget.objects.create(
            user=self.user, titulo='Minimal',
            chart_type='bar', data_source='headcount',
        )
        assert widget.config_json == {}

    def test_widgets_deleted_on_user_cascade(self):
        """Deleting the user cascades to delete their widgets."""
        DashboardWidget.objects.create(
            user=self.user, titulo='W1',
            chart_type='bar', data_source='x',
        )
        DashboardWidget.objects.create(
            user=self.user, titulo='W2',
            chart_type='line', data_source='y',
        )
        assert DashboardWidget.objects.count() == 2
        self.user.delete()
        assert DashboardWidget.objects.count() == 0

    def test_multiple_users_widgets_isolated(self):
        """Each user sees only their own widgets."""
        user2 = User.objects.create_user(username='other_user', password='pw')
        DashboardWidget.objects.create(
            user=self.user, titulo='Mine',
            chart_type='bar', data_source='a',
        )
        DashboardWidget.objects.create(
            user=user2, titulo='Theirs',
            chart_type='bar', data_source='b',
        )
        mine = DashboardWidget.objects.filter(user=self.user)
        assert mine.count() == 1
        assert mine.first().titulo == 'Mine'
