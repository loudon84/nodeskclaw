import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.mcp_skill_gateway.handler import dispatch_authenticated


@pytest.mark.asyncio
async def test_tools_call_success_returns_json_content():
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
    payload = {"instances": [{"instance_id": "inst-1", "profile": "demo"}]}

    with patch(
        "app.services.mcp_skill_gateway.handler.HermesDockerToolProvider",
    ) as provider_cls, patch(
        "app.services.mcp_skill_gateway.handler.log_mcp_call",
        new=AsyncMock(),
    ):
        provider = AsyncMock()
        provider.call_tool.return_value = payload
        provider_cls.return_value = provider

        result = await dispatch_authenticated(body, (user, org), db)

    assert result["result"]["isError"] is False
    assert len(result["result"]["content"]) == 1
    assert result["result"]["content"][0]["type"] == "text"
    assert json.loads(result["result"]["content"][0]["text"]) == payload
    assert "structuredContent" not in result["result"]
