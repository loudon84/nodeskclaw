"""Agent run_service fencing and approval helpers (unit, mocked DB)."""

from __future__ import annotations

import hashlib
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas import (
    CreateRunRequest,
    validate_semantic_event_payload,
)
from app.services import run_service


def test_validate_semantic_event_payload_shapes():
    assert validate_semantic_event_payload("assistant.message", {"text": "hi"}) is None
    assert validate_semantic_event_payload("assistant.message", {}) == "missing_assistant_text"
    assert (
        validate_semantic_event_payload(
            "tool.call",
            {"tool_name": "t", "call_id": "c1", "status": "started"},
        )
        is None
    )
    assert (
        validate_semantic_event_payload(
            "tool.call",
            {"tool_name": "t", "call_id": "c1", "status": "running"},
        )
        == "invalid_tool_call_status"
    )
    assert (
        validate_semantic_event_payload(
            "artifact.persisted",
            {
                "artifact_id": "a1",
                "name": "out.txt",
                "content_type": "text/plain",
                "size": 3,
                "checksum_sha256": "abc",
                "storage_key": "secret",
            },
        )
        == "forbidden_semantic_payload_field"
    )
    assert validate_semantic_event_payload("unknown.type", {"text": "x"}) == "unknown_semantic_type"


@pytest.mark.asyncio
async def test_append_event_rejects_stale_attempt():
    db = AsyncMock()
    mock_res = MagicMock()
    mock_res.mappings.return_value.first.return_value = None
    db.execute = AsyncMock(return_value=mock_res)

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


@pytest.mark.asyncio
async def test_append_event_source_idempotency_conflict_raises():
    db = AsyncMock()
    existing_row = {
        "id": "evt-existing",
        "run_id": "run-1",
        "attempt_id": "att-1",
        "event_type": "run.progress",
        "event_seq": 2,
        "source": "edge",
        "source_event_id": "src-evt-1",
        "payload": {"step": "1", "data": "old"},
        "created_at": None,
    }
    mapping_res = MagicMock()
    mapping_res.mappings.return_value.first.return_value = existing_row
    db.execute = AsyncMock(return_value=mapping_res)

    with pytest.raises(RuntimeError, match="idempotency conflict"):
        await run_service.append_event(
            db,
            "run-1",
            "run.progress",
            {"step": "1", "data": "different"},
            source="edge",
            source_event_id="src-evt-1",
        )



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
    mock_res = MagicMock()
    mock_res.rowcount = 0
    db.execute = AsyncMock(return_value=mock_res)

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
async def test_add_artifact_rejects_stale_attempt():
    db = AsyncMock()
    mock_res = MagicMock()
    mock_res.mappings.return_value.first.return_value = None
    db.execute = AsyncMock(return_value=mock_res)

    with pytest.raises(RuntimeError, match="stale attempt"):
        await run_service.add_artifact(
            db,
            "run-1",
            name="test.txt",
            attempt_id="attempt-old",
        )


