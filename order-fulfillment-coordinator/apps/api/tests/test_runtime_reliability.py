from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest


def test_sqlite_debug_real_migration_auth_and_health(tmp_path):
    """Real SQLite and API requests; external health dependencies are explicitly mocked."""
    api = Path(__file__).resolve().parents[1]
    env = {**os.environ, "DATABASE_URL": f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}",
           "DEBUG": "true", "OPENAI_API_KEY": "", "QDRANT_URL": "",
           "PYTHONPATH": str(api / "src"), "INTEGRATION_SECRET_KEY": "",
           "JWT_SECRET": "isolated-auth-fixture", "WEBHOOK_SECRET": "isolated-webhook-fixture"}
    result = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=api,
                            env=env, capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, result.stderr
    code = '''
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
import fulfillment.main as main
with patch.object(main, "_safe_celery_health", AsyncMock(return_value={"connected":False})), patch.object(main, "_safe_qdrant_health", AsyncMock(return_value=False)):
 with TestClient(main.app) as client:
  payload={"email":"sqlite-fixture@example.com","password":"fixture-password","name":"SQLite Fixture"}
  registered=client.post("/api/auth/register",json=payload)
  assert registered.status_code==201, registered.text
  login=client.post("/api/auth/login",json={"email":payload["email"],"password":payload["password"]})
  assert login.status_code==200, login.text
  token=login.json()["access_token"]
  profile=client.get("/api/auth/me",headers={"Authorization":"Bearer "+token})
  assert profile.status_code==200 and profile.json()["email"]==payload["email"]
  assert client.post("/api/auth/login",json={"email":payload["email"],"password":"incorrect"}).status_code==401
  health=client.get("/health")
  assert health.status_code==200 and health.json()["database"]=="sqlite"
  assert health.json()["backends"]["postgres"] is False
'''
    result = subprocess.run([sys.executable, "-c", code], cwd=api, env=env,
                            capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, result.stderr[-4000:]


@pytest.mark.asyncio
@pytest.mark.parametrize("cycle_error", [False, True])
async def test_monitor_task_retries_input_failure_and_disposes_before_loop_close(monkeypatch, cycle_error):
    from fulfillment.tasks import monitor_cycle as task

    db = AsyncMock()
    context = AsyncMock()
    context.__aenter__.return_value = db
    monkeypatch.setattr(task, "async_session_factory", lambda: context)
    orchestrator = MagicMock()
    result = MagicMock(events=[{"type": "cycle_error"}] if cycle_error else [])
    result.model_dump.return_value = {"shipments_checked": 1}
    orchestrator.run_monitor_cycle = AsyncMock(return_value=result)
    monkeypatch.setattr(task, "FulfillmentOrchestrator", lambda _db: orchestrator)
    dispose = AsyncMock()
    monkeypatch.setattr(task, "engine", MagicMock(dispose=dispose))
    if cycle_error:
        with pytest.raises(RuntimeError, match="input state"):
            await task._run_monitor_cycle_async()
        db.commit.assert_not_awaited()
    else:
        assert await task._run_monitor_cycle_async() == {"shipments_checked": 1}
        db.commit.assert_awaited_once()
    dispose.assert_awaited_once()
