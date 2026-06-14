import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import NotFoundError
from app.services.mcp_skill_gateway.handler import dispatch_authenticated


@pytest.mark.asyncio
async def test_genehub_register_failure_writes_audit():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    body = {
        "jsonrpc": "2.0",
        "id": "call-1",
        "method": "tools/call",
        "params": {
            "name": "genehub.registration.status",
            "arguments": {"job_id": "missing"},
        },
    }
    db = AsyncMock()

    with patch(
        "app.services.mcp_skill_gateway.genehub_tools.GeneHubMcpToolProvider.call_tool",
        new=AsyncMock(
            side_effect=NotFoundError(
                "missing",
                "errors.genehub.install_job_not_found",
            )
        ),
    ), patch(
        "app.services.mcp_skill_gateway.handler.log_mcp_call",
        new=AsyncMock(),
    ) as log_mock:
        result = await dispatch_authenticated(body, (user, org), db)

    assert result["error"]["data"]["errorCode"] == "GENEHUB_JOB_NOT_FOUND"
    log_mock.assert_awaited_once()
    assert log_mock.await_args.kwargs["status"] == "failed"
