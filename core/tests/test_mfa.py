"""
Tests del MFA TOTP (core/views_mfa.py + core/middleware_mfa.py).

Cubre:
- Activación: QR + confirmación con token válido; token inválido no confirma.
- Enforcement: usuario con device confirmado y sesión sin verificar es
  redirigido a /cuenta/2fa/verificar/; tras verificar, navega normal.
- Usuario SIN device navega sin fricción (política opt-in, no lockout).
- Desactivar exige contraseña correcta.
"""
import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from django_otp.oath import totp
from django_otp.plugins.otp_totp.models import TOTPDevice


@pytest.fixture
def usuario(db):
    return User.objects.create_user("seguro", "s@s.com", "clave-mfa-1", is_staff=True)


@pytest.fixture
def cliente(client, usuario):
    client.login(username="seguro", password="clave-mfa-1")
    return client


def _token_de(device):
    """Genera el token TOTP vigente para un device (mismo algoritmo)."""
    return totp(device.bin_key, device.step, device.t0, device.digits, device.drift)


class TestActivacion:
    def test_activar_muestra_qr_y_confirma_con_token(self, cliente, usuario):
        resp = cliente.get(reverse("mfa_activar"))
        assert resp.status_code == 200
        assert b"data:image/png;base64," in resp.content

        device = TOTPDevice.objects.get(user=usuario, confirmed=False)
        resp = cliente.post(reverse("mfa_activar"), {"token": str(_token_de(device)).zfill(6)})
        assert resp.status_code == 302
        device.refresh_from_db()
        assert device.confirmed is True

    def test_token_invalido_no_confirma(self, cliente, usuario):
        cliente.get(reverse("mfa_activar"))
        device = TOTPDevice.objects.get(user=usuario, confirmed=False)
        cliente.post(reverse("mfa_activar"), {"token": "000001"})
        device.refresh_from_db()
        assert device.confirmed is False


class TestEnforcement:
    def test_sin_device_navega_normal(self, cliente):
        resp = cliente.get("/", follow=False)
        # No redirige al verificador MFA
        assert "/cuenta/2fa/verificar/" not in resp.headers.get("Location", "")

    def test_con_device_confirmado_redirige_a_verificar(self, cliente, usuario):
        TOTPDevice.objects.create(user=usuario, name="t", confirmed=True)
        resp = cliente.get("/", follow=False)
        assert resp.status_code == 302
        assert resp.headers["Location"].startswith(reverse("mfa_verificar"))

    def test_verificar_con_token_desbloquea(self, cliente, usuario):
        device = TOTPDevice.objects.create(user=usuario, name="t", confirmed=True)
        resp = cliente.post(
            reverse("mfa_verificar"),
            {"token": str(_token_de(device)).zfill(6), "next": "/"},
        )
        assert resp.status_code == 302
        # Ya verificado: navegar no vuelve a redirigir al verificador
        resp = cliente.get("/", follow=False)
        assert "/cuenta/2fa/verificar/" not in resp.headers.get("Location", "")

    def test_exentos_no_bloqueados(self, cliente, usuario):
        TOTPDevice.objects.create(user=usuario, name="t", confirmed=True)
        # La propia página de verificación y health no entran en loop
        assert cliente.get(reverse("mfa_verificar")).status_code == 200
        assert cliente.get("/health/").status_code in (200, 301, 302)


class TestDesactivar:
    def test_password_incorrecta_no_desactiva(self, cliente, usuario):
        TOTPDevice.objects.create(user=usuario, name="t", confirmed=True)
        # Verificar primero para poder navegar
        device = TOTPDevice.objects.get(user=usuario)
        cliente.post(reverse("mfa_verificar"), {"token": str(_token_de(device)).zfill(6)})

        cliente.post(reverse("mfa_desactivar"), {"password": "mala"})
        assert TOTPDevice.objects.filter(user=usuario).exists()

    def test_password_correcta_desactiva(self, cliente, usuario):
        device = TOTPDevice.objects.create(user=usuario, name="t", confirmed=True)
        cliente.post(reverse("mfa_verificar"), {"token": str(_token_de(device)).zfill(6)})

        cliente.post(reverse("mfa_desactivar"), {"password": "clave-mfa-1"})
        assert not TOTPDevice.objects.filter(user=usuario).exists()
