import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.mcp_skill_gateway.handler import dispatch_authenticated


@pytest.mark.asyncio
async def test_tools_call_removed_ops_tool_is_rejected():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    body = {
        "jsonrpc": "2.0",
        "id": "call-1",
        "method": "tools/call",
        "params": {
            "name": "hermes.instances.list",
            "arguments": {},
        },
    }
    db = AsyncMock()

    with patch(
        "app.services.mcp_skill_gateway.handler.log_mcp_call",
        new=AsyncMock(),
    ) as log_mock:
        result = await dispatch_authenticated(body, (user, org), db)

    assert "error" in result
    assert "not available on employee MCP catalog" in result["error"]["message"]
    log_mock.assert_not_awaited()
