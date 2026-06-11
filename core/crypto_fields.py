"""
Campos cifrados at-rest para credenciales de integraciones.

`EncryptedCharField` cifra el valor con Fernet (AES-128-CBC + HMAC-SHA256)
antes de escribirlo en BD y lo descifra al leerlo. El modelo en memoria
siempre ve el valor en claro; la columna almacena `enc$<token fernet>`.

Clave de cifrado (en orden de prioridad):
  1. settings.HARMONI_ENCRYPTION_KEYS — una o varias claves Fernet
     (urlsafe base64 de 32 bytes) separadas por coma. La primera se usa
     para cifrar; todas para descifrar (rotación de claves).
  2. Derivada de SECRET_KEY (sha256 → base64). Sin configuración extra,
     pero rotar SECRET_KEY invalida los valores cifrados — si se rota,
     poner la clave derivada vieja en HARMONI_ENCRYPTION_KEYS.

Limitaciones por diseño:
- NO usar en campos que se consultan con .filter()/.exclude(): el
  ciphertext no es determinístico (los tokens de lookup de documentos,
  p.ej. zapsign_token, quedan fuera a propósito).
- max_length valida el valor EN CLARO; la columna en BD es TEXT.
- Valores legacy en claro (sin prefijo enc$) se leen tal cual; la
  migración de datos de cada app los cifra al aplicar el deploy.
"""
import base64
import hashlib
import logging
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.db import models

logger = logging.getLogger(__name__)

PREFIX = 'enc$'


@lru_cache(maxsize=8)
def _fernet_for(key_material: str) -> MultiFernet:
    keys = [k.strip() for k in key_material.split(',') if k.strip()]
    return MultiFernet([Fernet(k) for k in keys])


def _get_fernet() -> MultiFernet:
    explicit = getattr(settings, 'HARMONI_ENCRYPTION_KEYS', '') or ''
    if explicit:
        return _fernet_for(explicit)
    derived = base64.urlsafe_b64encode(
        hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    ).decode()
    return _fernet_for(derived)


def encrypt_value(value: str) -> str:
    """Cifra un valor en claro → 'enc$<token>'."""
    return PREFIX + _get_fernet().encrypt(value.encode()).decode()


def decrypt_value(stored: str) -> str:
    """Descifra un valor 'enc$<token>' → claro. Lanza InvalidToken si la clave no corresponde."""
    return _get_fernet().decrypt(stored[len(PREFIX):].encode()).decode()


def is_encrypted(value) -> bool:
    return isinstance(value, str) and value.startswith(PREFIX)


class EncryptedCharField(models.CharField):
    """CharField cifrado at-rest. Ver docstring del módulo."""

    def get_internal_type(self):
        # Columna TEXT: el ciphertext excede max_length (que valida el claro).
        return 'TextField'

    def from_db_value(self, value, expression, connection):
        if value is None or not value.startswith(PREFIX):
            return value  # vacío o legacy en claro (pre-migración)
        try:
            return decrypt_value(value)
        except InvalidToken:
            # Clave rotada sin re-cifrar: no romper la carga del modelo,
            # la integración fallará en auth y el admin re-ingresa el valor.
            logger.warning(
                'No se pudo descifrar %s.%s — ¿SECRET_KEY/HARMONI_ENCRYPTION_KEYS rotada?',
                self.model.__name__ if hasattr(self, 'model') else '?', self.name,
            )
            return ''

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None or value == '':
            return value
        value = str(value)
        if value.startswith(PREFIX):
            return value  # ya cifrado (p.ej. re-save de un valor preparado)
        return encrypt_value(value)
