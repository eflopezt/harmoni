"""
Tests E2E para features finales del Plan Starter:
- Wizard onboarding /onboarding/starter/ (3 pasos)
- API /api/v1/me/plan/
- Auto-login /d/<slug>/ con rate limit
- Dashboard /cuenta/plan/
"""
import json
import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client
from django.urls import reverse


User = get_user_model()


# ═══════════════════════════════════════════════════════════════════════
# Wizard onboarding /onboarding/starter/
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestWizardOnboardingStarter:
    def setup_method(self):
        cache.clear()
        self.client = Client(HTTP_HOST='demo.harmoni.pe', SERVER_NAME='demo.harmoni.pe')

    def test_step1_get_renders(self):
        r = self.client.get('/onboarding/starter/')
        assert r.status_code == 200
        content = r.content.decode('utf-8', errors='ignore')
        assert 'RUC' in content
        assert 'paso 1' in content.lower() or 'paso  1' in content.lower() or 'paso&nbsp;1' in content.lower() or '1 de 3' in content.lower()

    def test_step1_post_valida_ruc_corto(self):
        r = self.client.post('/onboarding/starter/', {
            'ruc': '123',
            'razon_social': 'Test SAC',
        })
        assert r.status_code == 200  # re-renderiza con errores
        assert 'RUC debe tener 11 d' in r.content.decode('utf-8', errors='ignore')

    def test_step1_post_valido_redirige_step2(self):
        r = self.client.post('/onboarding/starter/', {
            'ruc': '20111222333',
            'razon_social': 'Test SAC',
            'email_rrhh': 'test@example.com',
            'telefono': '+51 999 888 777',
        })
        assert r.status_code == 302
        assert '/onboarding/starter/admin/' in r['Location']

    def test_step2_sin_step1_redirige(self):
        """Si llegas directo a step2 sin completar step1 → vuelve a step1."""
        r = self.client.get('/onboarding/starter/admin/')
        assert r.status_code == 302
        assert '/onboarding/starter/' in r['Location']

    def test_step2_valida_password_corta(self):
        # Completar step1
        self.client.post('/onboarding/starter/', {
            'ruc': '20111222333', 'razon_social': 'Test SAC',
        })
        r = self.client.post('/onboarding/starter/admin/', {
            'username': 'admin', 'first_name': 'Edwin', 'last_name': 'Test',
            'email': 'a@b.c', 'password': '123', 'password_confirm': '123',
        })
        assert r.status_code == 200
        assert 'al menos 8' in r.content.decode('utf-8', errors='ignore')

    def test_step3_completo_crea_empresa_y_user(self):
        from empresas.models import Empresa

        # Step 1
        self.client.post('/onboarding/starter/', {
            'ruc': '20999000111', 'razon_social': 'Wizard Test SAC',
            'email_rrhh': 'rrhh@wtest.pe', 'telefono': '+51 111 222 333',
        })
        # Step 2
        self.client.post('/onboarding/starter/admin/', {
            'username': 'wtest_admin', 'first_name': 'Admin', 'last_name': 'Wizard',
            'email': 'admin@wtest.pe',
            'password': 'unaClaveLarga123!', 'password_confirm': 'unaClaveLarga123!',
        })
        # Step 3 GET — renderiza confirmación
        r = self.client.get('/onboarding/starter/listo/')
        assert r.status_code == 200

        # Step 3 POST — activar
        r2 = self.client.post('/onboarding/starter/listo/')
        assert r2.status_code == 302  # redirect a /

        # Verifica creación
        emp = Empresa.objects.get(ruc='20999000111')
        assert emp.plan == 'ASISTENCIA'
        assert emp.razon_social == 'Wizard Test SAC'
        assert User.objects.filter(username='wtest_admin', is_staff=True).exists()


# ═══════════════════════════════════════════════════════════════════════
# API /api/v1/me/plan/
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAPIMePlan:
    def setup_method(self):
        self.client = Client(HTTP_HOST='demo.harmoni.pe', SERVER_NAME='demo.harmoni.pe')

    def test_requiere_autenticacion(self):
        r = self.client.get('/api/v1/me/plan/')
        # 401 (DRF) o 403
        assert r.status_code in (401, 403)

    def test_user_sin_personal_devuelve_default(self):
        u = User.objects.create_user(username='loose_user', password='x')
        self.client.force_login(u)
        r = self.client.get('/api/v1/me/plan/')
        assert r.status_code == 200
        data = json.loads(r.content)
        assert data['plan'] in ('ASISTENCIA', 'SUITE')   # sin empresa → default Suite
        assert 'features_bloqueadas' in data
        assert 'upgrade_url' in data
        assert data['empresa'] is None

    def test_user_starter_via_whitelist(self):
        u = User.objects.create_user(username='demo2', password='x')
        self.client.force_login(u)
        r = self.client.get('/api/v1/me/plan/')
        data = json.loads(r.content)
        assert data['es_starter'] is True
        assert data['plan'] == 'ASISTENCIA'
        assert data['max_trabajadores'] == 50


# ═══════════════════════════════════════════════════════════════════════
# Auto-login /d/<slug>/ con rate-limit
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestAutoLoginRateLimit:
    def setup_method(self):
        cache.clear()
        self.client = Client(HTTP_HOST='demo.harmoni.pe', SERVER_NAME='demo.harmoni.pe')
        # Crear el user demo2 que el endpoint busca
        User.objects.get_or_create(username='demo2', defaults={'password': 'x'})

    def test_slug_valido_redirige(self):
        r = self.client.get('/d/starter/')
        assert r.status_code == 302
        assert r['Location'] == '/'

    def test_slug_invalido_404(self):
        r = self.client.get('/d/inexistente/')
        assert r.status_code == 404

    def test_host_no_demo_404(self):
        c = Client(HTTP_HOST='harmoni.pe', SERVER_NAME='harmoni.pe')
        r = c.get('/d/starter/')
        assert r.status_code == 404

    def test_rate_limit_bloquea_despues_de_10(self):
        results = [self.client.get('/d/starter/').status_code for _ in range(12)]
        # 10 primeros = 302, los siguientes = 429
        successes = sum(1 for s in results if s == 302)
        blocks    = sum(1 for s in results if s == 429)
        assert successes == 10
        assert blocks == 2


# ═══════════════════════════════════════════════════════════════════════
# Dashboard /cuenta/plan/
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestDashboardMiCuenta:
    def setup_method(self):
        self.client = Client(HTTP_HOST='demo.harmoni.pe', SERVER_NAME='demo.harmoni.pe')

    def test_requiere_login(self):
        r = self.client.get('/cuenta/plan/')
        # Login redirect
        assert r.status_code == 302
        assert 'login' in r['Location'].lower()

    def test_user_autenticado_ve_dashboard(self):
        u = User.objects.create_user(username='demo2', password='x')
        self.client.force_login(u)
        r = self.client.get('/cuenta/plan/')
        assert r.status_code == 200
        content = r.content.decode('utf-8', errors='ignore')
        assert 'Plan' in content
        assert 'Trabajadores' in content
