import json
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.mcp_tool_grant import McpToolGrant
from app.services.mcp_skill_gateway.approval_service import GrantCheckResult
from app.services.mcp_skill_gateway.errors import (
    MCP_TOOL_APPROVAL_REQUIRED,
    MCP_TOOL_GRANT_REVOKED,
)
from app.services.mcp_skill_gateway.handler import dispatch_authenticated


def _grant_result(grant: McpToolGrant | None = None) -> GrantCheckResult:
    return GrantCheckResult(allowed=True, grant=grant)


@pytest.mark.asyncio
async def test_mcp_write_tool_approval_required():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    body = {
        "jsonrpc": "2.0",
        "id": "call-1",
        "method": "tools/call",
        "params": {
            "name": "hermes.skills.uninstall",
            "arguments": {"instance_ref": "demo-inst", "skill_name": "demo-skill"},
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
                data={
                    "toolName": "hermes.skills.uninstall",
                    "approvalRequestId": "apr-1",
                    "approvalMode": "server",
                },
                approval_request_id="apr-1",
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
    assert result["error"]["data"]["approvalRequestId"] == "apr-1"


@pytest.mark.asyncio
async def test_mcp_write_tool_call_with_active_grant():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    body = {
        "jsonrpc": "2.0",
        "id": "call-1",
        "method": "tools/call",
        "params": {
            "name": "hermes.skills.uninstall",
            "arguments": {"instance_ref": "demo-inst", "skill_name": "demo-skill"},
        },
    }
    db = AsyncMock()
    grant = MagicMock()
    grant.constraints_json = None

    with patch(
        "app.services.mcp_skill_gateway.handler.check_tool_grant",
        new=AsyncMock(return_value=_grant_result(grant)),
    ), patch(
        "app.services.mcp_skill_gateway.handler.HermesDockerToolProvider",
    ) as provider_cls, patch(
        "app.services.mcp_skill_gateway.handler.resolve_instance_ref",
        new=AsyncMock(return_value=MagicMock(id="inst-1")),
    ), patch(
        "app.services.mcp_skill_gateway.handler.log_mcp_call",
        new=AsyncMock(),
    ):
        provider = AsyncMock()
        provider.call_tool.return_value = {
            "uninstalled": True,
            "skill_name": "demo-skill",
            "instance_id": "inst-1",
        }
        provider_cls.return_value = provider

        result = await dispatch_authenticated(body, (user, org), db)

    payload = json.loads(result["result"]["content"][0]["text"])
    assert payload["uninstalled"] is True
    provider.call_tool.assert_awaited_once()


@pytest.mark.asyncio
async def test_mcp_revoke_grant_blocks_tool_call():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    body = {
        "jsonrpc": "2.0",
        "id": "call-1",
        "method": "tools/call",
        "params": {
            "name": "hermes.skills.uninstall",
            "arguments": {"instance_ref": "demo-inst", "skill_name": "demo-skill"},
        },
    }
    db = AsyncMock()

    with patch(
        "app.services.mcp_skill_gateway.handler.check_tool_grant",
        new=AsyncMock(
            return_value=GrantCheckResult(
                allowed=False,
                error_code=MCP_TOOL_GRANT_REVOKED,
                message="Tool grant revoked",
                data={
                    "toolName": "hermes.skills.uninstall",
                    "revokedAt": "2026-06-14T00:00:00+00:00",
                },
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

    assert result["error"]["code"] == -32024
    assert result["error"]["data"]["errorCode"] == MCP_TOOL_GRANT_REVOKED


@pytest.mark.asyncio
async def test_mcp_grant_expired_blocks_tool_call():
    from app.services.mcp_skill_gateway.errors import MCP_TOOL_GRANT_EXPIRED

    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    body = {
        "jsonrpc": "2.0",
        "id": "call-1",
        "method": "tools/call",
        "params": {
            "name": "hermes.instance.restart",
            "arguments": {"instance_ref": "demo-inst"},
        },
    }
    db = AsyncMock()

    with patch(
        "app.services.mcp_skill_gateway.handler.check_tool_grant",
        new=AsyncMock(
            return_value=GrantCheckResult(
                allowed=False,
                error_code=MCP_TOOL_GRANT_EXPIRED,
                message="Tool grant expired",
                data={"toolName": "hermes.instance.restart"},
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

    assert result["error"]["data"]["errorCode"] == MCP_TOOL_GRANT_EXPIRED
