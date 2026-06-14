import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.mcp_skill_gateway.approval_service import GrantCheckResult
from app.services.mcp_skill_gateway.handler import dispatch_authenticated


@pytest.mark.asyncio
async def test_genehub_register_writes_audit():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    body = {
        "jsonrpc": "2.0",
        "id": "call-1",
        "method": "tools/call",
        "params": {
            "name": "genehub.skill.register_to_hermes",
            "arguments": {"gene_slug": "contact-to-order"},
        },
    }
    db = AsyncMock()

    with patch(
        "app.services.mcp_skill_gateway.genehub_tools.GeneHubMcpToolProvider.call_tool",
        new=AsyncMock(
            return_value={
                "job_id": "job-1",
                "status": "pending",
                "gene_slug": "contact-to-order",
                "gene_version": "1.0.0",
                "skill_name": "contact-to-order",
                "profile_id": "default",
                "action": "install",
                "message": "ok",
            }
        ),
    ), patch(
        "app.services.mcp_skill_gateway.handler.check_tool_grant",
        new=AsyncMock(return_value=GrantCheckResult(allowed=True)),
    ), patch(
        "app.services.mcp_skill_gateway.handler.log_mcp_call",
        new=AsyncMock(),
    ) as log_mock:
        await dispatch_authenticated(body, (user, org), db)

    log_mock.assert_awaited_once()
    kwargs = log_mock.await_args.kwargs
    assert kwargs["status"] == "success"
    assert kwargs["permission"] == "write"
    assert kwargs["result_summary"]["gene_slug"] == "contact-to-order"
    assert kwargs["result_summary"]["job_id"] == "job-1"
