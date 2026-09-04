import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.mcp_skill_gateway.errors import (
    IDEMPOTENCY_CONFLICT,
    MCP_INVALID_ARGUMENTS,
    MCP_METHOD_NOT_FOUND,
    _ERROR_CODES,
    mcp_error_v2,
    mcp_jsonrpc_code,
)
from app.services.mcp_skill_gateway.handler import dispatch_authenticated


def test_mcp_error_v2_includes_error_code_in_data():
    result = mcp_error_v2("req-1", MCP_INVALID_ARGUMENTS, "bad request")

    assert result["error"]["data"]["errorCode"] == MCP_INVALID_ARGUMENTS
    assert result["error"]["message"] == "bad request"


def test_idempotency_conflict_has_dedicated_jsonrpc_code():
    assert IDEMPOTENCY_CONFLICT in _ERROR_CODES
    assert _ERROR_CODES[IDEMPOTENCY_CONFLICT] == -32080
    assert mcp_jsonrpc_code(IDEMPOTENCY_CONFLICT) == -32080

    result = mcp_error_v2("req-idem", IDEMPOTENCY_CONFLICT, "conflict")
    assert result["error"]["code"] == -32080
    assert result["error"]["data"]["errorCode"] == IDEMPOTENCY_CONFLICT


@pytest.mark.asyncio
async def test_invalid_jsonrpc_version():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    body = {"jsonrpc": "1.0", "id": 1, "method": "tools/list"}
    db = AsyncMock()

    result = await dispatch_authenticated(body, (user, org), db)

    assert result["error"]["code"] == -32030
    assert result["error"]["data"]["errorCode"] == MCP_INVALID_ARGUMENTS


@pytest.mark.asyncio
async def test_unknown_method_returns_structured_error():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    body = {"jsonrpc": "2.0", "id": 2, "method": "resources/list"}
    db = AsyncMock()

    result = await dispatch_authenticated(body, (user, org), db)

    assert result["error"]["code"] == -32601
    assert result["error"]["data"]["errorCode"] == MCP_METHOD_NOT_FOUND
