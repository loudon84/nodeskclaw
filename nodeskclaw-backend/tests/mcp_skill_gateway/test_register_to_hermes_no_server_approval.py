import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.genehub import McpRegistrationJobResult
from app.services.mcp_skill_gateway.errors import MCP_TOOL_APPROVAL_REQUIRED
from app.services.mcp_skill_gateway.handler import dispatch_authenticated


@pytest.mark.asyncio
async def test_register_to_hermes_does_not_return_server_approval_required():
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
            "arguments": {
                "gene_slug": "contact-to-order",
                "profile_id": "default",
                "action": "install",
            },
        },
    }
    db = AsyncMock()
    job_result = McpRegistrationJobResult(
        job_id="job-1",
        status="pending",
        source="mcp_agent_request",
        gene_slug="contact-to-order",
        gene_version="1.0.0",
        skill_name="contact-to-order",
        profile_id="profile-server-1",
        profile_name="default",
        action="install",
        desktop_confirmation_required=True,
        message="Install job created. Copilot Desktop will apply it locally after user confirmation.",
    )

    with patch(
        "app.services.mcp_skill_gateway.genehub_tools.genehub_service.create_mcp_registration_job",
        new=AsyncMock(return_value=job_result),
    ), patch(
        "app.services.mcp_skill_gateway.genehub_tools.resolve_desktop_profile",
        new=AsyncMock(return_value=MagicMock(id="profile-server-1", profile_name="default")),
    ), patch(
        "app.services.mcp_skill_gateway.genehub_tools._load_user",
        new=AsyncMock(return_value=user),
    ), patch(
        "app.services.mcp_skill_gateway.handler.log_mcp_call",
        new=AsyncMock(),
    ):
        result = await dispatch_authenticated(body, (user, org), db)

    assert "error" not in result
    payload = json.loads(result["result"]["content"][0]["text"])
    assert payload["job_id"] == "job-1"
    assert payload["status"] == "pending"
    assert payload["source"] == "mcp_agent_request"
    assert payload["desktop_confirmation_required"] is True
    error_code = result.get("error", {}).get("data", {}).get("errorCode")
    assert error_code != MCP_TOOL_APPROVAL_REQUIRED