@pytest.mark.asyncio
async def test_store_and_get_artifact_bytes_local_file(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.run_service.settings.SKILL_AGENT_ARTIFACT_DIR", str(tmp_path))
    db = AsyncMock()
    mock_seq = MagicMock()
    mock_seq.mappings.return_value.first.return_value = {"next_event_seq": 1}
    db.execute = AsyncMock(return_value=mock_seq)

    # Store
    with patch("app.services.run_service.append_event", new=AsyncMock()):
        desc = await run_service.store_artifact_bytes(
            db,
            "run-1",
            name="output.json",
            content=b'{"result": "success"}',
            content_type="application/json",
            attempt_id="att-1",
        )
    assert desc.name == "output.json"
    assert desc.size_bytes == 21
    assert desc.checksum_sha256 is not None

    # Get from file
    file_path = tmp_path / "run-1" / f"{desc.artifact_id}_output.json"
    assert file_path.exists()
    assert file_path.read_bytes() == b'{"result": "success"}'

    mapping_res = MagicMock()
    mapping_res.mappings.return_value.first.return_value = {
        "id": desc.artifact_id,
        "name": "output.json",
        "content_type": "application/json",
        "size_bytes": 21,
        "storage_ref": str(file_path),
        "checksum_sha256": desc.checksum_sha256,
    }
    db.execute = AsyncMock(return_value=mapping_res)

    packed = await run_service.get_artifact_bytes(db, "run-1", desc.artifact_id)
    assert packed is not None
    meta, raw = packed
    assert meta["name"] == "output.json"
    assert raw == b'{"result": "success"}'



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


@pytest.mark.asyncio
async def test_resume_run_rejects_waiting_approval(monkeypatch):
    db = AsyncMock()
    waiting_view = run_service.RunView(
        run_id="run-waiting",
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
    get_run_mock = AsyncMock(return_value=waiting_view)
    monkeypatch.setattr(run_service, "get_run", get_run_mock)

    with pytest.raises(ValueError, match="requires approval"):
        await run_service.resume_run(db, "run-waiting", org_id="org-1")


@pytest.mark.asyncio
async def test_resume_run_transitions_paused(monkeypatch):
    db = AsyncMock()
    paused_view = run_service.RunView(
        run_id="run-paused",
        org_id="org-1",
        user_id="user-1",
        tool_name="test_tool",
        status="PAUSED",
        snapshot={},
        attempt_id=None,
        generation=0,
        created_at="2026-08-27T00:00:00Z",
        updated_at="2026-08-27T00:00:00Z",
    )
    queued_view = run_service.RunView(
        run_id="run-paused",
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
    get_run_mock = AsyncMock(side_effect=[paused_view, queued_view])
    monkeypatch.setattr(run_service, "get_run", get_run_mock)
    monkeypatch.setattr(run_service, "set_status", AsyncMock(return_value=True))
    monkeypatch.setattr(run_service, "append_event", AsyncMock())

    res = await run_service.resume_run(db, "run-paused", org_id="org-1", evidence={"reason": "test"})
    assert res is not None
    assert res.status == "QUEUED"


def test_build_hybrid_step_plan_deterministic():
    from app.services.worker import build_hybrid_step_plan

    # 1. Central
    plan1 = build_hybrid_step_plan({"placement": {"role": "central", "engine": "hermes"}})
    assert len(plan1) == 1
    assert plan1[0]["role"] == "central"
    assert plan1[0]["engine"] == "hermes"

    # 2. Edge only
    plan2 = build_hybrid_step_plan({"placement": {"role": "edge", "engine": "connector"}})
    assert len(plan2) == 1
    assert plan2[0]["role"] == "edge"
    assert plan2[0]["engine"] == "connector"

    # 3. Hybrid
    snapshot_hybrid = {
        "placement": {"role": "hybrid", "engine": "hybrid"},
        "runtime_policy": {
            "connector_bindings": [
                {"id": "b1", "placement": "edge"},
                {"id": "b2", "placement": "central"},
            ]
        },
    }
    plan3 = build_hybrid_step_plan(snapshot_hybrid)
    assert len(plan3) == 2
    assert plan3[0]["step"] == "central_hermes"
    assert plan3[1]["step"] == "edge_connector_b1"
    assert plan3[1]["role"] == "edge"


@pytest.mark.asyncio
async def test_mutation_gate_generation_fencing():
    db = AsyncMock()
    mock_res = MagicMock()
    mock_res.rowcount = 0
    db.execute = AsyncMock(return_value=mock_res)

    with pytest.raises(RuntimeError, match="stale attempt"):
        await run_service.set_status(
            db,
            "run-1",
            "COMPLETED",
            org_id="org-1",
            attempt_id="att-1",
            generation=1,
        )

    mock_seq = MagicMock()
    mock_seq.mappings.return_value.first.return_value = None
    db.execute = AsyncMock(return_value=mock_seq)

    with pytest.raises(RuntimeError, match="stale attempt, invalid generation, or terminal run"):
        await run_service.append_event(
            db,
            "run-1",
            "run.progress",
            {"step": 1},
            org_id="org-1",
            attempt_id="att-1",
            generation=1,
        )


@pytest.mark.asyncio
async def test_terminal_status_cannot_be_overwritten():
    db = AsyncMock()
    mock_res = MagicMock()
    mock_res.rowcount = 0
    db.execute = AsyncMock(return_value=mock_res)

    # When expected_status or terminal CAS fails to match, returns False if no attempt_id
    success = await run_service.set_status(
        db,
        "run-1",
        "COMPLETED",
        org_id="org-1",
    )
    assert success is False


@pytest.mark.asyncio
async def test_create_run_session_cross_org_rejected():
    db = AsyncMock()
    mock_res = MagicMock()
    mock_res.mappings.return_value.first.return_value = {
        "id": "sess-1",
        "org_id": "org-other",
        "user_id": "user-other",
        "context_version": 0,
        "deleted_at": None,
        "expires_at": None,
    }
    db.execute = AsyncMock(return_value=mock_res)

    req = CreateRunRequest(
        run_id="run-1",
        tool_name="test_tool",
        run_session_id="sess-1",
    )
    with pytest.raises(ValueError, match="cross-org run session access rejected"):
        await run_service.create_run(db, req, org_id="org-1", user_id="user-1")


@pytest.mark.asyncio
async def test_create_run_session_subject_mismatch_rejected():
    db = AsyncMock()
    mock_res = MagicMock()
    mock_res.mappings.return_value.first.return_value = {
        "id": "sess-1",
        "org_id": "org-1",
        "user_id": "user-other",
        "context_version": 0,
        "deleted_at": None,
        "expires_at": None,
    }
    db.execute = AsyncMock(return_value=mock_res)

    req = CreateRunRequest(run_id="run-1", tool_name="test_tool", run_session_id="sess-1")
    with pytest.raises(ValueError, match="run session subject mismatch rejected"):
        await run_service.create_run(db, req, org_id="org-1", user_id="user-1")


@pytest.mark.asyncio
async def test_create_run_session_soft_deleted_rejected():
    from datetime import datetime, timezone

    db = AsyncMock()
    mock_res = MagicMock()
    mock_res.mappings.return_value.first.return_value = {
        "id": "sess-1",
        "org_id": "org-1",
        "user_id": "user-1",
        "context_version": 1,
        "deleted_at": datetime.now(timezone.utc),
        "expires_at": None,
    }
    db.execute = AsyncMock(return_value=mock_res)

    req = CreateRunRequest(run_id="run-1", tool_name="test_tool", run_session_id="sess-1")
    with pytest.raises(ValueError, match="run session unrecoverable: soft deleted"):
        await run_service.create_run(db, req, org_id="org-1", user_id="user-1")


@pytest.mark.asyncio
async def test_ensure_run_session_allocates_monotonic_context_version():
    db = AsyncMock()
    select_result = MagicMock()
    select_result.mappings.return_value.first.return_value = {
        "id": "sess-1",
        "org_id": "org-1",
        "user_id": "user-1",
        "context_version": 7,
        "deleted_at": None,
        "expires_at": None,
    }
    db.execute = AsyncMock(side_effect=[select_result, MagicMock()])

    version = await run_service._ensure_run_session(
        db,
        run_session_id="sess-1",
        org_id="org-1",
        user_id="user-1",
        context_version=3,
    )

    assert version == 8
    assert db.execute.await_args_list[1].args[1]["context_version"] == 8


@pytest.mark.asyncio
async def test_revalidate_run_session_rejects_context_version_mismatch():
    db = AsyncMock()
    select_result = MagicMock()
    select_result.mappings.return_value.first.return_value = {
        "id": "sess-1",
        "org_id": "org-1",
        "user_id": "user-1",
        "context_version": 8,
        "deleted_at": None,
        "expires_at": None,
    }
    db.execute = AsyncMock(return_value=select_result)

    with pytest.raises(ValueError, match="run session context version mismatch"):
        await run_service.revalidate_run_session(
            db,
            run_session_id="sess-1",
            org_id="org-1",
            user_id="user-1",
            context_version=7,
        )


@pytest.mark.asyncio
async def test_create_run_binds_snapshot_context_version_to_session_version():
    db = AsyncMock()
    missing = MagicMock()
    missing.mappings.return_value.first.return_value = None
    session = MagicMock()
    session.mappings.return_value.first.return_value = {
        "id": "sess-1",
        "org_id": "org-1",
        "user_id": "user-1",
        "context_version": 7,
        "deleted_at": None,
        "expires_at": None,
    }
    db.execute = AsyncMock(side_effect=[missing, missing, session, MagicMock(), MagicMock()])
    request = CreateRunRequest(
        run_id="run-1",
        tool_name="test_tool",
        run_session_id="sess-1",
        context_version=999,
        execution_context={"context_version": 999, "descriptors": []},
    )

    with patch("app.services.run_service.append_event", new=AsyncMock()):
        await run_service.create_run(db, request, org_id="org-1", user_id="user-1")

    inserted_snapshot = json.loads(db.execute.await_args_list[4].args[1]["snapshot"])
    assert inserted_snapshot["context_version"] == 8
    assert inserted_snapshot["execution_context"]["context_version"] == 8


def test_build_snapshot_persists_execution_context_and_version():
    req = CreateRunRequest(
        run_id="run-1",
        tool_name="test_tool",
        execution_context={
            "context_version": 2,
            "descriptors": [
                {"type": "knowledge", "stable_id": "ks-1", "auth_version": "v1"},
            ],
        },
        context_version=2,
    )
    snap = run_service.build_snapshot(req, org_id="org-1", user_id="user-1")
    assert snap["context_version"] == 2
    assert snap["execution_context"]["descriptors"][0]["stable_id"] == "ks-1"


def test_build_snapshot_sanitizes_sensitive_tokens():
    req = CreateRunRequest(
        run_id="run-1",
        tool_name="test_tool",
        client_context={"auth_token": "secret-token-123", "user_email": "a@b.com"},
        route_snapshot={"api_key": "secret-key-456", "gateway_url": "https://api.example.com"},
    )
    snap = run_service.build_snapshot(req, org_id="org-1", user_id="user-1")
    assert snap["client_context"]["auth_token"] == "[REDACTED]"
    assert snap["client_context"]["user_email"] == "a@b.com"
    assert snap["runtime_policy"]["api_key"] == "[REDACTED]"
    assert snap["runtime_policy"]["gateway_url"] == "https://api.example.com"


def test_build_snapshot_preserves_opaque_connector_secret_ref_id():
    req = CreateRunRequest(
        run_id="run-1",
        tool_name="test_tool",
        route_snapshot={
            "connector_secret_ref_id": "secret-ref-1",
            "authorization": "plaintext-token",
        },
    )

    snap = run_service.build_snapshot(req, org_id="org-1", user_id="user-1")

    assert snap["runtime_policy"]["connector_secret_ref_id"] == "secret-ref-1"
    assert snap["runtime_policy"]["authorization"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_approve_run_requires_approval_id():
    db = AsyncMock()
    mock_run = MagicMock(status="WAITING_APPROVAL")
    mock_res = MagicMock()
    mock_res.mappings.return_value.first.return_value = {
        "id": "run-1",
        "org_id": "org-1",
        "user_id": "user-1",
        "tool_name": "tool",
        "status": "WAITING_APPROVAL",
        "snapshot": {},
        "result": None,
        "attempt_id": None,
        "generation": 0,
        "created_at": None,
        "updated_at": None,
    }
    db.execute = AsyncMock(return_value=mock_res)

    with pytest.raises(ValueError, match="approval_id is required"):
        await run_service.approve_run(db, "run-1", org_id="org-1", approval_id=None)


@pytest.mark.asyncio
async def test_store_artifact_bytes_rejects_tmp_in_prod(monkeypatch, tmp_path):
    from app.config import settings

    monkeypatch.setattr(settings, "SKILL_AGENT_INSECURE_MODE", False)
    monkeypatch.setattr(settings, "SKILL_AGENT_ARTIFACT_DIR", "/tmp/artifacts")

    db = AsyncMock()
    with pytest.raises(RuntimeError, match="Artifact directory must not be in ephemeral storage in production"):
        await run_service.store_artifact_bytes(
            db,
            "run-1",
            name="out.txt",
            content=b"hello",
        )


@pytest.mark.asyncio
async def test_store_artifact_bytes_and_read_across_restarts(monkeypatch, tmp_path):
    from app.config import settings

    target_dir = str(tmp_path / "persistent_artifacts")
    monkeypatch.setattr(settings, "SKILL_AGENT_INSECURE_MODE", True)
    monkeypatch.setattr(settings, "SKILL_AGENT_ARTIFACT_DIR", target_dir)

    db = AsyncMock()
    mock_seq = MagicMock()
    mock_seq.mappings.return_value.first.return_value = {"next_event_seq": 1}
    db.execute = AsyncMock(return_value=mock_seq)

    with patch("app.services.run_service.append_event", new=AsyncMock()):
        desc = await run_service.store_artifact_bytes(
            db,
            "run-1",
            name="test_artifact.json",
            content=b'{"result": 42}',
            content_type="application/json",
        )
    assert desc.size_bytes == len(b'{"result": 42}')
    assert desc.checksum_sha256 is not None

    # Simulate get_artifact_bytes by mocking the DB query returning storage_ref
    stored_path = str(tmp_path / "persistent_artifacts" / "run-1" / f"{desc.artifact_id}_test_artifact.json")
    mock_row = {
        "id": desc.artifact_id,
        "name": "test_artifact.json",
        "content_type": "application/json",
        "size_bytes": desc.size_bytes,
        "storage_ref": stored_path,
        "checksum_sha256": desc.checksum_sha256,
    }
    mock_res = MagicMock()
    mock_res.mappings.return_value.first.return_value = mock_row
    db.execute = AsyncMock(return_value=mock_res)

    meta, content = await run_service.get_artifact_bytes(db, "run-1", desc.artifact_id)
    assert content == b'{"result": 42}'
    assert meta["id"] == desc.artifact_id


@pytest.mark.asyncio
async def test_store_artifact_bytes_idempotency_and_conflict(monkeypatch, tmp_path):
    from app.config import settings

    target_dir = str(tmp_path / "persistent_artifacts")
    monkeypatch.setattr(settings, "SKILL_AGENT_INSECURE_MODE", True)
    monkeypatch.setattr(settings, "SKILL_AGENT_ARTIFACT_DIR", target_dir)

    db = AsyncMock()

    # 1. Existing artifact with same checksum -> idempotent return
    existing_row = {
        "id": "art-100",
        "name": "data.txt",
        "content_type": "text/plain",
        "size_bytes": 5,
        "storage_ref": "/some/path",
        "checksum_sha256": "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",  # sha256 of b"hello"
    }
    mock_res = MagicMock()
    mock_res.mappings.return_value.first.return_value = existing_row
    db.execute = AsyncMock(return_value=mock_res)

    desc1 = await run_service.store_artifact_bytes(
        db,
        "run-1",
        name="data.txt",
        content=b"hello",
    )
    assert desc1.artifact_id == "art-100"
    assert desc1.storage_state == "persisted"

    # 2. Existing artifact with DIFFERENT checksum -> conflict error
    with pytest.raises(RuntimeError, match="Artifact conflict"):
        await run_service.store_artifact_bytes(
            db,
            "run-1",
            name="data.txt",
            content=b"different content",
        )


@pytest.mark.asyncio
async def test_append_event_and_list_events_include_request_trace_id():
    db = AsyncMock()

    mock_snap = MagicMock()
    mock_snap.mappings.return_value.first.return_value = {"snapshot": {"request_trace_id": "trace-abc-123"}}

    mock_seq = MagicMock()
    mock_seq.mappings.return_value.first.return_value = {"next_event_seq": 1}

    db.execute = AsyncMock(side_effect=[mock_snap, mock_seq, None])

    evt = await run_service.append_event(
        db,
        "run-1",
        "custom.step",
        {"val": 1},
    )
    assert evt.request_trace_id == "trace-abc-123"

    # Test list_events
    rows = [{
        "id": "evt-1",
        "run_id": "run-1",
        "attempt_id": None,
        "event_type": "custom.step",
        "event_seq": 1,
        "source": "agent",
        "source_event_id": None,
        "payload": {"val": 1},
        "created_at": None,
    }]
    mock_list_snap = MagicMock()
    mock_list_snap.mappings.return_value.first.return_value = {"snapshot": {"request_trace_id": "trace-abc-123"}}

    mock_list_events = MagicMock()
    mock_list_events.mappings.return_value.all.return_value = rows

    db.execute = AsyncMock(side_effect=[mock_list_snap, mock_list_events])
    listed = await run_service.list_events(db, "run-1")
    assert len(listed) == 1
    assert listed[0].request_trace_id == "trace-abc-123"


@pytest.mark.asyncio
async def test_aggregate_run_terminal_single_winner():
    db = AsyncMock()

    # 1. Test when required step fails -> run transitions to FAILED
    dummy_run_running = MagicMock(status="RUNNING", run_id="r1", org_id="org-1")
    dummy_run_failed = MagicMock(status="FAILED", run_id="r1", org_id="org-1")
    steps_with_failure = [
        {"step_id": "s1", "required": True, "status": "FAILED", "error_message": "failed step 1"},
        {"step_id": "s2", "required": True, "status": "PENDING"},
    ]

    mock_steps_res = MagicMock()
    mock_steps_res.mappings.return_value.all.return_value = steps_with_failure

    with patch("app.services.run_service.get_run", side_effect=[dummy_run_running, dummy_run_failed]), \
         patch("app.services.run_service.set_status", return_value=True) as mock_set_st, \
         patch("app.services.run_service.append_event", return_value=MagicMock()):
        db.execute = AsyncMock(return_value=mock_steps_res)
        res = await run_service.aggregate_run_terminal(db, "r1", org_id="org-1")
        assert res.status == "FAILED"
        assert mock_set_st.call_count == 1
        assert mock_set_st.call_args[0][2] == "FAILED"

    # 2. Test when required artifact is missing -> COMPLETED blocked
    dummy_run_waiting = MagicMock(status="WAITING_EDGE", run_id="r2", org_id="org-1")
    steps_succeeded_with_artifact = [
        {"step_id": "s1", "required": True, "status": "SUCCEEDED", "required_artifacts": ["output.csv"], "result": {"data": "done"}},
    ]
    mock_steps_succ = MagicMock()
    mock_steps_succ.mappings.return_value.all.return_value = steps_succeeded_with_artifact

    with patch("app.services.run_service.get_run", return_value=dummy_run_waiting), \
         patch("app.services.run_service.list_artifacts", return_value=[]), \
         patch("app.services.run_service.set_status") as mock_set_st:
        db.execute = AsyncMock(return_value=mock_steps_succ)
        res = await run_service.aggregate_run_terminal(db, "r2", org_id="org-1")
        # Run remains in WAITING_EDGE because output.csv is missing
        assert res.status == "WAITING_EDGE"
        mock_set_st.assert_not_called()

    # 3. Test when required steps all succeeded and artifact verified -> transitions to COMPLETED
    artifact_desc = MagicMock(name="output.csv", checksum_sha256="sha256-123", storage_state="persisted")
    artifact_desc.name = "output.csv"
    dummy_run_completed = MagicMock(status="COMPLETED", run_id="r2", org_id="org-1")

    with patch("app.services.run_service.get_run", side_effect=[dummy_run_waiting, dummy_run_completed]), \
         patch("app.services.run_service.list_artifacts", return_value=[artifact_desc]), \
         patch("app.services.run_service.set_status", return_value=True) as mock_set_st, \
         patch("app.services.run_service.append_event", return_value=MagicMock()), \
         patch("app.services.run_service.store_artifact_bytes", return_value=MagicMock()):
        db.execute = AsyncMock(return_value=mock_steps_succ)
        res = await run_service.aggregate_run_terminal(db, "r2", org_id="org-1")
        assert res.status == "COMPLETED"
        assert mock_set_st.call_count == 1
        assert mock_set_st.call_args[0][2] == "COMPLETED"


@pytest.mark.asyncio
# @lat: [[architecture/skill-agent#Configuration#Gateway Reachability Probe]]
async def test_aggregate_keeps_failed_status_when_terminal_event_write_rejected():
    db = AsyncMock()
    dummy_run_running = MagicMock(status="RUNNING", run_id="r-fail", org_id="org-1")
    dummy_run_failed = MagicMock(status="FAILED", run_id="r-fail", org_id="org-1")
    steps_with_failure = [
        {"step_id": "s1", "required": True, "status": "FAILED", "error_message": "gateway unreachable"},
    ]
    mock_steps_res = MagicMock()
    mock_steps_res.mappings.return_value.all.return_value = steps_with_failure

    with patch("app.services.run_service.get_run", side_effect=[dummy_run_running, dummy_run_failed]), \
         patch("app.services.run_service.set_status", new=AsyncMock(return_value=True)) as mock_set_st, \
         patch(
             "app.services.run_service.append_event",
             new=AsyncMock(side_effect=RuntimeError("stale attempt, invalid generation, or terminal run cannot write events")),
         ):
        db.execute = AsyncMock(return_value=mock_steps_res)
        res = await run_service.aggregate_run_terminal(db, "r-fail", org_id="org-1")

    assert res.status == "FAILED"
    assert mock_set_st.await_count == 1
    assert mock_set_st.await_args.args[2] == "FAILED"


@pytest.mark.asyncio
async def test_ingest_rejection_is_audited():
    db = AsyncMock()
    db.execute = AsyncMock(return_value=MagicMock())

    await run_service.record_event_rejection(
        db,
        "run-1",
        reason="old_attempt",
        event_id="ev-1",
        source_event_id="src-1",
        details={"attempt_id": "att-old"},
    )
    assert db.execute.call_count == 1


@pytest.mark.asyncio
async def test_artifact_lifecycle_state_machine(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.run_service.settings.SKILL_AGENT_ARTIFACT_DIR", str(tmp_path))
    db = AsyncMock()
    mock_seq = MagicMock()
    mock_seq.mappings.return_value.first.return_value = {"next_event_seq": 1}
    db.execute = AsyncMock(return_value=mock_seq)

    # 1. Store transitions from INIT to PERSISTED
    with patch("app.services.run_service.append_event", new=AsyncMock()) as mock_append:
        desc = await run_service.store_artifact_bytes(
            db,
            "run-10",
            name="test_artifact.txt",
            content=b"hello-artifact",
            content_type="text/plain",
            attempt_id="att-1",
        )
        assert desc.name == "test_artifact.txt"
        assert desc.storage_state == "persisted"
        assert desc.size_bytes == 14
        persisted_calls = [
            call
            for call in mock_append.await_args_list
            if call.args[2] == "artifact.persisted"
        ]
        assert len(persisted_calls) == 1
        payload = persisted_calls[0].args[3]
        assert payload["artifact_id"] == desc.artifact_id
        assert payload["name"] == "test_artifact.txt"
        assert payload["size"] == 14
        assert "checksum_sha256" in payload
        assert "storage_key" not in payload
        assert persisted_calls[0].kwargs["source_event_id"] == f"artifact:{desc.artifact_id}:persisted"

    # 2. Mark corrupted
    ok_corrupt = await run_service.mark_artifact_corrupted(db, desc.artifact_id, reason="disk read error")
    assert ok_corrupt is True

    # 3. Mark expired
    ok_expire = await run_service.mark_artifact_expired(db, desc.artifact_id, reason="ttl exceeded")
    assert ok_expire is True


@pytest.mark.asyncio
async def test_storage_port_sha256_and_size_integrity(tmp_path):
    from app.services.storage_port import LocalStorageDriver, S3StorageDriver, StorageIntegrityError

    local_driver = LocalStorageDriver(base_dir=str(tmp_path))
    content = b"sample-binary-payload"
    correct_sha256 = hashlib.sha256(content).hexdigest()

    # 1. Write with matching sha256 and size succeeds
    res = await local_driver.write("r1/a1.bin", content, expected_sha256=correct_sha256, expected_size=len(content))
    assert res["size_bytes"] == len(content)
    assert res["sha256"] == correct_sha256

    # 2. Write with mismatching sha256 raises StorageIntegrityError
    with pytest.raises(StorageIntegrityError, match="sha256 mismatch"):
        await local_driver.write("r1/a2.bin", content, expected_sha256="bad-sha256")

    # 3. Write with mismatching size raises StorageIntegrityError
    with pytest.raises(StorageIntegrityError, match="size mismatch"):
        await local_driver.write("r1/a3.bin", content, expected_size=999)

    # 4. S3 driver integrity check uses isolated client operations
    from unittest.mock import AsyncMock

    s3_driver = S3StorageDriver(
        endpoint="http://127.0.0.1:9000",
        bucket="test-bucket",
        access_key="test-key",
        secret_key="test-secret",
        region="us-east-1",
    )
    s3_driver._client.put_object = AsyncMock()
    s3_driver._client.get_object = AsyncMock(return_value=content)
    s3_driver._client.head_object = AsyncMock(return_value={"size_bytes": len(content), "sha256": correct_sha256})
    s3_res = await s3_driver.write("r1/s3_a1.bin", content, expected_sha256=correct_sha256, expected_size=len(content))
    assert s3_res["storage_ref"] == "s3://test-bucket/r1/s3_a1.bin"
    read_back = await s3_driver.read("r1/s3_a1.bin")
    assert read_back == content


@pytest.mark.asyncio
async def test_artifact_idempotency_key_behavior(tmp_path, monkeypatch):
    monkeypatch.setattr("app.services.run_service.settings.SKILL_AGENT_ARTIFACT_DIR", str(tmp_path))
    db = AsyncMock()
    mock_seq = MagicMock()
    mock_seq.mappings.return_value.first.return_value = {"next_event_seq": 1}
    db.execute = AsyncMock(return_value=mock_seq)

    # 1. First upload with idempotency_key
    with patch("app.services.run_service.append_event", new=AsyncMock()):
        desc1 = await run_service.store_artifact_bytes(
            db,
            "run-idem-1",
            name="output.txt",
            content=b"content-v1",
            content_type="text/plain",
            idempotency_key="key-123",
            step_id="step-1",
        )
    assert desc1.name == "output.txt"
    assert desc1.storage_state == "persisted"

    # 2. Simulate DB returning existing record for same idempotency_key with same checksum
    existing_row = {
        "id": desc1.artifact_id,
        "name": "output.txt",
        "content_type": "text/plain",
        "size_bytes": len(b"content-v1"),
        "storage_ref": f"run-idem-1/{desc1.artifact_id}_output.txt",
        "checksum_sha256": hashlib.sha256(b"content-v1").hexdigest(),
        "storage_state": "PERSISTED",
        "idempotency_key": "key-123",
    }
    mock_existing = MagicMock()
    mock_existing.mappings.return_value.first.return_value = existing_row
    db.execute = AsyncMock(return_value=mock_existing)

    desc2 = await run_service.store_artifact_bytes(
        db,
        "run-idem-1",
        name="output.txt",
        content=b"content-v1",
        idempotency_key="key-123",
    )
    assert desc2.artifact_id == desc1.artifact_id

    # 3. Same idempotency_key with different checksum raises idempotency_conflict
    with pytest.raises(RuntimeError, match="errors.artifact.idempotency_conflict"):
        await run_service.store_artifact_bytes(
            db,
            "run-idem-1",
            name="output.txt",
            content=b"different-content",
            idempotency_key="key-123",
        )


@pytest.mark.asyncio
async def test_upload_internal_artifact_error_codes(monkeypatch, tmp_path):
    from app.api.internal_runs import upload_internal_artifact
    from app.schemas import ArtifactUploadRequest, RunView
    from fastapi.responses import JSONResponse
    import json

    monkeypatch.setattr("app.services.run_service.settings.SKILL_AGENT_ARTIFACT_DIR", str(tmp_path))
    db = AsyncMock()

    mock_run = RunView(
        run_id="run-err-1",
        org_id="org-good",
        user_id="user-1",
        tool_name="tool-1",
        status="RUNNING",
        snapshot={},
        generation=2,
        attempt_id="att-2",
        created_at="2026-08-29T00:00:00Z",
        updated_at="2026-08-29T00:00:00Z",
    )

    with patch("app.services.run_service.get_run", return_value=mock_run):
        # 1. unauthorized_scope (org mismatch)
        res_org = await upload_internal_artifact(
            "run-err-1",
            ArtifactUploadRequest(name="a.txt", content_base64="aGVsbG8="),
            db=db,
            x_exec_org_id="org-bad",
        )
        assert isinstance(res_org, JSONResponse)
        assert res_org.status_code == 403
        body = json.loads(res_org.body.decode())
        assert body["error_code"] == "errors.artifact.unauthorized_scope"

        # 2. stale_generation
        res_gen = await upload_internal_artifact(
            "run-err-1",
            ArtifactUploadRequest(name="a.txt", content_base64="aGVsbG8=", generation=1),
            db=db,
            x_exec_org_id="org-good",
        )
        assert isinstance(res_gen, JSONResponse)
        assert res_gen.status_code == 409
        body = json.loads(res_gen.body.decode())
        assert body["error_code"] == "errors.artifact.stale_generation"

        # 3. size_mismatch
        res_sz = await upload_internal_artifact(
            "run-err-1",
            ArtifactUploadRequest(name="a.txt", content_base64="aGVsbG8=", size=999),
            db=db,
            x_exec_org_id="org-good",
        )
        assert isinstance(res_sz, JSONResponse)
        assert res_sz.status_code == 400
        body = json.loads(res_sz.body.decode())
        assert body["error_code"] == "errors.artifact.size_mismatch"

        # 4. checksum_mismatch
        res_chk = await upload_internal_artifact(
            "run-err-1",
            ArtifactUploadRequest(name="a.txt", content_base64="aGVsbG8=", checksum_sha256="badchecksum"),
            db=db,
            x_exec_org_id="org-good",
        )
        assert isinstance(res_chk, JSONResponse)
        assert res_chk.status_code == 400
        body = json.loads(res_chk.body.decode())
        assert body["error_code"] == "errors.artifact.checksum_mismatch"

        # 5. missing_field (empty name)
        res_mf = await upload_internal_artifact(
            "run-err-1",
            ArtifactUploadRequest(name="", content_base64="aGVsbG8="),
            db=db,
            x_exec_org_id="org-good",
        )
        assert isinstance(res_mf, JSONResponse)
        assert res_mf.status_code == 400
        body = json.loads(res_mf.body.decode())
        assert body["error_code"] == "errors.artifact.missing_field"


