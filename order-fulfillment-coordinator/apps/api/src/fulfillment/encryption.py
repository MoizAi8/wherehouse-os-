"""At-rest encryption for secrets stored in the database.

Secrets such as Odoo API keys / passwords are encrypted before being persisted
and decrypted on read using a Fernet key supplied via the ``INTEGRATION_SECRET_KEY``
environment variable. When the key is absent (e.g. local dev without secrets),
encryption is a transparent no-op so the app still boots — but production MUST
set a strong key.
"""
from __future__ import annotations

import logging
import os

from cryptography.fernet import Fernet, InvalidToken

from fulfillment.config import settings

logger = logging.getLogger("fulfillment.encryption")

_fernet: Fernet | None = None


def _load_fernet() -> Fernet | None:
    global _fernet
    if _fernet is None:
        key = settings.integration_secret_key or os.environ.get("INTEGRATION_SECRET_KEY")
        if key:
            try:
                _fernet = Fernet(key.encode() if isinstance(key, str) else key)
            except (ValueError, TypeError) as exc:
                logger.warning("Invalid INTEGRATION_SECRET_KEY configured: %s", exc)
                _fernet = None
    return _fernet


def encrypt_secret(value: str | None) -> str | None:
    """Encrypt ``value`` for storage. Returns the ciphertext, or the original
    value when no encryption key is configured (dev fallback)."""
    if value is None:
        return None
    f = _load_fernet()
    if f is None:
        return value
    return f.encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str | None) -> str | None:
    """Decrypt a value produced by :func:`encrypt_secret`. Falls back to the
    plaintext value when no key is configured or decryption fails (so legacy
    plaintext rows keep working during rollout)."""
    if value is None:
        return None
    f = _load_fernet()
    if f is None:
        return value
    try:
        return f.decrypt(value.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        logger.warning("Decryption failed; returning value as-is: %s", exc)
        return value
