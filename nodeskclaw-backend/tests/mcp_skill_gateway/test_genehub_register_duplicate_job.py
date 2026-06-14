import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.mcp_skill_gateway.handler import dispatch_authenticated


@pytest.mark.asyncio
async def test_genehub_register_tool_is_callable():
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
        "app.services.mcp_skill_gateway.handler.log_mcp_call",
        new=AsyncMock(),
    ):
        result = await dispatch_authenticated(body, (user, org), db)

    assert "error" not in result
    payload = json.loads(result["result"]["content"][0]["text"])
    assert payload["job_id"] == "job-1"
