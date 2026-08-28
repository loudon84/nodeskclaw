from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_db
from app.schemas import RunView


def _client(monkeypatch, mock_db=None):
    monkeypatch.setattr(settings, "SKILL_AGENT_WORKER_ENABLED", False)
    monkeypatch.setattr(settings, "SKILL_AGENT_INSECURE_MODE", True)
    import app.main as main_module

    if mock_db is None:
        mock_db = AsyncMock()
        mock_res = MagicMock()
        mock_res.mappings.return_value.first.return_value = None
        mock_res.first.return_value = ("0001_initial_agent_schema",)
        mock_db.execute.return_value = mock_res

    async def _override_db():
        yield mock_db

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


def test_internal_run_rejects_forged_user(monkeypatch):
    monkeypatch.setattr(settings, "SKILL_AGENT_INTERNAL_TOKEN", "secret")
    for client in _client(monkeypatch):
        response = client.post(
            "/internal/v1/runs",
            json={"run_id": "r1", "tool_name": "demo", "user_id": "other-user", "arguments": {}},
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


@pytest.mark.parametrize(
    "method,url,body",
    [
        ("POST", "/internal/v1/runs", {"run_id": "r1", "tool_name": "demo"}),
        ("GET", "/internal/v1/runs/r1", None),
        ("GET", "/internal/v1/runs/r1/events", None),
        ("GET", "/internal/v1/runs/r1/result", None),
        ("GET", "/internal/v1/runs/r1/artifacts", None),
        ("GET", "/internal/v1/runs/r1/artifacts/art1/bytes", None),
        ("POST", "/internal/v1/runs/r1/events/ingest", {"events": []}),
        ("POST", "/internal/v1/runs/r1/cancel", None),
        ("POST", "/internal/v1/runs/r1/resume", None),
        ("POST", "/internal/v1/runs/r1/approvals/appr1", None),
    ],
)
def test_all_10_routes_require_exec_org_id_fail_closed(monkeypatch, method, url, body):
    monkeypatch.setattr(settings, "SKILL_AGENT_INTERNAL_TOKEN", "secret")
    mock_db = AsyncMock()
    for client in _client(monkeypatch, mock_db=mock_db):
        headers = {"X-Skill-Agent-Token": "secret"}  # No X-Exec-Org-Id
        if method == "POST":
            resp = client.post(url, json=body or {}, headers=headers)
        else:
            resp = client.get(url, headers=headers)
        assert resp.status_code == 422
        # Verify no DB execution happened (fail-closed before DB query)
        assert not mock_db.execute.called


def test_ingest_rejects_forged_org_in_body(monkeypatch):
    monkeypatch.setattr(settings, "SKILL_AGENT_INTERNAL_TOKEN", "secret")
    for client in _client(monkeypatch):
        response = client.post(
            "/internal/v1/runs/r1/events/ingest",
            json={"org_id": "forged-org", "events": []},
            headers={
                "X-Skill-Agent-Token": "secret",
                "X-Exec-Org-Id": "org-1",
            },
        )
        assert response.status_code == 403


def test_canonical_response_models(monkeypatch):
    monkeypatch.setattr(settings, "SKILL_AGENT_INTERNAL_TOKEN", "secret")
    from app.services import run_service

    dummy_run = RunView(
        run_id="r1",
        org_id="org-1",
        user_id="user-1",
        tool_name="demo",
        status="COMPLETED",
        snapshot={},
        result={"summary": "done"},
        created_at="2026-08-27T00:00:00Z",
        updated_at="2026-08-27T00:00:00Z",
    )
    monkeypatch.setattr(run_service, "get_run", AsyncMock(return_value=dummy_run))
    monkeypatch.setattr(run_service, "list_events", AsyncMock(return_value=[]))
    monkeypatch.setattr(run_service, "list_artifacts", AsyncMock(return_value=[]))
    monkeypatch.setattr(run_service, "cancel_run", AsyncMock(return_value=dummy_run))
    monkeypatch.setattr(run_service, "approve_run", AsyncMock(return_value=dummy_run))

    headers = {
        "X-Skill-Agent-Token": "secret",
        "X-Exec-Org-Id": "org-1",
    }

    for client in _client(monkeypatch):
        # 1. GET /runs/{run_id} -> RunView
        r = client.get("/internal/v1/runs/r1", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["run_id"] == "r1"
        assert data["org_id"] == "org-1"

        # 2. GET /runs/{run_id}/events -> EventsResponse
        r = client.get("/internal/v1/runs/r1/events", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "next_seq" in data
        assert data["org_id"] == "org-1"

        # 3. GET /runs/{run_id}/result -> ResultResponse
        r = client.get("/internal/v1/runs/r1/result", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["org_id"] == "org-1"
        assert data["status"] == "COMPLETED"
        assert data["result"] == {"summary": "done"}

        # 4. GET /runs/{run_id}/artifacts -> ArtifactsResponse
        r = client.get("/internal/v1/runs/r1/artifacts", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert data["org_id"] == "org-1"

        # 5. POST /runs/{run_id}/cancel -> MutationResponse
        r = client.post("/internal/v1/runs/r1/cancel", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["org_id"] == "org-1"
        assert data["status"] == "COMPLETED"
        assert data["idempotent"] is True

        # 6. POST /runs/{run_id}/resume -> MutationResponse
        r = client.post("/internal/v1/runs/r1/resume", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["org_id"] == "org-1"
        assert data["idempotent"] is True


def test_dual_token_grace_period_rotation(monkeypatch):
    monkeypatch.setattr(settings, "SKILL_AGENT_INTERNAL_TOKEN", "new-secret")
    monkeypatch.setattr(settings, "SKILL_AGENT_INTERNAL_TOKEN_PREVIOUS", "old-secret")

    for client in _client(monkeypatch):
        # 1. New token accepted
        r1 = client.get(
            "/internal/v1/runs/r1",
            headers={"X-Skill-Agent-Token": "new-secret", "X-Exec-Org-Id": "org-1"},
        )
        assert r1.status_code != 401

        # 2. Previous token accepted during rotation
        r2 = client.get(
            "/internal/v1/runs/r1",
            headers={"X-Skill-Agent-Token": "old-secret", "X-Exec-Org-Id": "org-1"},
        )
        assert r2.status_code != 401

        # 3. Bad token rejected
        r3 = client.get(
            "/internal/v1/runs/r1",
            headers={"X-Skill-Agent-Token": "invalid-secret", "X-Exec-Org-Id": "org-1"},
        )
        assert r3.status_code == 401


def test_health_and_metrics_endpoints(monkeypatch):
    mock_db = AsyncMock()
    # Mock for metrics query
    mapping_res = MagicMock()
    mapping_res.mappings.return_value.all.return_value = [{"status": "COMPLETED", "count": 5}]
    mock_db.execute = AsyncMock(return_value=mapping_res)

    for client in _client(monkeypatch, mock_db=mock_db):
        # Health check
        h_resp = client.get("/health")
        assert h_resp.status_code == 200
        h_data = h_resp.json()
        assert h_data["status"] == "ok"
        assert h_data["database"] == "connected"

        # Liveness & Readiness probes
        live_resp = client.get("/health/live")
        assert live_resp.status_code == 200
        assert live_resp.json()["status"] == "ok"

        ready_resp = client.get("/health/ready")
        assert ready_resp.status_code == 200
        assert ready_resp.json()["database"] == "connected"

        # Metrics
        m_resp = client.get("/metrics")
        assert m_resp.status_code == 200
        m_data = m_resp.json()
        assert "runs_by_status" in m_data
        assert m_data["runs_by_status"].get("COMPLETED") == 5

