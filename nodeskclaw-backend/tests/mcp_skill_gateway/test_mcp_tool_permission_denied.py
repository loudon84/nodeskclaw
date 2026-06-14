import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.mcp_skill_gateway.approval_service import GrantCheckResult
from app.services.mcp_skill_gateway.errors import MCP_TOOL_APPROVAL_REQUIRED
from app.services.mcp_skill_gateway.handler import dispatch_authenticated


@pytest.mark.asyncio
async def test_tools_call_write_tool_returns_approval_required():
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
            "arguments": {"instance_ref": "demo", "skill_slug": "writer"},
        },
    }
    db = AsyncMock()

    with patch(
        "app.services.mcp_skill_gateway.handler.check_tool_grant",
        new=AsyncMock(
            return_value=GrantCheckResult(
                allowed=False,
                error_code=MCP_TOOL_APPROVAL_REQUIRED,
                message="Tool approval required",
                data={"approvalRequestId": "apr-1", "toolName": "hermes.skills.install_builtin"},
            )
        ),
    ), patch(
        "app.services.mcp_skill_gateway.handler.log_mcp_call",
        new=AsyncMock(),
    ), patch(
        "app.services.mcp_skill_gateway.handler.resolve_instance_ref",
        new=AsyncMock(return_value=MagicMock(id="inst-1")),
    ):
        result = await dispatch_authenticated(body, (user, org), db)

    assert result["error"]["code"] == -32023
    assert result["error"]["data"]["errorCode"] == MCP_TOOL_APPROVAL_REQUIRED
