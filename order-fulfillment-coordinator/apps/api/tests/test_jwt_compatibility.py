import base64
import hashlib
import hmac
import json
import time

import jwt
import pytest

from fulfillment import security


@pytest.fixture
def signing_key(monkeypatch):
    key = "isolated-jwt-compatibility-fixture-" * 2
    monkeypatch.setattr(security.settings, "jwt_secret", key)
    monkeypatch.setattr(security.settings, "jwt_algorithm", "HS256")
    return key


def test_accepts_existing_standard_hs256_token_serialization(signing_key):
    """The previous jose encoder used this same standard JWT wire format."""
    claims = {"sub": "fixture-user", "role": "operator", "typ": "access",
              "iat": int(time.time()), "exp": int(time.time()) + 60}
    def encode(value):
        return base64.urlsafe_b64encode(json.dumps(value, separators=(",", ":")).encode()).rstrip(b"=")
    content = encode({"alg": "HS256", "typ": "JWT"}) + b"." + encode(claims)
    signature = base64.urlsafe_b64encode(hmac.new(signing_key.encode(), content, hashlib.sha256).digest()).rstrip(b"=")
    assert security.decode_access_token((content + b"." + signature).decode()) == claims


@pytest.mark.parametrize("change", ["expired", "missing_exp", "missing_sub", "wrong_type", "wrong_key", "wrong_algorithm"])
def test_rejects_invalid_or_unbounded_tokens(signing_key, change):
    claims = {"sub": "fixture-user", "role": "viewer", "typ": "access",
              "iat": int(time.time()), "exp": int(time.time()) + 60}
    if change == "expired":
        claims["exp"] = int(time.time()) - 60
    elif change == "missing_exp":
        del claims["exp"]
    elif change == "missing_sub":
        del claims["sub"]
    elif change == "wrong_type":
        claims["typ"] = "refresh"
    token = jwt.encode(claims, "wrong-fixture-signing-key" * 2 if change == "wrong_key" else signing_key,
                       algorithm="HS512" if change == "wrong_algorithm" else "HS256")
    assert security.decode_access_token(token) is None
