"""Agent run_service fencing and approval helpers (unit, mocked DB)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas import CreateRunRequest
from app.services import run_service


@pytest.mark.asyncio
async def test_append_event_rejects_stale_attempt():
    db = AsyncMock()
    scalar = MagicMock()
    scalar.scalar_one_or_none.return_value = "attempt-current"
    db.execute = AsyncMock(return_value=scalar)

    with pytest.raises(RuntimeError, match="stale attempt"):
        await run_service.append_event(
            db,
            "run-1",
            "run.progress",
            {"x": 1},
            attempt_id="attempt-old",
        )


@pytest.mark.asyncio
async def test_append_event_source_dedup():
    db = AsyncMock()
    existing_row = {
        "id": "evt-existing",
        "run_id": "run-1",
        "attempt_id": "att-1",
        "event_type": "run.progress",
        "event_seq": 2,
        "source": "edge",
        "source_event_id": "src-evt-1",
        "payload": {"step": "1"},
        "created_at": None,
    }
    mapping_res = MagicMock()
    mapping_res.mappings.return_value.first.return_value = existing_row
    db.execute = AsyncMock(return_value=mapping_res)

    res = await run_service.append_event(
        db,
        "run-1",
        "run.progress",
        {"step": "1"},
        source="edge",
        source_event_id="src-evt-1",
    )
    assert res.event_id == "evt-existing"
    assert res.event_seq == 2
    assert res.source_event_id == "src-evt-1"


def test_build_snapshot_uses_release_fields():
    req = CreateRunRequest(
        run_id="run-1",
        tool_name="foo",
        skill_id="foo",
        skill_version="1.2.0",
        skill_release_id="rel-1",
        skill_release_digest="abc123",
        snapshot_hash="hash-1",
        route_snapshot={"gateway_url": "http://example.com"},
    )
    snap = run_service.build_snapshot(req, org_id="org", user_id="user")
    assert snap["skill_version"] == "1.2.0"
    assert snap["skill_release_id"] == "rel-1"
    assert snap["skill_release_digest"] == "abc123"
    assert snap["snapshot_hash"] == "hash-1"
    assert snap["runtime_policy"]["gateway_url"] == "http://example.com"


def test_build_snapshot_keeps_connector_refs():
    req = CreateRunRequest(
        run_id="run-2",
        tool_name="crm_lookup",
        connector_binding_refs=["binding-1"],
        knowledge_refs=["kb://doc-1"],
        placement={"role": "central", "engine": "connector"},
        route_snapshot={"route_type": "connector", "connector_kind": "rest"},
    )
    snap = run_service.build_snapshot(req, org_id="org", user_id="user")
    assert snap["connector_binding_refs"] == ["binding-1"]
    assert snap["knowledge_refs"] == ["kb://doc-1"]
    assert snap["placement"] == {"role": "central", "engine": "connector"}


@pytest.mark.asyncio
async def test_waiting_approval_create_status(monkeypatch):
    db = AsyncMock()
    mock_res = MagicMock()
    mock_res.mappings.return_value.first.return_value = None
    db.execute = AsyncMock(return_value=mock_res)
    monkeypatch.setattr(run_service, "append_event", AsyncMock())
    req = CreateRunRequest(run_id="run-1", tool_name="foo", requires_approval=True)
    result = await run_service.create_run(db, req, org_id="org", user_id="user")
    assert result.status == "WAITING_APPROVAL"


@pytest.mark.asyncio
async def test_set_status_rejects_stale_attempt():
    db = AsyncMock()
    scalar = MagicMock()
    scalar.scalar_one_or_none.return_value = "attempt-current"
    db.execute = AsyncMock(return_value=scalar)

    with pytest.raises(RuntimeError, match="stale attempt"):
        await run_service.set_status(
            db,
            "run-1",
            "COMPLETED",
            attempt_id="attempt-old",
        )


@pytest.mark.asyncio
async def test_approve_run_records_approval_idempotently(monkeypatch):
    db = AsyncMock()
    waiting_view = run_service.RunView(
        run_id="run-wait",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status="WAITING_APPROVAL",
        snapshot={},
        attempt_id=None,
        generation=0,
        created_at="2026-08-27T00:00:00Z",
        updated_at="2026-08-27T00:00:00Z",
    )
    resumed_view = run_service.RunView(
        run_id="run-wait",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status="QUEUED",
        snapshot={},
        attempt_id=None,
        generation=0,
        created_at="2026-08-27T00:00:00Z",
        updated_at="2026-08-27T00:00:00Z",
    )
    get_run_mock = AsyncMock(side_effect=[waiting_view, resumed_view])
    monkeypatch.setattr(run_service, "get_run", get_run_mock)
    monkeypatch.setattr(run_service, "set_status", AsyncMock(return_value=True))
    monkeypatch.setattr(run_service, "append_event", AsyncMock())

    res = await run_service.approve_run(db, "run-wait", org_id="org-1", approval_id="appr-123", evidence={"actor": "admin"})
    assert res.status == "QUEUED"
    assert db.execute.called


@pytest.mark.asyncio
async def test_cancel_run_three_phase_transitions(monkeypatch):
    db = AsyncMock()
    # 1. In-flight run -> transitions to CANCELLING
    running_view = run_service.RunView(
        run_id="run-running",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status="RUNNING",
        snapshot={},
        attempt_id="att-1",
        generation=1,
        created_at="2026-08-27T00:00:00Z",
        updated_at="2026-08-27T00:00:00Z",
    )
    cancelling_view = run_service.RunView(
        run_id="run-running",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status="CANCELLING",
        snapshot={},
        attempt_id="att-1",
        generation=1,
        created_at="2026-08-27T00:00:00Z",
        updated_at="2026-08-27T00:00:00Z",
    )

    get_run_mock = AsyncMock(side_effect=[running_view, cancelling_view])
    monkeypatch.setattr(run_service, "get_run", get_run_mock)
    monkeypatch.setattr(run_service, "set_status", AsyncMock(return_value=True))
    monkeypatch.setattr(run_service, "append_event", AsyncMock())

    res = await run_service.cancel_run(db, "run-running", org_id="org-1")
    assert res.status == "CANCELLING"

    # 2. Queued run -> transitions directly to CANCELLED
    queued_view = run_service.RunView(
        run_id="run-queued",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status="QUEUED",
        snapshot={},
        attempt_id=None,
        generation=0,
        created_at="2026-08-27T00:00:00Z",
        updated_at="2026-08-27T00:00:00Z",
    )
    cancelled_view = run_service.RunView(
        run_id="run-queued",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status="CANCELLED",
        snapshot={},
        attempt_id=None,
        generation=0,
        created_at="2026-08-27T00:00:00Z",
        updated_at="2026-08-27T00:00:00Z",
    )
    get_run_mock2 = AsyncMock(side_effect=[queued_view, cancelled_view])
    monkeypatch.setattr(run_service, "get_run", get_run_mock2)
    res2 = await run_service.cancel_run(db, "run-queued", org_id="org-1")
    assert res2.status == "CANCELLED"


@pytest.mark.asyncio
async def test_get_artifact_bytes_returns_content():
    db = AsyncMock()
    mapping_res = MagicMock()
    first_mock = MagicMock()
    first_mock.return_value = {
        "id": "art-1",
        "name": "report.pdf",
        "content_type": "application/pdf",
        "checksum_sha256": "fakehash",
        "size_bytes": 10,
        "storage_ref": "data:base64:aGVsbG8gd29ybGQ=",
    }
    mapping_res.mappings.return_value.first = first_mock
    exec_mock = AsyncMock(return_value=mapping_res)
    db.execute = exec_mock

    packed = await run_service.get_artifact_bytes(db, "run-1", "art-1")
    assert packed is not None
    meta, content = packed
    assert meta["name"] == "report.pdf"
    assert content == b"hello world"
