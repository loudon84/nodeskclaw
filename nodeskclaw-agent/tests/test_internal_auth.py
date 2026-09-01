from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import get_db
from app.schemas import RunView
from app.services.readiness import expected_alembic_heads

DEFAULT_HEAD = next(iter(expected_alembic_heads()))


def _mock_session_local(monkeypatch, mock_db: AsyncMock) -> None:
    import app.main as main_module

    class _SessionCtx:
        async def __aenter__(self):
            return mock_db

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(main_module, "SessionLocal", lambda: _SessionCtx())


def _default_health_mock_db() -> AsyncMock:
    mock_db = AsyncMock()
    mock_ok = MagicMock()
    mock_version = MagicMock()
    mock_version.fetchall.return_value = [(DEFAULT_HEAD,)]
    run_res = MagicMock()
    run_res.mappings.return_value.first.return_value = None

    async def _execute(sql, *args, **kwargs):
        sql_text = str(sql)
        if "alembic_version" in sql_text:
            return mock_version
        if 'FROM "' in sql_text and ".runs" in sql_text:
            return run_res
        return mock_ok

    mock_db.execute = AsyncMock(side_effect=_execute)
    return mock_db


def _client(monkeypatch, mock_db=None):
    monkeypatch.setattr(settings, "SKILL_AGENT_WORKER_ENABLED", False)
    monkeypatch.setattr(settings, "SKILL_AGENT_INSECURE_MODE", True)
    import app.main as main_module

    if mock_db is None:
        mock_db = _default_health_mock_db()

    _mock_session_local(monkeypatch, mock_db)

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


def test_health_and_metrics_endpoints(monkeypatch, tmp_path):
    mock_db = AsyncMock()
    mapping_res = MagicMock()
    mapping_res.mappings.return_value.all.return_value = [{"status": "COMPLETED", "count": 5}]
    mock_version = MagicMock()
    mock_version.fetchall.return_value = [(DEFAULT_HEAD,)]

    async def _execute(sql, *args, **kwargs):
        sql_text = str(sql)
        if "alembic_version" in sql_text:
            return mock_version
        if "runs" in sql_text and "GROUP BY" in sql_text:
            return mapping_res
        return MagicMock()

    mock_db.execute = AsyncMock(side_effect=_execute)
    monkeypatch.setattr(settings, "SKILL_AGENT_ARTIFACT_DIR", str(tmp_path))

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
        assert ready_resp.json()["checks"]["credential_broker"] is True

        # Metrics
        m_resp = client.get("/metrics")
        assert m_resp.status_code == 200
        m_data = m_resp.json()
        assert "runs_by_status" in m_data
        assert m_data["runs_by_status"].get("COMPLETED") == 5


def test_ingest_run_completed_does_not_mark_run_completed(monkeypatch):
    monkeypatch.setattr(settings, "SKILL_AGENT_INTERNAL_TOKEN", "secret")
    from app.services import run_service

    dummy_run = RunView(
        run_id="r1",
        org_id="org-1",
        user_id="user-1",
        tool_name="demo",
        status="RUNNING",
        attempt_id="att-1",
        generation=1,
        snapshot={},
        result=None,
        created_at="2026-08-27T00:00:00Z",
        updated_at="2026-08-27T00:00:00Z",
    )
    mock_set_status = AsyncMock()
    mock_append_event = AsyncMock()
    monkeypatch.setattr(run_service, "get_run", AsyncMock(return_value=dummy_run))
    monkeypatch.setattr(run_service, "set_status", mock_set_status)
    monkeypatch.setattr(run_service, "append_event", mock_append_event)

    for client in _client(monkeypatch):
        resp = client.post(
            "/internal/v1/runs/r1/events/ingest",
            json={
                "org_id": "org-1",
                "events": [
                    {
                        "event_type": "run.completed",
                        "payload": {"result": "edge output"},
                        "source": "edge",
                        "source_event_id": "ev-1",
                    }
                ],
            },
            headers={
                "X-Skill-Agent-Token": "secret",
                "X-Exec-Org-Id": "org-1",
            },
        )
        assert resp.status_code == 200
        # Ingest only appends event evidence, does NOT write COMPLETED to status machine
        mock_append_event.assert_called_once()
        mock_set_status.assert_not_called()


