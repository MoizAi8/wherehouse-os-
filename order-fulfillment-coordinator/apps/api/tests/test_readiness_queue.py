"""Readiness must execute real work independently of stale historical probes."""
from unittest.mock import Mock

from fulfillment.tasks.health import celery_worker_health
from fulfillment.tasks.monitor_cycle import celery_app


def test_readiness_uses_separate_expiring_queue(monkeypatch):
    result = Mock()
    result.get.return_value = "pong"
    send = Mock(return_value=result)
    monkeypatch.setattr(celery_app, "send_task", send)
    assert celery_worker_health(timeout=5) == {"connected": True, "detail": "pong"}
    assert send.call_args.kwargs == {"queue": "readiness", "expires": 10.0}
    result.get.assert_called_once_with(timeout=5)


def test_readiness_requires_actual_pong(monkeypatch):
    result = Mock()
    result.get.return_value = "unexpected"
    monkeypatch.setattr(celery_app, "send_task", Mock(return_value=result))
    assert celery_worker_health()["connected"] is False


def test_readiness_timeout_remains_unhealthy(monkeypatch):
    result = Mock()
    result.get.side_effect = TimeoutError("worker did not execute probe")
    monkeypatch.setattr(celery_app, "send_task", Mock(return_value=result))
    health = celery_worker_health()
    assert health["connected"] is False
    assert "TimeoutError" in health["detail"]
