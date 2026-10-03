import uuid
from unittest.mock import AsyncMock

import pytest

from app.acp_gateway.errors import AcpGatewayError
from app.acp_gateway.prompt import create_or_replay_prompt_run, prompt_idempotency_key, require_uuid_request_id
from app.acp_gateway.resources import parse_prompt_attachments


def test_mutating_id_must_be_uuid():
    try:
        require_uuid_request_id(1)
        assert False
    except AcpGatewayError as exc:
        assert exc.error_code == "ACP_PROTOCOL_ERROR"
    assert require_uuid_request_id(str(uuid.uuid4()))


def test_local_path_resource_rejected():
    try:
        parse_prompt_attachments([{"type": "resource_link", "uri": "file:///C:/secret.txt"}])
        assert False
    except AcpGatewayError as exc:
        assert exc.error_code == "ACP_RESOURCE_DENIED"


@pytest.mark.asyncio
async def test_prompt_replay_skips_backend(monkeypatch):
    request_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    digest_run = {
        "id": "run-1",
        "status": "QUEUED",
        "arguments": {"acp_prompt_digest": "abc"},
    }

    async def fake_find(*args, **kwargs):
        return digest_run

    fetch = AsyncMock()
    monkeypatch.setattr("app.acp_gateway.prompt.find_run_by_idempotency", fake_find)
    monkeypatch.setattr("app.acp_gateway.prompt.canonical_prompt_digest", lambda prompt: "abc")
    result = await create_or_replay_prompt_run(
        AsyncMock(),
        session_id=session_id,
        request_id=request_id,
        prompt=[{"type": "text", "text": "hi"}],
        capability_token="cap",
        claims={"org_id": "o", "user_id": "u", "agent_ref": "a", "trace_id": "t"},
        fetch_context=fetch,
    )
    assert result["replay"] is True
    fetch.assert_not_called()


@pytest.mark.asyncio
async def test_prompt_conflict_zero_mutation(monkeypatch):
    request_id = str(uuid.uuid4())

    async def fake_find(*args, **kwargs):
        return {"id": "run-1", "status": "QUEUED", "arguments": {"acp_prompt_digest": "old"}}

    monkeypatch.setattr("app.acp_gateway.prompt.find_run_by_idempotency", fake_find)
    monkeypatch.setattr("app.acp_gateway.prompt.canonical_prompt_digest", lambda prompt: "new")
    try:
        await create_or_replay_prompt_run(
            AsyncMock(),
            session_id=str(uuid.uuid4()),
            request_id=request_id,
            prompt=["x"],
            capability_token="cap",
            claims={"org_id": "o", "user_id": "u", "agent_ref": "a"},
            fetch_context=AsyncMock(),
        )
        assert False
    except AcpGatewayError as exc:
        assert exc.error_code == "ACP_IDEMPOTENCY_CONFLICT"


def test_idempotency_key_stable():
    sid = "session"
    rid = "11111111-1111-1111-1111-111111111111"
    assert prompt_idempotency_key(sid, rid) == prompt_idempotency_key(sid, rid)
