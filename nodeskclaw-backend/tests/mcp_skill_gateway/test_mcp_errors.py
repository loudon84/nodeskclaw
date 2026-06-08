import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.mcp_skill_gateway.errors import (
    MCP_INVALID_REQUEST,
    MCP_METHOD_NOT_FOUND,
    mcp_error,
)
from app.services.mcp_skill_gateway.handler import dispatch_authenticated


def test_mcp_error_includes_error_code_in_data():
    result = mcp_error("req-1", MCP_INVALID_REQUEST, "bad request")

    assert result["error"]["data"]["errorCode"] == MCP_INVALID_REQUEST
    assert result["error"]["data"]["reason"] == "bad request"


@pytest.mark.asyncio
async def test_invalid_jsonrpc_version():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    body = {"jsonrpc": "1.0", "id": 1, "method": "tools/list"}
    db = AsyncMock()

    result = await dispatch_authenticated(body, (user, org), db)

    assert result["error"]["code"] == -32600
    assert result["error"]["data"]["errorCode"] == MCP_INVALID_REQUEST


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