def test_ingest_rejects_unknown_and_invalid_semantic_types(monkeypatch):
    monkeypatch.setattr(settings, "SKILL_AGENT_INTERNAL_TOKEN", "secret")
    from app.services import run_service

    dummy_run = RunView(
        run_id="r1",
        org_id="org-1",
        user_id="user-1",
        tool_name="demo",
        status="RUNNING",
        attempt_id="att-1",
        generation=1,
        snapshot={},
        result=None,
        created_at="2026-08-27T00:00:00Z",
        updated_at="2026-08-27T00:00:00Z",
    )
    rejections = []
    mock_append = AsyncMock()
    mock_update_step = AsyncMock()

    async def mock_reject(db, run_id, *, reason, event_id=None, source_event_id=None, details=None):
        rejections.append({"reason": reason, "details": details or {}})

    monkeypatch.setattr(run_service, "get_run", AsyncMock(return_value=dummy_run))
    monkeypatch.setattr(run_service, "append_event", mock_append)
    monkeypatch.setattr(run_service, "record_event_rejection", mock_reject)
    monkeypatch.setattr(run_service, "update_step_state", mock_update_step)
    monkeypatch.setattr(run_service, "list_artifacts", AsyncMock(return_value=[]))

    for client in _client(monkeypatch):
        rejections.clear()
        mock_append.reset_mock()
        mock_update_step.reset_mock()
        resp = client.post(
            "/internal/v1/runs/r1/events/ingest",
            json={
                "org_id": "org-1",
                "events": [
                    {"event_type": "foo.bar", "payload": {}, "source_event_id": "u1"},
                    {
                        "event_type": "tool.call",
                        "payload": {"tool_name": "t", "call_id": "c1", "status": "running"},
                        "source_event_id": "u2",
                    },
                    {
                        "event_type": "tool.call",
                        "payload": {
                            "tool_name": "t",
                            "call_id": "c1",
                            "status": "started",
                            "arguments": {"token": "secret"},
                        },
                        "source_event_id": "u3",
                    },
                    {
                        "event_type": "tool.call",
                        "payload": {
                            "tool_name": "t",
                            "call_id": "c2",
                            "status": "started",
                            "headers": {"Authorization": "Bearer secret"},
                        },
                        "source_event_id": "u3a",
                    },
                    {
                        "event_type": "artifact.persisted",
                        "payload": {
                            "artifact_id": "missing",
                            "name": "x",
                            "content_type": "text/plain",
                            "size": 1,
                            "checksum_sha256": "abc",
                        },
                        "source_event_id": "u4",
                    },
                    {
                        "event_type": "assistant.message",
                        "payload": {"text": "ok"},
                        "source_event_id": "u5",
                        "step_id": "central",
                    },
                    {
                        "event_type": "run.progress",
                        "payload": {"stage": "x"},
                        "source_event_id": "u6",
                    },
                    {
                        "event_type": "run.created",
                        "payload": {},
                        "source_event_id": "u7",
                    },
                ],
            },
            headers={
                "X-Skill-Agent-Token": "secret",
                "X-Exec-Org-Id": "org-1",
            },
        )
        assert resp.status_code == 200
        reasons = [r["reason"] for r in rejections]
        assert "unknown_event_type" in reasons
        assert "invalid_tool_call_status" in reasons
        assert "forbidden_semantic_payload_field" in reasons
        assert "unexpected_semantic_payload_field" in reasons
        assert "artifact_not_persisted" in reasons
        assert all("arguments" not in (r["details"] or {}) for r in rejections)
        assert all("token" not in str(r["details"]) for r in rejections)
        # assistant + run.progress + run.created accepted
        assert mock_append.await_count == 3
        mock_update_step.assert_not_called()


def test_ingest_artifact_persisted_requires_matching_persisted_descriptor(monkeypatch):
    monkeypatch.setattr(settings, "SKILL_AGENT_INTERNAL_TOKEN", "secret")
    from app.schemas import ArtifactDescriptor
    from app.services import run_service

    dummy_run = RunView(
        run_id="r1",
        org_id="org-1",
        user_id="user-1",
        tool_name="demo",
        status="RUNNING",
        attempt_id="att-1",
        generation=1,
        snapshot={},
        result=None,
        created_at="2026-08-27T00:00:00Z",
        updated_at="2026-08-27T00:00:00Z",
    )
    desc = ArtifactDescriptor(
        artifact_id="art-1",
        name="out.txt",
        content_type="text/plain",
        size_bytes=3,
        checksum_sha256="abc",
        storage_state="persisted",
    )
    mock_append = AsyncMock()
    mock_update_step = AsyncMock()
    rejections = []

    async def mock_reject(db, run_id, *, reason, event_id=None, source_event_id=None, details=None):
        rejections.append({"reason": reason, "details": details or {}})

    monkeypatch.setattr(run_service, "get_run", AsyncMock(return_value=dummy_run))
    monkeypatch.setattr(run_service, "append_event", mock_append)
    monkeypatch.setattr(run_service, "update_step_state", mock_update_step)
    monkeypatch.setattr(run_service, "list_artifacts", AsyncMock(return_value=[desc]))
    monkeypatch.setattr(run_service, "record_event_rejection", mock_reject)

    for client in _client(monkeypatch):
        resp = client.post(
            "/internal/v1/runs/r1/events/ingest",
            json={
                "events": [
                    {
                        "event_type": "artifact.persisted",
                        "payload": {
                            "artifact_id": "art-1",
                            "name": "out.txt",
                            "content_type": "text/plain",
                            "size": 3,
                            "checksum_sha256": "abc",
                        },
                        "source_event_id": "art-evt-1",
                        "step_id": "central",
                    }
                ],
            },
            headers={
                "X-Skill-Agent-Token": "secret",
                "X-Exec-Org-Id": "org-1",
            },
        )
        assert resp.status_code == 200
        mock_append.assert_called_once()
        mock_update_step.assert_not_called()

        mock_append.reset_mock()
        rejections.clear()
        mismatch = client.post(
            "/internal/v1/runs/r1/events/ingest",
            json={
                "events": [
                    {
                        "event_type": "artifact.persisted",
                        "payload": {
                            "artifact_id": "art-1",
                            "name": "forged.txt",
                            "content_type": "text/plain",
                            "size": 3,
                            "checksum_sha256": "abc",
                        },
                        "source_event_id": "art-evt-2",
                    }
                ],
            },
            headers={
                "X-Skill-Agent-Token": "secret",
                "X-Exec-Org-Id": "org-1",
            },
        )
        assert mismatch.status_code == 200
        mock_append.assert_not_called()
        assert [rejection["reason"] for rejection in rejections] == ["artifact_descriptor_mismatch"]

