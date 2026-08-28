"""Agent run_service fencing and approval helpers (unit, mocked DB)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas import CreateRunRequest
from app.services import run_service


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
    # Existing session belonging to another org
    mock_res.mappings.return_value.first.return_value = {"id": "sess-1", "org_id": "org-other"}
    db.execute = AsyncMock(return_value=mock_res)

    req = CreateRunRequest(
        run_id="run-1",
        tool_name="test_tool",
        run_session_id="sess-1",
    )
    with pytest.raises(ValueError, match="cross-org run session access rejected"):
        await run_service.create_run(db, req, org_id="org-1", user_id="user-1")


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




