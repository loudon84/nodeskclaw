import pytest

from app.api.mcp_skill_gateway.router import mcp_health


@pytest.mark.asyncio
async def test_mcp_health_returns_gateway_status():
    result = await mcp_health()

    assert result["ok"] is True
    assert result["service"] == "nodeskclaw-mcp-skill-gateway"
    assert result["status"] == "running"
    assert result["protocolVersion"] == "2025-06-18"
    assert result["tools"]["count"] >= 3
    assert result["tools"]["read"] >= 3
    assert result["tools"]["write"] == 0
    assert result["tools"]["admin"] == 0
