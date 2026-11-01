from cryptography.fernet import Fernet
import pytest

from fulfillment import encryption
from fulfillment.config import Settings
from fulfillment.rate_limit import RateLimitMiddleware


@pytest.fixture
def production_encryption(monkeypatch):
    monkeypatch.setattr(encryption.settings, "debug", False)
    monkeypatch.setattr(encryption, "_fernet", None)


@pytest.mark.parametrize("key", ["", "invalid-key"])
def test_production_encryption_refuses_missing_or_invalid_keys(monkeypatch, production_encryption, key):
    monkeypatch.delenv("INTEGRATION_SECRET_KEY", raising=False)
    monkeypatch.setattr(encryption.settings, "integration_secret_key", key)
    with pytest.raises(RuntimeError):
        encryption.encrypt_secret("sensitive-value")


def test_production_encryption_round_trip_and_wrong_key(monkeypatch, production_encryption):
    monkeypatch.setattr(encryption.settings, "integration_secret_key", Fernet.generate_key().decode())
    ciphertext = encryption.encrypt_secret("sensitive-value")
    assert ciphertext != "sensitive-value"
    assert encryption.decrypt_secret(ciphertext) == "sensitive-value"
    monkeypatch.setattr(encryption, "_fernet", None)
    monkeypatch.setattr(encryption.settings, "integration_secret_key", Fernet.generate_key().decode())
    with pytest.raises(RuntimeError, match="could not be decrypted"):
        encryption.decrypt_secret(ciphertext)
    with pytest.raises(RuntimeError):
        encryption.decrypt_secret("legacy-plaintext")


def test_production_boot_rejects_malformed_fernet_key():
    settings = Settings(_env_file=None, debug=False, jwt_secret="x" * 40,
                        webhook_secret="y" * 40, integration_secret_key="invalid-key")
    with pytest.raises(RuntimeError, match="Fernet"):
        settings.validate_production()


def test_rate_limiter_reclaims_idle_clients_after_the_refill_window():
    from fulfillment.rate_limit import _Bucket

    bucket = _Bucket(1, 60)
    assert bucket.take(bucket.timestamp)
    assert not bucket.is_stale(bucket.timestamp + 59, 60)
    assert bucket.is_stale(bucket.timestamp + 61, 60)


@pytest.mark.asyncio
async def test_public_health_is_rate_limited_with_retry_after(monkeypatch):
    from fulfillment.config import settings
    from httpx import ASGITransport, AsyncClient

    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_default", "1/hour")

    async def endpoint(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    app = RateLimitMiddleware(endpoint)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/health")).status_code == 200
        limited = await client.get("/health")
        assert limited.status_code == 429
        assert int(limited.headers["retry-after"]) > 0
