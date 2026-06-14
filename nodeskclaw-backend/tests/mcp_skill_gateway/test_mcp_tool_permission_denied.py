import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.mcp_skill_gateway.errors import MCP_TOOL_DISABLED
from app.services.mcp_skill_gateway.handler import dispatch_authenticated


@pytest.mark.asyncio
async def test_tools_call_write_tool_returns_disabled():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    body = {
        "jsonrpc": "2.0",
        "id": "call-1",
        "method": "tools/call",
        "params": {
            "name": "hermes.skills.install_builtin",
            "arguments": {},
        },
    }
    db = AsyncMock()

    with patch(
        "app.services.mcp_skill_gateway.handler.HermesDockerToolProvider",
    ) as provider_cls, patch(
        "app.services.mcp_skill_gateway.handler.log_mcp_call",
        new=AsyncMock(),
    ):
        from app.core.exceptions import ForbiddenError

        provider = AsyncMock()
        provider.call_tool.side_effect = ForbiddenError("disabled", MCP_TOOL_DISABLED)
        provider_cls.return_value = provider

        result = await dispatch_authenticated(body, (user, org), db)

    assert result["error"]["code"] == -32021
    assert result["error"]["data"]["errorCode"] == MCP_TOOL_DISABLED
