import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.mcp_skill_gateway.handler import dispatch_authenticated


@pytest.mark.asyncio
async def test_tools_call_success_writes_audit():
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
        "app.services.mcp_skill_gateway.handler.HermesDockerToolProvider",
    ) as provider_cls, patch(
        "app.services.mcp_skill_gateway.handler.log_mcp_call",
        new=AsyncMock(),
    ) as log_mock:
        provider = AsyncMock()
        provider.call_tool.return_value = {"instances": [{"instance_id": "inst-1"}]}
        provider_cls.return_value = provider

        await dispatch_authenticated(body, (user, org), db)

    log_mock.assert_awaited_once()
    kwargs = log_mock.await_args.kwargs
    assert kwargs["status"] == "success"
    assert kwargs["tool_name"] == "hermes.instances.list"
    assert kwargs["permission"] == "read"
    assert kwargs["risk_level"] == "low"
    assert kwargs["result_summary"] == {"instances_count": 1}
