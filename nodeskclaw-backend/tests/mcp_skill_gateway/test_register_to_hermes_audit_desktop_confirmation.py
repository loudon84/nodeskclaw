import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.mcp_skill_gateway.handler import dispatch_authenticated


@pytest.mark.asyncio
async def test_register_audit_includes_desktop_confirmation_fields():
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
            "arguments": {"gene_slug": "contact-to-order", "profile_id": "default"},
        },
    }
    db = AsyncMock()

    with patch(
        "app.services.mcp_skill_gateway.genehub_tools.GeneHubMcpToolProvider.call_tool",
        new=AsyncMock(
            return_value={
                "job_id": "job-1",
                "status": "pending",
                "source": "mcp_agent_request",
                "gene_slug": "contact-to-order",
                "gene_version": "1.0.0",
                "skill_name": "contact-to-order",
                "profile_id": "profile-server-1",
                "profile_name": "default",
                "action": "install",
                "desktop_confirmation_required": True,
                "message": "ok",
            }
        ),
    ), patch(
        "app.services.mcp_skill_gateway.handler.log_mcp_call",
        new=AsyncMock(),
    ) as log_mock:
        await dispatch_authenticated(body, (user, org), db)

    kwargs = log_mock.await_args.kwargs
    assert kwargs["approval_mode"] == "desktop"
    assert kwargs["result_summary"]["source"] == "mcp_agent_request"
    assert kwargs["result_summary"]["desktop_confirmation_required"] is True
    assert kwargs["result_summary"]["job_id"] == "job-1"
