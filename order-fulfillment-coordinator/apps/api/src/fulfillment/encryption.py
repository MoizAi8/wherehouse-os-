"""At-rest encryption for secrets stored in the database.

Secrets such as Odoo API keys / passwords are encrypted before being persisted
and decrypted on read using a Fernet key supplied via the ``INTEGRATION_SECRET_KEY``
environment variable. When the key is absent (e.g. local dev without secrets),
encryption is a transparent no-op only in DEBUG mode. Production refuses
missing/invalid keys and undecryptable credentials.
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
                if not settings.debug:
                    raise RuntimeError("Integration encryption key is invalid") from exc
                logger.warning("Invalid INTEGRATION_SECRET_KEY configured: %s", exc)
                _fernet = None
        elif not settings.debug:
            raise RuntimeError("Integration encryption key is required")
    return _fernet


def encrypt_secret(value: str | None) -> str | None:
    """Encrypt for storage; plaintext fallback is limited to DEBUG mode."""
    if value is None:
        return None
    f = _load_fernet()
    if f is None:
        return value
    return f.encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(value: str | None) -> str | None:
    """Decrypt stored credentials. Legacy plaintext fallback is DEBUG-only."""
    if value is None:
        return None
    f = _load_fernet()
    if f is None:
        return value
    try:
        return f.decrypt(value.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        if not settings.debug:
            raise RuntimeError("Integration credential could not be decrypted") from exc
        logger.warning("Decryption failed; returning value as-is: %s", exc)
        return value
