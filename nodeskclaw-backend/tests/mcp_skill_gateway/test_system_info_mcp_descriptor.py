import pytest

from app.api.router import system_info


@pytest.mark.asyncio
async def test_system_info_includes_mcp_descriptor():
    result = await system_info()

    assert "mcp" in result
    mcp = result["mcp"]
    assert mcp["enabled"] is True
    assert mcp["endpoint"] == "/api/v1/mcp"
    assert mcp["healthEndpoint"] == "/api/v1/mcp/health"
    assert mcp["transport"] == "streamable_http"
    assert mcp["requiresAuth"] is True
    assert mcp["protocolVersion"] == "2025-06-18"
    assert mcp["name"] == "Coding MCP Gateway"
