"""
Tests for the Empresa model and EmpresaEmailBackend — empresas module.
"""
import pytest
from unittest.mock import patch, MagicMock


from empresas.models import Empresa
from empresas.email_backend import (
    EmpresaEmailBackend,
    set_current_empresa,
    get_current_empresa,
)


# ────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────

def _make_empresa(**kwargs):
    defaults = {
        "ruc": "20123456789",
        "razon_social": "Constructora Harmoni S.A.C.",
    }
    defaults.update(kwargs)
    return Empresa.objects.create(**defaults)


def _make_empresa_with_smtp(**kwargs):
    """Create an Empresa with a fully configured Gmail SMTP."""
    defaults = {
        "ruc": "20999888777",
        "razon_social": "Empresa con SMTP S.A.C.",
        "email_proveedor": "GMAIL",
        "email_host": "smtp.gmail.com",
        "email_port": 587,
        "email_use_tls": True,
        "email_use_ssl": False,
        "email_host_user": "rrhh@empresa.com",
        "email_host_password": "app-password-123",
        "email_from": "noreply@empresa.com",
        "email_reply_to": "rrhh@empresa.com",
    }
    defaults.update(kwargs)
    return Empresa.objects.create(**defaults)


# ════════════════════════════════════════════════════════════════
# Empresa model tests
# ════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestEmpresaModel:
    """Tests for the Empresa model."""

    # ── es_principal uniqueness ────────────────────────────────

    def test_only_one_empresa_can_be_principal(self):
        e1 = _make_empresa(ruc="20100000001", es_principal=True)
        e2 = _make_empresa(ruc="20100000002", es_principal=True)

        e1.refresh_from_db()
        e2.refresh_from_db()
        assert e1.es_principal is False
        assert e2.es_principal is True

    def test_saving_non_principal_does_not_affect_existing(self):
        e1 = _make_empresa(ruc="20200000001", es_principal=True)
        _make_empresa(ruc="20200000002", es_principal=False)

        e1.refresh_from_db()
        assert e1.es_principal is True

    def test_reassign_principal(self):
        e1 = _make_empresa(ruc="20300000001", es_principal=True)
        e2 = _make_empresa(ruc="20300000002", es_principal=False)

        # Switch principal to e2
        e2.es_principal = True
        e2.save()

        e1.refresh_from_db()
        assert e1.es_principal is False
        assert e2.es_principal is True

    # ── auto_fill_smtp() — Gmail ───────────────────────────────

    def test_auto_fill_smtp_gmail(self):
        e = _make_empresa(ruc="20400000001", email_proveedor="GMAIL")
        e.email_host = ""  # ensure blank so auto_fill kicks in
        e.auto_fill_smtp()

        assert e.email_host == "smtp.gmail.com"
        assert e.email_port == 587
        assert e.email_use_tls is True
        assert e.email_use_ssl is False

    def test_auto_fill_smtp_gmail_no_overwrite(self):
        """auto_fill_smtp should NOT overwrite an existing host."""
        e = _make_empresa(
            ruc="20400000002",
            email_proveedor="GMAIL",
            email_host="custom.smtp.server",
        )
        e.auto_fill_smtp()
        assert e.email_host == "custom.smtp.server"

    # ── auto_fill_smtp() — Office 365 ─────────────────────────

    def test_auto_fill_smtp_office365(self):
        e = _make_empresa(ruc="20500000001", email_proveedor="OFFICE365")
        e.email_host = ""
        e.auto_fill_smtp()

        assert e.email_host == "smtp.office365.com"
        assert e.email_port == 587
        assert e.email_use_tls is True
        assert e.email_use_ssl is False

    # ── auto_fill_smtp() — NONE/CUSTOM ─────────────────────────

    def test_auto_fill_smtp_none_does_nothing(self):
        e = _make_empresa(ruc="20500000002", email_proveedor="NONE")
        e.email_host = ""
        e.auto_fill_smtp()
        assert e.email_host == ""

    def test_auto_fill_smtp_custom_does_nothing(self):
        e = _make_empresa(ruc="20500000003", email_proveedor="CUSTOM")
        e.email_host = ""
        e.auto_fill_smtp()
        assert e.email_host == ""

    # ── tiene_email_configurado property ───────────────────────

    def test_tiene_email_configurado_true(self):
        e = _make_empresa_with_smtp()
        assert bool(e.tiene_email_configurado) is True

    def test_tiene_email_configurado_false_when_none(self):
        e = _make_empresa(email_proveedor="NONE")
        assert bool(e.tiene_email_configurado) is False

    def test_tiene_email_configurado_false_missing_host(self):
        e = _make_empresa(
            ruc="20600000001",
            email_proveedor="GMAIL",
            email_host="",
            email_host_user="user@test.com",
            email_host_password="secret",
        )
        assert bool(e.tiene_email_configurado) is False

    def test_tiene_email_configurado_false_missing_password(self):
        e = _make_empresa(
            ruc="20600000002",
            email_proveedor="GMAIL",
            email_host="smtp.gmail.com",
            email_host_user="user@test.com",
            email_host_password="",
        )
        assert bool(e.tiene_email_configurado) is False

    def test_tiene_email_configurado_false_missing_user(self):
        e = _make_empresa(
            ruc="20600000003",
            email_proveedor="GMAIL",
            email_host="smtp.gmail.com",
            email_host_user="",
            email_host_password="secret",
        )
        assert bool(e.tiene_email_configurado) is False

    # ── get_smtp_config() ──────────────────────────────────────

    def test_get_smtp_config_returns_dict(self):
        e = _make_empresa_with_smtp()
        config = e.get_smtp_config()

        assert isinstance(config, dict)
        assert config["host"] == "smtp.gmail.com"
        assert config["port"] == 587
        assert config["username"] == "rrhh@empresa.com"
        assert config["password"] == "app-password-123"
        assert config["use_tls"] is True
        assert config["use_ssl"] is False
        assert config["from_email"] == "noreply@empresa.com"
        assert config["reply_to"] == "rrhh@empresa.com"

    def test_get_smtp_config_from_email_fallback(self):
        """When email_from is blank, from_email should fall back to email_host_user."""
        e = _make_empresa_with_smtp(ruc="20700000001", email_from="")
        config = e.get_smtp_config()
        assert config["from_email"] == "rrhh@empresa.com"

    def test_get_smtp_config_returns_none_when_not_configured(self):
        e = _make_empresa(email_proveedor="NONE")
        assert e.get_smtp_config() is None

    # ── __str__ / nombre_display ───────────────────────────────

    def test_str_with_nombre_comercial(self):
        e = _make_empresa(
            ruc="20800000001",
            razon_social="Razón Formal S.A.",
            nombre_comercial="MiMarca",
        )
        assert str(e) == "MiMarca (20800000001)"

    def test_str_without_nombre_comercial(self):
        e = _make_empresa(
            ruc="20800000002",
            razon_social="Solo Razón S.A.C.",
            nombre_comercial="",
        )
        assert str(e) == "Solo Razón S.A.C. (20800000002)"

    def test_nombre_display_property(self):
        e = _make_empresa(
            ruc="20800000003",
            razon_social="Formal",
            nombre_comercial="Comercial",
        )
        assert e.nombre_display == "Comercial"


