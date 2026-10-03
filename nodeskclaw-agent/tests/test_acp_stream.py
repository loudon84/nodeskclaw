from types import SimpleNamespace

from app.acp_gateway.event_mapping import map_event, strip_runtime_secrets
from app.acp_gateway.errors import AcpGatewayError
from app.acp_gateway.permission import apply_permission
from unittest.mock import AsyncMock

import pytest


def test_runtime_run_id_stripped_from_updates():
    cleaned = strip_runtime_secrets({"runtime_run_id": "secret", "text": "ok"})
    assert "runtime_run_id" not in cleaned
    assert cleaned["text"] == "ok"


def test_artifact_maps_to_public_path():
    event = SimpleNamespace(
        event_type="artifact.persisted",
        payload={"artifact_id": "art-1", "name": "out.txt"},
        run_id="run-1",
        event_seq=3,
    )
    updates, stop, perm = map_event(event, agent_ref="sales-expert")
    assert stop is None
    assert perm is None
    uri = updates[0]["content"]["downloadPath"]
    assert uri.startswith("/api/v1/remote-experts/sales-expert/acp/runs/run-1/artifacts/")
    assert "127.0.0.1" not in uri


def test_failed_run_maps_to_remote_failed():
    event = SimpleNamespace(event_type="run.failed", payload={}, run_id="run-1", event_seq=9)
    _updates, stop, _perm = map_event(event, agent_ref="sales-expert")
    assert stop == "ACP_REMOTE_RUN_FAILED"


@pytest.mark.asyncio
async def test_stale_attempt_permission_rejected(monkeypatch):
    run = SimpleNamespace(attempt_id="att-2", generation=4)
    db = AsyncMock()
    from app.services import run_service

    async def fake_get(*args, **kwargs):
        return run

    monkeypatch.setattr(run_service, "get_run", fake_get)
    try:
        await apply_permission(
            db,
            run_id="run-1",
            org_id="org",
            approval_id="appr-1",
            outcome={"optionId": "allow_once"},
            expected_attempt_id="att-1",
            expected_generation=4,
        )
        assert False
    except AcpGatewayError as exc:
        assert exc.error_code == "ACP_STALE_ATTEMPT"
