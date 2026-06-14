import pytest
from unittest.mock import AsyncMock

from app.services.mcp_skill_gateway.handler import dispatch


@pytest.mark.asyncio
async def test_genehub_tool_requires_auth():
    body = {
        "jsonrpc": "2.0",
        "id": "call-1",
        "method": "tools/call",
        "params": {
            "name": "genehub.skills.search",
            "arguments": {},
        },
    }
    db = AsyncMock()

    result = await dispatch(body, None, db)

    assert result["error"]["data"]["errorCode"] == "MCP_AUTH_REQUIRED"
