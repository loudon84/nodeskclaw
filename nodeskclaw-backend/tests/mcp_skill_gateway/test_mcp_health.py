import pytest
from unittest.mock import patch

from app.api.mcp_skill_gateway.router import mcp_health


@pytest.mark.asyncio
async def test_mcp_health_returns_gateway_status():
    db = None
    result = await mcp_health(db=db)

    assert result["ok"] is True
    assert result["service"] == "nodeskclaw-mcp-skill-gateway"
    assert result["status"] == "running"
    assert result["tools"]["count"] >= 3
