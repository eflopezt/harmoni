"""
Tests for the Dashboard Ejecutivo Unificado (core.views_dashboard).

Covers:
  - access control (anonymous → login redirect, admin → 200)
  - renders without breaking when there is no seed data
  - core KPIs land in the context
"""
import pytest
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.urls import reverse


URL_NAME = 'dashboard_ejecutivo'


@pytest.mark.django_db
class TestDashboardEjecutivoAccess(TestCase):
    """Access control tests."""

    def setUp(self):
        self.client = Client()
        self.url = reverse(URL_NAME)

    def test_anonymous_redirects_to_login(self):
        """Anonymous user should be redirected to login."""
        resp = self.client.get(self.url)
        # 302 redirect to login (LOGIN_URL or 'login')
        assert resp.status_code in (302, 301)
        assert '/login' in resp.url.lower() or 'login' in resp.url.lower()

    def test_regular_user_blocked(self):
        """Non-staff, non-superuser user should be denied (redirect)."""
        User.objects.create_user(username='basic', password='test1234')
        self.client.login(username='basic', password='test1234')
        resp = self.client.get(self.url)
        # user_passes_test redirects to login_url='login' when test fails
        assert resp.status_code in (302, 301)

    def test_admin_user_gets_200(self):
        """Superuser should get a 200 OK page."""
        User.objects.create_superuser(
            username='admin_dash', email='a@a.com', password='test1234'
        )
        self.client.login(username='admin_dash', password='test1234')
        resp = self.client.get(self.url)
        assert resp.status_code == 200

    def test_staff_user_gets_200(self):
        """Staff user (not superuser) should also have access."""
        User.objects.create_user(
            username='staff_dash', password='test1234', is_staff=True
        )
        self.client.login(username='staff_dash', password='test1234')
        resp = self.client.get(self.url)
        assert resp.status_code == 200


@pytest.mark.django_db
class TestDashboardEjecutivoContext(TestCase):
    """KPI / context tests — verify dashboard does not break with empty DB."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser(
            username='ceo', email='ceo@harmoni.pe', password='test1234'
        )
        self.client.login(username='ceo', password='test1234')
        self.url = reverse(URL_NAME)

    def test_renders_with_empty_db(self):
        """Without any seed data the view should still render OK."""
        resp = self.client.get(self.url)
        assert resp.status_code == 200

    def test_context_has_headline_kpis(self):
        """Headline KPI keys must appear in context."""
        resp = self.client.get(self.url)
        ctx = resp.context
        assert ctx is not None
        assert 'kpi_personal_activo' in ctx
        assert 'kpi_empresas_activas' in ctx
        assert 'kpi_nomina_mes' in ctx
        assert 'kpi_vacantes_abiertas' in ctx
        assert 'kpi_postulaciones_mes' in ctx
        assert 'kpi_contrataciones_mes' in ctx

    def test_context_has_charts(self):
        """Chart data must appear in context (always present, even if empty)."""
        resp = self.client.get(self.url)
        ctx = resp.context
        for key in (
            'chart_postulaciones', 'chart_personal_areas',
            'chart_headcount', 'chart_nomina',
        ):
            assert key in ctx, f'missing chart key: {key}'
        # Headcount / Nómina / postulaciones should have 6 month entries
        assert len(ctx['chart_headcount']['labels']) == 6
        assert len(ctx['chart_nomina']['labels']) == 6
        assert len(ctx['chart_postulaciones']['labels']) == 6

    def test_context_has_reclutamiento_metrics(self):
        """Reclutamiento panel context keys must be present."""
        resp = self.client.get(self.url)
        ctx = resp.context
        assert 'conversion_rate' in ctx
        assert 'tiempo_avg_contratacion' in ctx
        assert 'funnel_etapas' in ctx
        assert 'top_vacantes' in ctx

    def test_context_has_alertas(self):
        """Alertas should always be a list (possibly empty)."""
        resp = self.client.get(self.url)
        ctx = resp.context
        assert 'alertas' in ctx
        assert isinstance(list(ctx['alertas']), list)

    def test_empresa_filter_does_not_break(self):
        """Passing ?empresa=123 (no match) must not break view."""
        resp = self.client.get(self.url + '?empresa=99999')
        assert resp.status_code == 200

    def test_empresa_filter_invalid_does_not_break(self):
        """Passing ?empresa=abc (non-int) must not break view."""
        resp = self.client.get(self.url + '?empresa=invalid')
        assert resp.status_code == 200
