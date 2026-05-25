"""
Tests para PlanStarterMiddleware y is_starter_user.

Cubre:
- is_starter_user() resuelve vía Empresa.plan == 'STARTER' (caso producción)
- is_starter_user() resuelve vía STARTER_USERNAMES fallback (caso demo)
- Anonymous user no es starter
- URLs bloqueadas redirigen a /upgrade/
- URLs permitidas siguen accesibles
- ALWAYS_ALLOW (admin, static, login) bypasses el middleware
- Demo y Enterprise no son afectados
"""
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import Client, RequestFactory

from core.middleware_plan_starter import (
    PlanStarterMiddleware,
    is_starter_user,
    is_blocked_path,
    STARTER_USERNAMES,
    STARTER_BLOCKED_RE,
)


User = get_user_model()


# ═══════════════════════════════════════════════════════════════════════
# is_starter_user — resolución del flag
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestIsStarterUser:
    def test_anonymous_user_no_es_starter(self):
        assert is_starter_user(AnonymousUser()) is False

    def test_username_en_whitelist_es_starter(self):
        u = User.objects.create_user(username='demo2', password='x')
        assert is_starter_user(u) is True

    def test_username_fuera_de_whitelist_no_es_starter(self):
        u = User.objects.create_user(username='otro_user', password='x')
        assert is_starter_user(u) is False

    def test_empresa_plan_starter_via_personal(self):
        """Si user.personal.empresa.plan == 'STARTER', is_starter_user() = True."""
        from empresas.models import Empresa
        from personal.models import Personal
        emp = Empresa.objects.create(
            ruc='20999888777', razon_social='Test Starter SAC',
            plan='STARTER',
        )
        u = User.objects.create_user(username='admin_starter', password='x')
        Personal.objects.create(
            usuario=u, empresa=emp,
            nro_doc='99999999',
            apellidos_nombres='Starter, Test',
            cargo='Admin', tipo_trab='Empleado',
        )
        assert is_starter_user(u) is True

    def test_empresa_plan_profesional_no_es_starter(self):
        from empresas.models import Empresa
        from personal.models import Personal
        emp = Empresa.objects.create(
            ruc='20888777666', razon_social='Test Profesional SAC',
            plan='PROFESIONAL',
        )
        u = User.objects.create_user(username='admin_prof', password='x')
        Personal.objects.create(
            usuario=u, empresa=emp,
            nro_doc='88888888',
            apellidos_nombres='Profesional, Test',
            cargo='Admin', tipo_trab='Empleado',
        )
        assert is_starter_user(u) is False

    def test_user_sin_personal_recae_en_username_whitelist(self):
        """Si el user no tiene Personal asociado, usar whitelist."""
        u = User.objects.create_user(username='demo2', password='x')
        # No creamos Personal → recae en whitelist
        assert is_starter_user(u) is True


# ═══════════════════════════════════════════════════════════════════════
# is_blocked_path — patrón regex
# ═══════════════════════════════════════════════════════════════════════

