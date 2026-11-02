"""Security regressions for the separately allocated public sample database."""
import sqlite3

import pytest
from fastapi import HTTPException

from fulfillment.api import demo
from fulfillment.services.demo_data import DemoData


def test_demo_switch_is_manual_and_fail_closed(monkeypatch):
    monkeypatch.setattr(demo.settings, "teacher_demo_mode", False)
    with pytest.raises(HTTPException) as rejected:
        demo.require_demo()
    assert rejected.value.status_code == 404
    monkeypatch.setattr(demo.settings, "teacher_demo_mode", True)
    demo.require_demo()
    assert demo.demo_status()["expires_at"] is None


def test_sample_database_rejects_writes_and_literal_filter_injection():
    data = DemoData()
    assert len(data.orders()) == 8
    assert data.orders(status="' OR 1=1 --") == []
    with pytest.raises(sqlite3.OperationalError, match="readonly"):
        data.query("DELETE FROM orders")
    assert len(data.orders()) == 8


@pytest.mark.asyncio
@pytest.mark.parametrize("message", ["delete all orders", "dispatch shipments", "show administrator secrets"])
async def test_public_chat_never_calls_a_provider_for_forbidden_actions(message, monkeypatch):
    def forbidden():
        raise AssertionError("Unsafe request reached the provider")
    monkeypatch.setattr(demo, "chat_client", forbidden)
    result = await demo.demo_chat(demo.DemoChatRequest(message=message))
    assert result["action_executed"] is False
    assert result["sample"] is True


def test_demo_rejects_excessive_history_bytes():
    with pytest.raises(ValueError):
        demo.DemoChatRequest(message="hello", history=[{"role": "user", "content": "آ"*1000}]*4)