# ════════════════════════════════════════════════════════════════
# EmpresaEmailBackend tests
# ════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestEmpresaEmailBackend:
    """Tests for the multi-tenant email backend."""

    def setup_method(self):
        """Clean thread-local state before each test."""
        set_current_empresa(None)

    def teardown_method(self):
        set_current_empresa(None)

    def test_fallback_to_django_defaults_when_no_empresa(self):
        """When no empresa is set, the backend should use Django's default settings."""
        set_current_empresa(None)

        backend = EmpresaEmailBackend(fail_silently=True)
        # SmtpEmailBackend reads from django.conf.settings by default
        from django.conf import settings
        assert backend.host == getattr(settings, "EMAIL_HOST", "localhost")
        assert backend.port == getattr(settings, "EMAIL_PORT", 25)

    def test_fallback_when_empresa_has_no_smtp(self):
        """When empresa exists but SMTP is not configured, use Django defaults."""
        empresa = _make_empresa(email_proveedor="NONE")
        set_current_empresa(empresa)

        backend = EmpresaEmailBackend(fail_silently=True)
        from django.conf import settings
        assert backend.host == getattr(settings, "EMAIL_HOST", "localhost")

    def test_uses_empresa_smtp_when_configured(self):
        """When empresa has SMTP configured, the backend should use those settings."""
        empresa = _make_empresa_with_smtp(ruc="20900000001")
        set_current_empresa(empresa)

        backend = EmpresaEmailBackend(fail_silently=True)
        assert backend.host == "smtp.gmail.com"
        assert backend.port == 587
        assert backend.username == "rrhh@empresa.com"
        assert backend.password == "app-password-123"
        assert backend.use_tls is True
        assert backend.use_ssl is False

    def test_send_messages_overrides_from_email(self):
        """send_messages should replace the default from_email with empresa's."""
        empresa = _make_empresa_with_smtp(ruc="20900000002")
        set_current_empresa(empresa)

        backend = EmpresaEmailBackend(fail_silently=True)

        msg = MagicMock()
        msg.from_email = "webmaster@localhost"
        msg.reply_to = []

        # Patch the actual SMTP send to avoid network calls
        with patch.object(backend, "open", return_value=True):
            with patch.object(
                type(backend).__mro__[1],  # SmtpEmailBackend
                "send_messages",
                return_value=1,
            ):
                backend.send_messages([msg])

        assert msg.from_email == "noreply@empresa.com"
        assert msg.reply_to == ["rrhh@empresa.com"]

    def test_send_messages_preserves_custom_from_email(self):
        """send_messages should NOT override from_email if it is already custom."""
        empresa = _make_empresa_with_smtp(ruc="20900000003")
        set_current_empresa(empresa)

        backend = EmpresaEmailBackend(fail_silently=True)

        msg = MagicMock()
        msg.from_email = "custom-sender@other.com"
        msg.reply_to = ["already@set.com"]

        with patch.object(backend, "open", return_value=True):
            with patch.object(
                type(backend).__mro__[1],
                "send_messages",
                return_value=1,
            ):
                backend.send_messages([msg])

        # Should keep the custom values
        assert msg.from_email == "custom-sender@other.com"
        assert msg.reply_to == ["already@set.com"]

    def test_thread_local_get_set(self):
        """set_current_empresa / get_current_empresa round-trip."""
        assert get_current_empresa() is None

        empresa = _make_empresa(ruc="20900000004")
        set_current_empresa(empresa)
        assert get_current_empresa() == empresa

        set_current_empresa(None)
        assert get_current_empresa() is None