class TestIsBlockedPath:
    def test_paths_enterprise_son_bloqueados(self):
        bloqueadas = [
            '/reclutamiento/',
            '/reclutamiento/pipeline/',
            '/personal/organigrama/',
            '/personal/contratos/',
            '/personal/roster/matricial/',
            '/calendario/',
            '/capacitaciones/',
            '/evaluaciones/',
            '/disciplinaria/',
            '/asistencia/banco-horas/',
            '/asistencia/solicitudes-he/',
            '/workflows/',
            '/salarios/',
            '/prestamos/',
            '/comunicaciones/',
            '/comunicaciones/campanas/',
            '/encuestas/',
            '/analytics/',
            '/integraciones/',
            '/viaticos/',
            '/portal/',
            '/mi-portal/',
            '/mi-portal/mi-nomina/',
            '/documentos/boletas/mis/',
            '/sistema/dashboard/ejecutivo/',
            '/sistema/reporte-bi-mensual/',
            '/empresas/pulse/',
            '/roster/gastro/',
            '/onboarding/gastro/',
            '/reportes/planilla/pdf/',
            '/reportes/asistencia/pdf/',
            '/nominas/boletas/123/notificar/',
            '/nominas/notificar/',
            '/documentos/vencimientos/notificar/',
            '/disciplinaria/45/notificar/',
            '/documentos/legajo/42/pdf/',
            '/asistencia/reportes/areas/',
            '/asistencia/reportes/pivote/',
            '/asistencia/reportes/kpis-cross/',
            '/asistencia/reportes/masivo/',
            '/asistencia/reportes/123/pdf/',
            '/asistencia/reportes/123/enviar/',
        ]
        for path in bloqueadas:
            assert is_blocked_path(path), f'Esperaba que {path} estuviera bloqueado'

    def test_paths_core_no_son_bloqueados(self):
        permitidos = [
            '/',
            '/personal/',
            '/asistencia/',
            '/asistencia/papeletas/',
            '/asistencia/papeletas/reporte/',
            '/asistencia/reportes/',           # panel matricial básico
            '/asistencia/reportes/listado/',
            '/nominas/',
            '/nominas/boletas/123/',           # boleta NO notificar es OK
            '/vacaciones/',
            '/documentos/',
            '/cierre/',
            '/empresas/',
            '/sistema/',
            '/buscar/',
            '/upgrade/',
            '/d/starter/',
            '/admin/',
            '/login/',
            '/cuenta/',
        ]
        for path in permitidos:
            assert not is_blocked_path(path), f'{path} NO debería estar bloqueado'


# ═══════════════════════════════════════════════════════════════════════
# PlanStarterMiddleware — comportamiento end-to-end
# ═══════════════════════════════════════════════════════════════════════

@pytest.mark.django_db
class TestPlanStarterMiddleware:
    def setup_method(self):
        self.factory = RequestFactory()
        # Stub get_response que devuelve un response simple
        self.middleware = PlanStarterMiddleware(lambda r: _Resp())

    def _build_request(self, path, user):
        request = self.factory.get(path)
        request.user = user
        # Django middleware necesita messages framework setup mínimo
        request._messages = _DummyMessages()
        return request

    def test_anonymous_pasa_sin_filtrar(self):
        """Usuario anónimo no debe ser afectado por el middleware Starter."""
        request = self._build_request('/reclutamiento/', AnonymousUser())
        response = self.middleware(request)
        assert getattr(response, 'is_redirect', False) is False  # No redirige

    def test_user_no_starter_pasa_sin_filtrar(self):
        u = User.objects.create_user(username='admin_normal', password='x', is_superuser=True)
        request = self._build_request('/reclutamiento/', u)
        response = self.middleware(request)
        assert getattr(response, 'is_redirect', False) is False

    def test_starter_user_bloqueado_en_url_enterprise(self):
        from django.http import HttpResponseRedirect
        u = User.objects.create_user(username='demo2', password='x')
        request = self._build_request('/reclutamiento/', u)
        response = self.middleware(request)
        assert isinstance(response, HttpResponseRedirect)
        # Debería redirigir a /upgrade/
        assert '/upgrade/' in response['Location'] or response['Location'] == '/'

    def test_starter_user_permitido_en_url_core(self):
        u = User.objects.create_user(username='demo2', password='x')
        request = self._build_request('/personal/', u)
        response = self.middleware(request)
        # No es HttpResponseRedirect → pasa al get_response stub (devuelve _Resp)
        assert isinstance(response, _Resp)

    def test_starter_user_permitido_en_admin(self):
        u = User.objects.create_user(username='demo2', password='x')
        request = self._build_request('/admin/login/', u)
        response = self.middleware(request)
        assert isinstance(response, _Resp)

    def test_starter_user_permitido_en_upgrade(self):
        u = User.objects.create_user(username='demo2', password='x')
        request = self._build_request('/upgrade/', u)
        response = self.middleware(request)
        assert isinstance(response, _Resp)


# ═══════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════

class _Resp:
    """Stub de HttpResponse para los tests."""
    is_redirect = False
    status_code = 200


class _DummyMessages:
    """Stub mínimo del messages framework para que request._messages exista."""
    def add(self, *args, **kwargs):
        pass
