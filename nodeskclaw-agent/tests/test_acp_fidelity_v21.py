from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.acp_gateway.assistant_reconciler import AssistantReconciler
from app.acp_gateway.errors import AcpGatewayError
from app.acp_gateway.event_mapping import map_event, strip_runtime_secrets


def test_assistant_delta_plus_matching_snapshot_emits_no_duplicate():
    reconciler = AssistantReconciler()
    delta1 = SimpleNamespace(
        event_type="assistant.delta",
        payload={"message_id": "m1", "delta_seq": 1, "delta": "abc"},
        run_id="run-1",
        event_seq=1,
    )
    delta2 = SimpleNamespace(
        event_type="assistant.delta",
        payload={"message_id": "m1", "delta_seq": 2, "delta": "def"},
        run_id="run-1",
        event_seq=2,
    )
    snapshot = SimpleNamespace(
        event_type="assistant.message",
        payload={"message_id": "m1", "text": "abcdef"},
        run_id="run-1",
        event_seq=3,
    )
    texts: list[str] = []
    for event in (delta1, delta2, snapshot):
        updates, _stop, _perm = map_event(event, agent_ref="sales-expert", reconciler=reconciler)
        for update in updates:
            if update.get("sessionUpdate") == "agent_message_chunk":
                texts.append(update["content"]["text"])
    assert texts == ["abc", "def"]
    assert "".join(texts) == "abcdef"


def test_assistant_snapshot_only_emits_full_text():
    reconciler = AssistantReconciler()
    snapshot = SimpleNamespace(
        event_type="assistant.message",
        payload={"message_id": "m1", "text": "hello world"},
        run_id="run-1",
        event_seq=1,
    )
    updates, _stop, _perm = map_event(snapshot, agent_ref="sales-expert", reconciler=reconciler)
    assert len(updates) == 1
    assert updates[0]["content"]["text"] == "hello world"


def test_assistant_snapshot_suffix_and_mismatch():
    reconciler = AssistantReconciler()
    delta = SimpleNamespace(
        event_type="assistant.delta",
        payload={"message_id": "m1", "delta_seq": 1, "delta": "abc"},
        run_id="run-1",
        event_seq=1,
    )
    map_event(delta, agent_ref="sales-expert", reconciler=reconciler)
    suffix = SimpleNamespace(
        event_type="assistant.message",
        payload={"message_id": "m1", "text": "abcdefXYZ"},
        run_id="run-1",
        event_seq=2,
    )
    updates, _stop, _perm = map_event(suffix, agent_ref="sales-expert", reconciler=reconciler)
    assert updates[0]["content"]["text"] == "defXYZ"

    conflict = SimpleNamespace(
        event_type="assistant.message",
        payload={"message_id": "m1", "text": "zzz"},
        run_id="run-1",
        event_seq=3,
    )
    with pytest.raises(AcpGatewayError) as exc:
        map_event(conflict, agent_ref="sales-expert", reconciler=reconciler)
    assert exc.value.error_code == "ACP_STREAM_RECONCILIATION_MISMATCH"


def test_rich_tool_call_and_result_projection():
    call = SimpleNamespace(
        event_type="tool.call",
        payload={
            "call_id": "c1",
            "tool_name": "terminal",
            "status": "started",
            "arguments": {"cmd": "ls"},
            "redacted": False,
            "truncated": False,
        },
        run_id="run-1",
        event_seq=1,
    )
    updates, _stop, _perm = map_event(call, agent_ref="sales-expert")
    assert updates[0]["status"] == "in_progress"
    assert updates[0]["rawInput"] == {"cmd": "ls"}
    assert updates[0]["redacted"] is False
    assert "pending" not in str(updates[0].get("status"))

    result = SimpleNamespace(
        event_type="tool.result",
        payload={
            "call_id": "c1",
            "status": "completed",
            "content": "ok",
            "structured_content": {"files": ["a"]},
            "redacted": False,
            "truncated": True,
        },
        run_id="run-1",
        event_seq=2,
    )
    updates2, _stop2, _perm2 = map_event(result, agent_ref="sales-expert")
    assert updates2[0]["content"] == "ok"
    assert updates2[0]["structuredContent"] == {"files": ["a"]}
    assert updates2[0]["truncated"] is True


