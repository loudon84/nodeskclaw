import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import NotFoundError
from app.services.mcp_skill_gateway.errors import HERMES_INSTANCE_NOT_FOUND
from app.services.mcp_skill_gateway.handler import dispatch_authenticated


@pytest.mark.asyncio
async def test_tools_call_failure_writes_audit_with_error_code():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    body = {
        "jsonrpc": "2.0",
        "id": "call-1",
        "method": "tools/call",
        "params": {
            "name": "hermes.instance.status",
            "arguments": {"instance_ref": "missing"},
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
        provider.call_tool.side_effect = NotFoundError(
            "not found",
            "errors.external_docker.instance_not_found",
        )
        provider_cls.return_value = provider

        result = await dispatch_authenticated(body, (user, org), db)

    assert result["error"]["data"]["errorCode"] == HERMES_INSTANCE_NOT_FOUND
    log_mock.assert_awaited_once()
    kwargs = log_mock.await_args.kwargs
    assert kwargs["status"] == "failed"
    assert kwargs["error_code"] == HERMES_INSTANCE_NOT_FOUND
