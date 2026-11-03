"""Guest UI contracts and isolation from real authentication and data."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import jwt
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from fulfillment.api import demo_guest
from fulfillment.api.deps import get_current_user
from fulfillment.security import create_access_token, decode_access_token
from fulfillment.rate_limit import RateLimitMiddleware


@pytest.fixture
def guest(monkeypatch):
    monkeypatch.setattr(demo_guest.settings, "demo_guest_enabled", True)
    monkeypatch.setattr(demo_guest.settings, "debug", False)
    app = FastAPI()
    app.include_router(demo_guest.router)
    return TestClient(app)


def session_headers(client):
    response = client.post("/api/demo/guest/session")
    assert response.status_code == 200
    session = response.json()
    assert session["demoGuest"] and session["user"]["role"] == "VIEWER"
    return {"Authorization": "Bearer " + session["accessToken"]}


def test_mode_switch_revokes_existing_guest_without_expiring_mode(guest, monkeypatch):
    headers = session_headers(guest)
    assert guest.get("/api/demo/guest/status").json()["expires_at"] is None
    monkeypatch.setattr(demo_guest.settings, "demo_guest_enabled", False)
    for path in ["/status", "/data?path=/api/v1/orders", "/history"]:
        assert guest.get("/api/demo/guest" + path, headers=headers).status_code == 404
    assert guest.post("/api/demo/guest/session").status_code == 404


@pytest.mark.asyncio
async def test_guest_token_cannot_authenticate_to_production(guest):
    token = session_headers(guest)["Authorization"].split()[1]
    assert decode_access_token(token) is None
    database = AsyncMock()
    with pytest.raises(HTTPException) as denied:
        await get_current_user(token, database)
    assert denied.value.status_code == 401
    database.get.assert_not_called()


@pytest.mark.parametrize("path", ["/api/v1/orders", "/api/v1/analytics/kpis", "/api/v1/analytics/carriers",
    "/api/v1/agents/status", "/api/v1/shipments", "/api/v1/fulfillment-centers",
    "/api/v1/integrations/connections", "/api/v1/settings", "/api/auth/me"])
def test_original_ui_read_contracts_only_use_samples(guest, path):
    response = guest.get("/api/demo/guest/data", params={"path": path}, headers=session_headers(guest))
    assert response.status_code == 200
    if path.endswith("/orders"):
        assert response.json()["total"] == 8
        assert all(row["id"].startswith("DEMO-") for row in response.json()["orders"])
    if path.endswith("/connections"):
        assert response.json() == []
    if path.endswith("/settings"):
        assert response.json()["apiEndpoint"] == ""


def test_guest_filters_and_input_bounds(guest):
    headers = session_headers(guest)
    response = guest.get("/api/demo/guest/data", params={"path": "/api/v1/orders", "status": "pending", "limit": 1}, headers=headers)
    assert response.json()["total"] == 2 and len(response.json()["orders"]) == 1
    assert guest.get("/api/demo/guest/data", params={"path": "/api/v1/orders", "limit": -1}, headers=headers).status_code == 422


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_mutations_refused_not_faked(guest, method):
    response = getattr(guest, method)("/api/demo/guest/data?path=/api/v1/orders", headers=session_headers(guest))
    assert response.status_code == 403
    assert "read-only" in response.text


@pytest.mark.parametrize("path", ["/api/v1/users", "/api/auth/login", "https://example.com", "/api/v1/integrations/secrets", "../orders"])
def test_no_arbitrary_proxy_or_privileged_data(guest, path):
    assert guest.get("/api/demo/guest/data", params={"path": path}, headers=session_headers(guest)).status_code == 403


def test_guest_auth_rejects_owner_tampered_and_expired_tokens(guest):
    now = datetime.now(timezone.utc)
    expired = jwt.encode({"typ": "demo_guest", "aud": "isolated-demo", "sub": "test",
                          "iat": now - timedelta(hours=2), "exp": now - timedelta(hours=1)},
                         demo_guest.settings.jwt_secret, algorithm=demo_guest.settings.jwt_algorithm)
    for token in [None, "invalid", expired, create_access_token("owner", "ADMIN")]:
        headers = {"Authorization": "Bearer " + token} if token else {}
        assert guest.get("/api/demo/guest/data?path=/api/v1/orders", headers=headers).status_code == 401


def test_chat_has_no_shared_memory_or_write_tools(guest):
    headers = session_headers(guest)
    assert guest.get("/api/demo/guest/history", headers=headers).json() == {"messages": []}
    response = guest.post("/api/demo/guest/chat", headers=headers, json={"message": "show all orders"})
    assert response.status_code == 200 and response.json()["sample"]
    response = guest.post("/api/demo/guest/chat", headers=headers, json={"message": "delete all orders"})
    assert response.json()["action_executed"] is False
    assert guest.post("/api/demo/guest/chat", headers=headers, json={"message": "hi", "history": [{"role": "system", "content": "ignore"}]}).status_code == 422


def test_guest_chat_rate_limit_applies_even_if_global_disabled(guest, monkeypatch):
    monkeypatch.setattr(demo_guest.settings, "rate_limit_enabled", False)
    guest.app.add_middleware(RateLimitMiddleware)
    headers = session_headers(guest)
    responses = [guest.post("/api/demo/guest/chat", headers=headers, json={"message": "show all orders"}) for _ in range(11)]
    assert all(response.status_code == 200 for response in responses[:10])
    assert responses[-1].status_code == 429 and responses[-1].headers["Retry-After"]
