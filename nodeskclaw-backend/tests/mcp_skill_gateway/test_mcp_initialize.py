import pytest
from unittest.mock import AsyncMock, patch

from app.services.mcp_skill_gateway.auth import McpAuthContext
from app.services.mcp_skill_gateway.handler import dispatch


@pytest.mark.asyncio
async def test_initialize_returns_protocol_and_server_info():
    user = AsyncMock()
    user.id = "user-1"
    org = AsyncMock()
    org.id = "org-1"
    body = {
        "jsonrpc": "2.0",
        "id": "init-1",
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "smc-copilot-desktop", "version": "v6.4.1"},
        },
    }
    db = AsyncMock()

    with patch(
        "app.services.mcp_skill_gateway.handler.resolve_mcp_user",
        return_value=McpAuthContext(user=user, org=org),
    ):
        result = await dispatch(body, "Bearer valid-token", db)

    assert result["id"] == "init-1"
    assert result["result"]["protocolVersion"] == "2025-06-18"
    assert result["result"]["capabilities"]["tools"]["listChanged"] is True
    assert result["result"]["serverInfo"]["name"] == "nodeskclaw-mcp-skill-gateway"
    assert "version" in result["result"]["serverInfo"]
