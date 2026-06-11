"""
Tests de core/crypto_fields.py — cifrado at-rest de credenciales.

Verifica que EncryptedCharField:
- cifra en BD (la columna almacena 'enc$...') y descifra al leer,
- tolera valores legacy en claro (pre-migración),
- mantiene vacíos como vacíos,
- y que el serializer de ConfiguracionSistema no expone ningún secreto.
"""
import pytest
from django.db import connection

from core.crypto_fields import PREFIX, decrypt_value, encrypt_value, is_encrypted
from empresas.models import Empresa


def _raw_column(table, column, pk):
    with connection.cursor() as cur:
        cur.execute(f'SELECT {column} FROM {table} WHERE id = %s', [pk])
        return cur.fetchone()[0]


# ════════════════════════════════════════════════════════════════
# Primitivas encrypt/decrypt
# ════════════════════════════════════════════════════════════════


class TestPrimitivas:

    def test_round_trip(self):
        stored = encrypt_value('mi-secreto-123')
        assert stored.startswith(PREFIX)
        assert decrypt_value(stored) == 'mi-secreto-123'

    def test_no_deterministico(self):
        # Fernet incluye IV/timestamp: dos cifrados del mismo valor difieren.
        assert encrypt_value('x') != encrypt_value('x')

    def test_is_encrypted(self):
        assert is_encrypted(encrypt_value('x'))
        assert not is_encrypted('password-plano')
        assert not is_encrypted('')
        assert not is_encrypted(None)


# ════════════════════════════════════════════════════════════════
# EncryptedCharField sobre Empresa
# ════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestEncryptedCharField:

    def _make_empresa(self, **kwargs):
        defaults = {'ruc': '20612345678', 'razon_social': 'Cifrado S.A.C.'}
        defaults.update(kwargs)
        return Empresa.objects.create(**defaults)

    def test_modelo_ve_claro_bd_guarda_cifrado(self):
        emp = self._make_empresa(email_host_password='app-password-123')

        emp.refresh_from_db()
        assert emp.email_host_password == 'app-password-123'

        raw = _raw_column('empresas_empresa', 'email_host_password', emp.pk)
        assert raw.startswith(PREFIX)
        assert 'app-password-123' not in raw

    def test_todos_los_campos_secretos_de_empresa(self):
        emp = self._make_empresa(
            email_host_password='smtp-pass',
            whatsapp_access_token='EAAB-token-meta',
            openclaw_gateway_token='oc-token',
        )
        for column, plain in [
            ('email_host_password', 'smtp-pass'),
            ('whatsapp_access_token', 'EAAB-token-meta'),
            ('openclaw_gateway_token', 'oc-token'),
        ]:
            raw = _raw_column('empresas_empresa', column, emp.pk)
            assert raw.startswith(PREFIX), column
            assert plain not in raw, column

        emp.refresh_from_db()
        assert emp.email_host_password == 'smtp-pass'
        assert emp.whatsapp_access_token == 'EAAB-token-meta'
        assert emp.openclaw_gateway_token == 'oc-token'

    def test_vacio_queda_vacio(self):
        emp = self._make_empresa()
        raw = _raw_column('empresas_empresa', 'email_host_password', emp.pk)
        assert raw == ''

    def test_legacy_en_claro_se_lee_tal_cual(self):
        # Simula una fila pre-migración: valor en claro directo en la columna.
        emp = self._make_empresa()
        with connection.cursor() as cur:
            cur.execute(
                'UPDATE empresas_empresa SET email_host_password = %s WHERE id = %s',
                ['password-legacy', emp.pk],
            )
        emp.refresh_from_db()
        assert emp.email_host_password == 'password-legacy'

    def test_resave_cifra_el_legacy(self):
        emp = self._make_empresa()
        with connection.cursor() as cur:
            cur.execute(
                'UPDATE empresas_empresa SET email_host_password = %s WHERE id = %s',
                ['password-legacy', emp.pk],
            )
        emp.refresh_from_db()
        emp.save(update_fields=['email_host_password'])

        raw = _raw_column('empresas_empresa', 'email_host_password', emp.pk)
        assert raw.startswith(PREFIX)
        assert decrypt_value(raw) == 'password-legacy'

    def test_get_smtp_config_usa_valor_claro(self):
        # El backend de email por empresa debe recibir la contraseña descifrada.
        emp = self._make_empresa(
            email_proveedor='GMAIL',
            email_host='smtp.gmail.com',
            email_host_user='rrhh@x.com',
            email_host_password='app-pass',
            email_from='noreply@x.com',
        )
        emp.refresh_from_db()
        assert emp.get_smtp_config()['password'] == 'app-pass'


# ════════════════════════════════════════════════════════════════
# Secretos de ConfiguracionSistema (asistencia) y ConfiguracionSMTP
# ════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestSingletonsCifrados:

    def test_configuracion_sistema_cifra_secretos(self):
        from asistencia.models import ConfiguracionSistema

        config, _ = ConfiguracionSistema.objects.get_or_create(pk=1)
        config.ia_api_key = 'gemini-key-abc'
        config.telegram_bot_token = '123456:bot-token'
        config.whatsapp_access_token = 'EAAB-meta'
        config.openclaw_gateway_token = 'oc-tok'
        config.zapsign_api_key = 'zs-key'
        config.ia_gemini_api_key = 'gem-ocr-key'
        config.save()
        table = ConfiguracionSistema._meta.db_table
        for column in [
            'ia_api_key', 'ia_gemini_api_key', 'zapsign_api_key',
            'telegram_bot_token', 'whatsapp_access_token', 'openclaw_gateway_token',
        ]:
            raw = _raw_column(table, column, config.pk)
            assert raw.startswith(PREFIX), column

        config = ConfiguracionSistema.objects.get(pk=config.pk)
        assert config.ia_api_key == 'gemini-key-abc'
        assert config.telegram_bot_token == '123456:bot-token'

    def test_configuracion_smtp_cifra_password(self):
        from comunicaciones.models import ConfiguracionSMTP

        smtp = ConfiguracionSMTP.get()
        smtp.smtp_password = 'smtp-secreta'
        smtp.save()

        raw = _raw_column(ConfiguracionSMTP._meta.db_table, 'smtp_password', smtp.pk)
        assert raw.startswith(PREFIX)
        assert ConfiguracionSMTP.get().smtp_password == 'smtp-secreta'


# ════════════════════════════════════════════════════════════════
# El serializer de API no expone secretos
# ════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestSerializerNoExponeSecretos:

    def test_configuracion_sistema_serializer_sin_secretos(self):
        from asistencia.api_serializers import ConfiguracionSistemaSerializer
        from asistencia.models import ConfiguracionSistema

        config, _ = ConfiguracionSistema.objects.get_or_create(pk=1)
        for campo in [
            'ia_api_key', 'ia_gemini_api_key', 'zapsign_api_key',
            'telegram_bot_token', 'whatsapp_access_token', 'openclaw_gateway_token',
        ]:
            setattr(config, campo, 'secret')
        config.save()
        data = ConfiguracionSistemaSerializer(config).data
        for campo in [
            'ia_api_key', 'ia_gemini_api_key', 'zapsign_api_key',
            'telegram_bot_token', 'whatsapp_access_token', 'openclaw_gateway_token',
        ]:
            assert campo not in data, f'{campo} expuesto por la API'
