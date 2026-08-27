from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_db


def _client(monkeypatch):
    monkeypatch.setattr(settings, "SKILL_AGENT_WORKER_ENABLED", False)
    import app.main as main_module

    async def _override_db():
        mock_db = AsyncMock()
        mock_res = MagicMock()
        mock_res.mappings.return_value.first.return_value = None
        mock_db.execute.return_value = mock_res
        yield mock_db

    with patch.object(main_module, "init_schema", new=AsyncMock()):
        main_module.app.dependency_overrides[get_db] = _override_db
        client = TestClient(main_module.app)
        try:
            yield client
        finally:
            main_module.app.dependency_overrides.clear()


def test_internal_run_requires_token(monkeypatch):
    monkeypatch.setattr(settings, "SKILL_AGENT_INTERNAL_TOKEN", "secret")
    for client in _client(monkeypatch):
        response = client.post(
            "/internal/v1/runs",
            json={"tool_name": "demo", "arguments": {}},
            headers={"X-Exec-Org-Id": "org-1", "X-Exec-User-Id": "user-1"},
        )
        assert response.status_code == 401


def test_internal_run_rejects_forged_org(monkeypatch):
    monkeypatch.setattr(settings, "SKILL_AGENT_INTERNAL_TOKEN", "secret")
    for client in _client(monkeypatch):
        response = client.post(
            "/internal/v1/runs",
            json={"run_id": "r1", "tool_name": "demo", "org_id": "other-org", "arguments": {}},
            headers={
                "X-Skill-Agent-Token": "secret",
                "X-Exec-Org-Id": "org-1",
                "X-Exec-User-Id": "user-1",
            },
        )
        assert response.status_code == 403


def test_internal_run_rejects_default_token(monkeypatch):
    monkeypatch.setattr(settings, "SKILL_AGENT_INTERNAL_TOKEN", "")
    for client in _client(monkeypatch):
        response = client.post(
            "/internal/v1/runs",
            json={"run_id": "r1", "tool_name": "demo", "arguments": {}},
            headers={
                "X-Skill-Agent-Token": "some-token",
                "X-Exec-Org-Id": "org-1",
                "X-Exec-User-Id": "user-1",
            },
        )
        assert response.status_code == 401


def test_health_check_db_status(monkeypatch):
    for client in _client(monkeypatch):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"
        assert data["service"] == "nodeskclaw-agent"


def test_internal_run_accepts_previous_token(monkeypatch):
    monkeypatch.setattr(settings, "SKILL_AGENT_INTERNAL_TOKEN", "new-secret")
    monkeypatch.setattr(settings, "SKILL_AGENT_INTERNAL_TOKEN_PREVIOUS", "old-secret")
    for client in _client(monkeypatch):
        # 1. Old secret succeeds
        resp1 = client.get(
            "/internal/v1/runs/r1",
            headers={
                "X-Skill-Agent-Token": "old-secret",
                "X-Exec-Org-Id": "org-1",
                "X-Exec-User-Id": "user-1",
            },
        )
        assert resp1.status_code != 401

        # 2. New secret succeeds
        resp2 = client.get(
            "/internal/v1/runs/r1",
            headers={
                "X-Skill-Agent-Token": "new-secret",
                "X-Exec-Org-Id": "org-1",
                "X-Exec-User-Id": "user-1",
            },
        )
        assert resp2.status_code != 401