def test_tool_result_failed_projects_error_fields():
    result = SimpleNamespace(
        event_type="tool.result",
        payload={
            "call_id": "c2",
            "status": "failed",
            "error_code": "TOOL_X",
            "error_message": "boom",
        },
        run_id="run-1",
        event_seq=1,
    )
    updates, _stop, _perm = map_event(result, agent_ref="sales-expert")
    assert updates[0]["status"] == "failed"
    assert updates[0]["errorCode"] == "TOOL_X"
    assert updates[0]["errorMessage"] == "boom"


def test_strip_runtime_secrets_recurses_lists():
    cleaned = strip_runtime_secrets({"items": [{"runtime_run_id": "secret", "ok": 1}]})
    assert "runtime_run_id" not in cleaned["items"][0]
    assert cleaned["items"][0]["ok"] == 1


@pytest.mark.asyncio
async def test_pump_failed_raises_jsonrpc_error(monkeypatch):
    from app.acp_gateway import event_pump
    from app.services import run_service

    events = [
        SimpleNamespace(
            event_type="run.failed",
            payload={"error_code": "RUNTIME_PROTOCOL_INVALID", "error": "x"},
            run_id="run-1",
            event_seq=1,
            source_event_id="s1",
        )
    ]

    async def fake_list(db, run_id, *, after_seq):
        return events if after_seq < 1 else []

    monkeypatch.setattr(run_service, "list_events", fake_list)
    monkeypatch.setattr(run_service, "get_run", AsyncMock(return_value=None))
    sent: list[dict] = []

    async def send(frame):
        sent.append(frame)

    with pytest.raises(AcpGatewayError) as exc:
        await event_pump.pump_run_events(
            AsyncMock(),
            run_id="run-1",
            session_id="sess",
            agent_ref="a",
            org_id="o",
            after_seq=0,
            send=send,
        )
    assert exc.value.error_code == "ACP_REMOTE_RUN_FAILED"


@pytest.mark.asyncio
async def test_pump_binding_missing_code_passthrough(monkeypatch):
    from app.acp_gateway import event_pump
    from app.services import run_service

    events = [
        SimpleNamespace(
            event_type="run.failed",
            payload={"error_code": "ACP_RUNTIME_SESSION_BINDING_MISSING", "error": "no session"},
            run_id="run-1",
            event_seq=1,
            source_event_id="s1",
        )
    ]

    async def fake_list(db, run_id, *, after_seq):
        return events if after_seq < 1 else []

    monkeypatch.setattr(run_service, "list_events", fake_list)
    monkeypatch.setattr(run_service, "get_run", AsyncMock(return_value=None))

    with pytest.raises(AcpGatewayError) as exc:
        await event_pump.pump_run_events(
            AsyncMock(),
            run_id="run-1",
            session_id="sess",
            agent_ref="a",
            org_id="o",
            after_seq=0,
            send=AsyncMock(),
        )
    assert exc.value.error_code == "ACP_RUNTIME_SESSION_BINDING_MISSING"


@pytest.mark.asyncio
async def test_pump_rich_tool_capability_maps_to_runtime_unavailable(monkeypatch):
    from app.acp_gateway import event_pump
    from app.services import run_service

    events = [
        SimpleNamespace(
            event_type="run.failed",
            payload={
                "error_code": "RUNTIME_CAPABILITY_MISSING",
                "capability": "run_tool_event_details_v1",
                "error": "Hermes runtime lacks rich-tool capability",
            },
            run_id="run-1",
            event_seq=1,
            source_event_id="s1",
        )
    ]

    async def fake_list(db, run_id, *, after_seq):
        return events if after_seq < 1 else []

    monkeypatch.setattr(run_service, "list_events", fake_list)
    monkeypatch.setattr(run_service, "get_run", AsyncMock(return_value=None))

    with pytest.raises(AcpGatewayError) as exc:
        await event_pump.pump_run_events(
            AsyncMock(),
            run_id="run-1",
            session_id="sess",
            agent_ref="a",
            org_id="o",
            after_seq=0,
            send=AsyncMock(),
        )
    assert exc.value.error_code == "ACP_RUNTIME_UNAVAILABLE"
    assert "rich-tool" in exc.value.message


