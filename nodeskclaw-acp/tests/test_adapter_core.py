import asyncio
from types import SimpleNamespace

import pytest

from app.errors import AdapterError
from app.event_mapper import join_text_blocks, reconcile_final
from app.profile import Profile, load_profile
from app.prompt_turn import PromptTurnController
from app.session_registry import SessionRegistry


def test_profile_rejects_secrets_and_attachments(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("profile_version: 1\nname: n\nagent_ref: a\naccess_token: x\n", encoding="utf-8")
    with pytest.raises(AdapterError) as exc:
        load_profile(path)
    assert exc.value.symbol == "ACP_PROFILE_INVALID"


def test_join_text_and_reject_image():
    assert join_text_blocks([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]) == "a\n\nb"
    with pytest.raises(AdapterError):
        join_text_blocks([{"type": "image", "data": "xx"}])


def test_parse_attachment_resource_link():
    from app.resource_links import parse_prompt_blocks

    text, refs = parse_prompt_blocks(
        [
            {"type": "text", "text": "see"},
            {"type": "resource_link", "uri": "nodeskclaw://attachment/att_1", "name": "a.xlsx"},
            {"type": "resource_link", "uri": "nodeskclaw://attachment/att_1", "name": "a.xlsx"},
        ]
    )
    assert text == "see"
    assert refs == ["att_1"]
    with pytest.raises(AdapterError) as exc:
        parse_prompt_blocks([{"type": "resource_link", "uri": "https://example.com/x"}])
    assert exc.value.symbol == "ACP_RESOURCE_LINK_UNSUPPORTED"


def test_managed_credentials_skip_keyring(monkeypatch):
    from app.config import Settings
    from app.credentials import CredentialStore
    from app.errors import AdapterError

    settings = Settings(
        NODESKCLAW_BASE_URL="https://example.com",
        NODESKCLAW_ACCESS_TOKEN="acc",
        NODESKCLAW_REFRESH_TOKEN="ref",
        NODESKCLAW_CREDENTIAL_MODE="managed",
    )

    def boom(*args, **kwargs):
        raise AssertionError("keyring")

    monkeypatch.setattr("app.credentials.keyring.get_password", boom)
    monkeypatch.setattr("app.credentials.keyring.set_password", boom)
    store = CredentialStore(settings, None)

    async def run():
        token = await store.resolve_access_token()
        assert token == "acc"
        with pytest.raises(AdapterError) as exc:
            store.store_login_tokens("a", "b")
        assert exc.value.symbol == "ACP_DESKTOP_CREDENTIAL_INVALID"

    asyncio.run(run())


def test_initialize_advertises_resume():
    from app.agent import AcpV1Agent
    from app.profile import Profile
    from app.session_registry import SessionRegistry

    agent = AcpV1Agent(
        Profile({"profile_version": 1, "name": "n", "agent_ref": "e"}, "p.yaml"),
        SessionRegistry("e"),
        None,
        None,
        None,
        None,
    )
    result = agent.initialize_result({"protocolVersion": 1})
    assert result["agentCapabilities"]["sessionCapabilities"]["resume"] == {}
    assert result["agentCapabilities"]["loadSession"] is False


@pytest.mark.asyncio
async def test_resume_sets_next_turn_seq(tmp_path):
    from app.agent import AcpV1Agent
    from app.profile import Profile
    from app.session_registry import SessionRegistry

    class Client:
        async def get_session_proof(self, session_id, profile):
            return {"session_ref": session_id, "agent_ref": "e", "status": "idle", "last_run_id": "r1", "next_turn_seq": 4}

    cwd = str(tmp_path.resolve())
    registry = SessionRegistry("e")
    agent = AcpV1Agent(
        Profile({"profile_version": 1, "name": "n", "agent_ref": "e"}, "p.yaml"),
        registry,
        Client(),
        None,
        None,
        None,
    )
    await agent.session_resume({"sessionId": "11111111-1111-1111-1111-111111111111", "cwd": cwd, "mcpServers": []})
    state = registry.get("11111111-1111-1111-1111-111111111111")
    begun = registry.begin_turn(state.session_id)
    assert begun.turn_seq == 4


@pytest.mark.asyncio
async def test_prompt_sends_attachment_refs():
    captured = {}

    class Client:
        async def create_run(self, body):
            captured.update(body)
            return {"id": "run-1"}

        async def stream_events(self, run_id, last_event_id=None):
            yield {"event_id": "1", "event_type": "run.completed", "data": {}}

    profile = Profile({"profile_version": 1, "name": "n", "agent_ref": "e"}, "p.yaml")
    registry = SessionRegistry("e")
    session = registry.create("/tmp")
    turns = PromptTurnController(profile, registry, Client(), SimpleNamespace())
    await turns.run_prompt(
        session.session_id,
        "1",
        [
            {"type": "text", "text": "go"},
            {"type": "resource_link", "uri": "nodeskclaw://attachment/att_9"},
        ],
    )
    assert captured["attachment_refs"] == ["att_9"]


def test_reconcile_mismatch_raises():
    with pytest.raises(AdapterError) as exc:
        reconcile_final("hello", "world", True)
    assert exc.value.symbol == "ACP_STREAM_RECONCILIATION_MISMATCH"


@pytest.mark.asyncio
async def test_overlapping_prompt_is_busy():
    registry = SessionRegistry("sales-expert")
    state = registry.create("/tmp")
    registry.begin_turn(state.session_id)
    state.active_run_id = "run-1"
    with pytest.raises(AdapterError) as exc:
        registry.begin_turn(state.session_id)
    assert exc.value.symbol == "ACP_SESSION_BUSY"


@pytest.mark.asyncio
async def test_create_payload_has_empty_attachments_and_session_ref():
    captured = {}

    class Client:
        async def create_run(self, body):
            captured.update(body)
            return {"id": "run-1"}

        async def stream_events(self, run_id, last_event_id=None):
            yield {"event_id": "1", "event_type": "run.completed", "data": {}}

        async def cancel_run(self, run_id):
            raise AssertionError("cancel")

    profile = Profile(
        {
            "profile_version": 1,
            "name": "sales",
            "agent_ref": "sales-expert",
            "integration_account_refs": ["acc-1"],
        },
        "p.yaml",
    )
    registry = SessionRegistry("sales-expert")
    session = registry.create("/tmp")
    turns = PromptTurnController(profile, registry, Client(), SimpleNamespace(), artifact_hints=False)
    result = await turns.run_prompt(session.session_id, "1", [{"type": "text", "text": "hello"}])
    assert result["stopReason"] == "end_turn"
    assert captured["attachment_refs"] == []
    assert captured["session_ref"] == session.session_id
    assert captured["client_request_id"] == f"acp:{session.session_id}:1"
    assert captured["integration_account_refs"] == ["acc-1"]


@pytest.mark.asyncio
async def test_permission_cancelled_cancels_remote():
    calls = []

    class Client:
        async def create_run(self, body):
            return {"id": "run-1"}

        async def stream_events(self, run_id, last_event_id=None):
            yield {
                "event_id": "1",
                "event_type": "approval.requested",
                "data": {"approval_id": "appr-1", "tool_call_id": "t1"},
            }

        async def cancel_run(self, run_id):
            calls.append(("cancel", run_id))

        async def decide_approval(self, *args, **kwargs):
            calls.append("approve")

    class Perms:
        def options(self):
            return []

        async def apply(self, **kwargs):
            await Client().cancel_run(kwargs["run_id"])
            return "cancelled"

    profile = Profile({"profile_version": 1, "name": "n", "agent_ref": "e"}, "p.yaml")
    registry = SessionRegistry("e")
    session = registry.create("/tmp")

    async def request_permission(params):
        return "cancelled"

    turns = PromptTurnController(
        profile,
        registry,
        Client(),
        Perms(),
        request_permission=request_permission,
    )
    result = await turns.run_prompt(session.session_id, "1", [{"type": "text", "text": "go"}])
    assert result["stopReason"] == "cancelled"
    assert calls == [("cancel", "run-1")]
    assert "approve" not in calls


@pytest.mark.asyncio
async def test_failed_run_is_jsonrpc_error_symbol():
    class Client:
        async def create_run(self, body):
            return {"id": "run-1"}

        async def stream_events(self, run_id, last_event_id=None):
            yield {"event_id": "1", "event_type": "run.timed_out", "data": {"error_code": "TIMEOUT"}}

        async def cancel_run(self, run_id):
            return {}

    profile = Profile({"profile_version": 1, "name": "n", "agent_ref": "e"}, "p.yaml")
    registry = SessionRegistry("e")
    session = registry.create("/tmp")
    turns = PromptTurnController(profile, registry, Client(), SimpleNamespace())
    with pytest.raises(AdapterError) as exc:
        await turns.run_prompt(session.session_id, "1", [{"type": "text", "text": "go"}])
    assert exc.value.symbol == "ACP_REMOTE_RUN_FAILED"
