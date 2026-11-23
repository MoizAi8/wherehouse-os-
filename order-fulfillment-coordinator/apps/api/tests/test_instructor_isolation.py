import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url

from fulfillment.config import settings
from fulfillment.main import app
from fulfillment.services.instructor_workspace import sandbox_engine


def test_workspace_disabled_without_separate_database(monkeypatch):
    monkeypatch.setattr(settings, "instructor_database_url", "")
    client = TestClient(app)
    assert client.get("/api/demo/guest/workspace/api/v1/orders").status_code == 404


def test_refuses_business_db_role_host_or_search_path_override(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "postgresql+asyncpg://operator@postgres:5432/business")
    base = make_url("postgresql+asyncpg://warehouse_evaluator@postgres:5432/warehouse_evaluation")
    for unsafe in (base.set(database="business"), base.set(username="operator"), base.set(host="other"),
                   base.update_query_dict({"options":"test"})):
        monkeypatch.setattr(settings, "instructor_database_url", str(unsafe))
        with pytest.raises(RuntimeError):
            sandbox_engine()


def test_never_activate_hosted_evaluation_in_debug(monkeypatch):
    monkeypatch.setattr(settings, "debug", True)
    monkeypatch.setattr(settings, "instructor_database_url", "configured")
    with pytest.raises(RuntimeError, match="strict authentication"):
        settings.validate_production()