def test_map_event_keeps_generic_capability_miss_as_remote_run_failed():
    _updates, stop, _perm = map_event(
        {
            "event_type": "run.failed",
            "payload": {"error_code": "RUNTIME_CAPABILITY_MISSING", "error": "missing run_stop"},
            "run_id": "run-1",
            "event_seq": 1,
        },
        agent_ref="a",
    )
    assert stop == "ACP_REMOTE_RUN_FAILED"


@pytest.mark.asyncio
async def test_new_prompt_resets_after_seq(monkeypatch):
    from app.acp_gateway.connection import AcpConnection

    conn = AcpConnection(AsyncMock(), AsyncMock(), {"org_id": "o", "user_id": "u", "agent_ref": "a"}, "cap")
    conn.after_seq = 12
    seen: dict[str, int] = {}

    async def fake_require(params):
        return "sess", {}

    async def fake_create(*args, **kwargs):
        return {"run_id": "run-1", "replay": False}

    async def fake_pump(*args, **kwargs):
        seen["after_seq"] = kwargs["after_seq"]
        return "end_turn"

    monkeypatch.setattr(conn, "_require_session", fake_require)
    monkeypatch.setattr("app.acp_gateway.connection.create_or_replay_prompt_run", fake_create)
    monkeypatch.setattr("app.acp_gateway.connection.pump_run_events", fake_pump)
    await conn._session_prompt("11111111-1111-1111-1111-111111111111", {"sessionId": "sess", "prompt": []})
    assert seen["after_seq"] == 0
    assert conn.after_seq == 0


@pytest.mark.asyncio
async def test_replay_prompt_keeps_after_seq(monkeypatch):
    from app.acp_gateway.connection import AcpConnection

    conn = AcpConnection(AsyncMock(), AsyncMock(), {"org_id": "o", "user_id": "u", "agent_ref": "a"}, "cap")
    conn.after_seq = 7
    seen: dict[str, int] = {}

    async def fake_require(params):
        return "sess", {}

    async def fake_create(*args, **kwargs):
        return {"run_id": "run-1", "replay": True}

    async def fake_pump(*args, **kwargs):
        seen["after_seq"] = kwargs["after_seq"]
        return "end_turn"

    monkeypatch.setattr(conn, "_require_session", fake_require)
    monkeypatch.setattr("app.acp_gateway.connection.create_or_replay_prompt_run", fake_create)
    monkeypatch.setattr("app.acp_gateway.connection.pump_run_events", fake_pump)
    await conn._session_prompt("11111111-1111-1111-1111-111111111111", {"sessionId": "sess", "prompt": []})
    assert seen["after_seq"] == 7


@pytest.mark.asyncio
async def test_prompt_sets_continuity_marker(monkeypatch):
    import uuid

    from app.acp_gateway.prompt import create_or_replay_prompt_run
    from app.schemas import CreateRunRequest

    captured: dict = {}

    async def fake_find(*args, **kwargs):
        return None

    async def fake_create(db, request: CreateRunRequest, *, org_id, user_id):
        captured["route"] = dict(request.route_snapshot or {})
        return MagicMock(run_id=request.run_id, status="QUEUED")

    monkeypatch.setattr("app.acp_gateway.prompt.find_run_by_idempotency", fake_find)
    monkeypatch.setattr("app.acp_gateway.prompt.canonical_prompt_digest", lambda prompt: "d")
    monkeypatch.setattr("app.acp_gateway.prompt.parse_prompt_attachments", lambda prompt: [])
    monkeypatch.setattr("app.acp_gateway.prompt.run_service.create_run", fake_create)

    async def fetch_context(**kwargs):
        return {"route_snapshot": {"expert_slug": "a"}, "execution_context": {}, "context_version": 1}

    await create_or_replay_prompt_run(
        AsyncMock(),
        session_id=str(uuid.uuid4()),
        request_id=str(uuid.uuid4()),
        prompt=[{"type": "text", "text": "hi"}],
        capability_token="cap",
        claims={"org_id": "o", "user_id": "u", "agent_ref": "a", "trace_id": "t"},
        fetch_context=fetch_context,
    )
    assert captured["route"].get("session_continuity_required") is True


