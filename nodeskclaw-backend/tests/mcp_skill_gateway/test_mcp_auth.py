import pytest
from unittest.mock import AsyncMock, patch

from app.services.mcp_skill_gateway.errors import MCP_AUTH_REQUIRED
from app.services.mcp_skill_gateway.handler import dispatch


@pytest.mark.asyncio
async def test_dispatch_missing_authorization_returns_mcp_auth_required():
    body = {"jsonrpc": "2.0", "id": "test", "method": "tools/list", "params": {}}
    db = AsyncMock()

    result = await dispatch(body, None, db)

    assert result["error"]["code"] == -32010
    assert result["error"]["message"] == "Missing or invalid Authorization header"
    assert result["error"]["data"]["errorCode"] == MCP_AUTH_REQUIRED


@pytest.mark.asyncio
async def test_dispatch_invalid_token_returns_mcp_auth_required():
    from fastapi import HTTPException

    body = {"jsonrpc": "2.0", "id": "test", "method": "tools/list", "params": {}}
    db = AsyncMock()

    with patch(
        "app.core.security._get_user_by_token",
        side_effect=HTTPException(status_code=401, detail={}),
    ):
        result = await dispatch(body, "Bearer bad-token", db)

    assert result["error"]["data"]["errorCode"] == MCP_AUTH_REQUIRED


@pytest.mark.asyncio
async def test_dispatch_authenticated_tools_list():
    from app.services.mcp_skill_gateway.auth import McpAuthContext

    user = AsyncMock()
    user.id = "user-1"
    org = AsyncMock()
    org.id = "org-1"
    body = {"jsonrpc": "2.0", "id": "tools-1", "method": "tools/list", "params": {}}
    db = AsyncMock()

    with patch(
        "app.services.mcp_skill_gateway.handler.resolve_mcp_user",
        return_value=McpAuthContext(user=user, org=org),
    ), patch(
        "app.services.mcp_skill_gateway.handler.McpToolMapper",
    ) as mock_mapper_cls, patch(
        "app.services.mcp_skill_gateway.handler.list_enabled_tools",
        return_value=[],
    ), patch(
        "app.services.mcp_skill_gateway.handler.get_grant_annotation",
        new=AsyncMock(return_value=None),
    ):
        mock_mapper = AsyncMock()
        mock_mapper.list_tools.return_value = [{"name": "coding.create_prd"}]
        mock_mapper_cls.return_value = mock_mapper

        result = await dispatch(body, "Bearer valid-token", db)

    assert result["result"]["tools"] == [{"name": "coding.create_prd"}]
