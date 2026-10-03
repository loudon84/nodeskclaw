from unittest.mock import AsyncMock

import pytest

from app.acp_gateway.errors import AcpGatewayError
from app.acp_gateway.jsonrpc import parse_frame
from app.acp_gateway.session import assert_session_scope


def test_initialize_rejects_v2():
    from app.acp_gateway.connection import AcpConnection

    class Dummy:
        pass

    conn = AcpConnection(Dummy(), Dummy(), {"org_id": "o", "user_id": "u", "agent_ref": "a"}, "cap")
    try:
        conn._initialize({"protocolVersion": 2})
        assert False
    except AcpGatewayError as exc:
        assert exc.error_code == "ACP_PROTOCOL_ERROR"


def test_initialize_accepts_v1():
    from app.acp_gateway.connection import AcpConnection

    class Dummy:
        pass

    conn = AcpConnection(Dummy(), Dummy(), {"org_id": "o", "user_id": "u", "agent_ref": "a"}, "cap")
    result = conn._initialize({"protocolVersion": 1})
    assert result["protocolVersion"] == 1
    assert "resume" in result["agentCapabilities"]["sessionCapabilities"]


def test_cross_scope_resume_denied():
    row = {"org_id": "org-a", "user_id": "user-a", "metadata": {"agent_ref": "sales-expert"}, "deleted_at": None}
    try:
        assert_session_scope(row, org_id="org-b", user_id="user-a", agent_ref="sales-expert")
        assert False
    except AcpGatewayError as exc:
        assert exc.error_code == "ACP_SESSION_FORBIDDEN"


@pytest.mark.asyncio
async def test_session_new_commits_before_return(monkeypatch):
    from app.acp_gateway.connection import AcpConnection

    db = AsyncMock()
    db.commit = AsyncMock()
    conn = AcpConnection(AsyncMock(), db, {"org_id": "o", "user_id": "u", "agent_ref": "a"}, "cap")
    conn.initialized = True

    async def fake_create(*args, **kwargs):
        return "sess-1"

    monkeypatch.setattr("app.acp_gateway.connection.create_session", fake_create)
    result = await conn._session_new({"cwd": "/", "mcpServers": []})
    assert result == {"sessionId": "sess-1"}
    db.commit.assert_awaited()


def test_parse_frame_requires_jsonrpc():
    try:
        parse_frame("{}")
        assert False
    except AcpGatewayError as exc:
        assert exc.error_code == "ACP_PROTOCOL_ERROR"
