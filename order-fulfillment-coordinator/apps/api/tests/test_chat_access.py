from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from fulfillment.api import chat as module
from fulfillment.api.deps import get_current_user, get_db
from fulfillment.models.user import UserRole
from . import test_chat_1000 as chat_fixtures

chat_client = chat_fixtures.chat_client


@pytest.mark.parametrize("intent,message", [
    ("create_order", "create an order"), ("proceed_delivery", "route pending orders"),
    ("unknown", "customer@example.com"),
])
def test_viewer_cannot_mutate_orders_through_chat(chat_client, intent, message):
    client, _ = chat_client
    async def viewer():
        return SimpleNamespace(id="viewer", role=UserRole.VIEWER)
    client.app.dependency_overrides[get_current_user] = viewer
    create = AsyncMock()
    with patch.object(module, "detect_intent", AsyncMock(return_value=intent)), \
         patch.object(module, "_handle_create_order", create):
        response = client.post("/api/chat", json={"message": message})
    assert response.status_code == 403
    create.assert_not_awaited()


def test_chat_history_is_scoped_to_user_even_for_identical_public_session_ids(chat_client):
    client, factory = chat_client
    identity = "alice"
    async def persistent_db():
        async with factory() as db:
            yield db
            await db.commit()
    client.app.dependency_overrides[get_db] = persistent_db
    async def current_user():
        return SimpleNamespace(id=identity, role=UserRole.ADMIN)
    client.app.dependency_overrides[get_current_user] = current_user
    with patch.object(module, "detect_intent", AsyncMock(return_value="greeting")), \
         patch.object(module, "_openai_client", None):
        for identity in ("alice", "bob"):
            response = client.post("/api/chat", json={"message": f"Hello {identity}", "session_id": "same-session"})
            assert response.status_code == 200
            assert response.json()["session_id"] == "same-session"
        for identity in ("alice", "bob"):
            response = client.get("/api/chat/history", params={"session_id": "same-session"})
            assert response.status_code == 200
            user_messages = [m["content"] for m in response.json()["messages"] if m["role"] == "user"]
            assert user_messages == [f"Hello {identity}"]


def test_chat_refuses_missing_authenticated_identity(chat_client):
    client, _ = chat_client
    async def missing_identity():
        return {"role": "admin"}
    client.app.dependency_overrides[get_current_user] = missing_identity
    assert client.post("/api/chat", json={"message": "hello"}).status_code == 401