@pytest.mark.asyncio
async def test_continuity_lost_when_once_bound_missing(monkeypatch):
    from app.acp_gateway.errors import AcpGatewayError
    from app.acp_gateway.prompt import create_or_replay_prompt_run
    from app.schemas import CreateRunRequest
    import uuid

    async def fake_find(*args, **kwargs):
        return None

    async def fake_create(db, request: CreateRunRequest, *, org_id, user_id):
        raise ValueError("ACP_RUNTIME_SESSION_CONTINUITY_LOST")

    monkeypatch.setattr("app.acp_gateway.prompt.find_run_by_idempotency", fake_find)
    monkeypatch.setattr("app.acp_gateway.prompt.canonical_prompt_digest", lambda prompt: "d")
    monkeypatch.setattr("app.acp_gateway.prompt.parse_prompt_attachments", lambda prompt: [])
    monkeypatch.setattr("app.acp_gateway.prompt.run_service.create_run", fake_create)

    async def fetch_context(**kwargs):
        return {"route_snapshot": {"expert_slug": "a"}, "execution_context": {}, "context_version": 1}

    with pytest.raises(AcpGatewayError) as exc:
        await create_or_replay_prompt_run(
            AsyncMock(),
            session_id=str(uuid.uuid4()),
            request_id=str(uuid.uuid4()),
            prompt=["x"],
            capability_token="cap",
            claims={"org_id": "o", "user_id": "u", "agent_ref": "a"},
            fetch_context=fetch_context,
        )
    assert exc.value.error_code == "ACP_RUNTIME_SESSION_CONTINUITY_LOST"


@pytest.mark.asyncio
async def test_copy_continuation_fail_closed_acp_path(monkeypatch):
    from app.schemas import CreateRunRequest
    from app.services import run_service

    request = CreateRunRequest(
        run_id="run-new",
        tool_name=run_service.REMOTE_AGENT_TOOL_NAME,
        org_id="o",
        user_id="u",
        arguments={},
        route_snapshot={"session_continuity_required": True, "expert_slug": "a"},
        run_session_id="sess-1",
    )

    async def fake_binding(db, *, run_session_id, org_id, user_id, run_id):
        return {"binding": None, "ever_started": True}

    monkeypatch.setattr(run_service, "_remote_acp_continuity_binding", fake_binding)
    with pytest.raises(ValueError) as exc:
        await run_service._copy_remote_agent_continuation(
            AsyncMock(), request, org_id="o", user_id="u"
        )
    assert "ACP_RUNTIME_SESSION_CONTINUITY_LOST" in str(exc.value)


@pytest.mark.asyncio
async def test_copy_continuation_http_path_still_silent(monkeypatch):
    from app.schemas import CreateRunRequest
    from app.services import run_service

    request = CreateRunRequest(
        run_id="run-new",
        tool_name=run_service.REMOTE_AGENT_TOOL_NAME,
        org_id="o",
        user_id="u",
        arguments={},
        route_snapshot={"expert_slug": "a"},
        run_session_id="sess-1",
    )

    async def fake_latest(*args, **kwargs):
        return "prior-run"

    async def fake_runtime(*args, **kwargs):
        return None

    monkeypatch.setattr(run_service, "_latest_remote_agent_run_id", fake_latest)
    monkeypatch.setattr(run_service, "_runtime_session_id_for_run", fake_runtime)
    out = await run_service._copy_remote_agent_continuation(
        AsyncMock(), request, org_id="o", user_id="u"
    )
    assert out.route_snapshot.get("session_id") is None
