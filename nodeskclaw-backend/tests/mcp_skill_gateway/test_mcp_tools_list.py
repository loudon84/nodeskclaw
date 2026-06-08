import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.mcp_skill_gateway.auth import McpAuthContext
from app.services.mcp_skill_gateway.handler import dispatch, dispatch_authenticated


@pytest.mark.asyncio
async def test_tools_list_returns_empty_array_without_grants():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    body = {"jsonrpc": "2.0", "id": "tools-1", "method": "tools/list", "params": {}}
    db = AsyncMock()

    with patch(
        "app.services.mcp_skill_gateway.handler.resolve_mcp_user",
        return_value=McpAuthContext(user=user, org=org),
    ), patch(
        "app.services.mcp_skill_gateway.handler.McpToolMapper",
    ) as mock_mapper_cls:
        mock_mapper = AsyncMock()
        mock_mapper.list_tools.return_value = []
        mock_mapper_cls.return_value = mock_mapper

        result = await dispatch(body, "Bearer valid-token", db)

    assert result["result"]["tools"] == []


@pytest.mark.asyncio
async def test_tools_list_never_returns_null():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    body = {"jsonrpc": "2.0", "id": "tools-1", "method": "tools/list", "params": {}}
    db = AsyncMock()

    with patch(
        "app.services.mcp_skill_gateway.handler.McpToolMapper",
    ) as mock_mapper_cls:
        mock_mapper = AsyncMock()
        mock_mapper.list_tools.return_value = [{"name": "tool.a"}]
        mock_mapper_cls.return_value = mock_mapper

        result = await dispatch_authenticated(body, (user, org), db)

    assert result["result"]["tools"] is not None
    assert isinstance(result["result"]["tools"], list)


@pytest.mark.asyncio
async def test_tools_list_different_users_can_differ():
    user_a = MagicMock()
    user_a.id = "user-with-grant"
    user_b = MagicMock()
    user_b.id = "user-without-grant"
    org = MagicMock()
    org.id = "org-1"
    body = {"jsonrpc": "2.0", "id": "tools-1", "method": "tools/list", "params": {}}
    db = AsyncMock()

    with patch(
        "app.services.mcp_skill_gateway.handler.McpToolMapper",
    ) as mock_mapper_cls:
        mock_mapper = AsyncMock()
        mock_mapper.list_tools.side_effect = [
            [{"name": "granted_tool"}],
            [],
        ]
        mock_mapper_cls.return_value = mock_mapper

        granted = await dispatch_authenticated(body, (user_a, org), db)
        denied = await dispatch_authenticated(body, (user_b, org), db)

    assert granted["result"]["tools"] == [{"name": "granted_tool"}]
    assert denied["result"]["tools"] == []
