import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.genehub import McpRegistrationJobResult
from app.services.mcp_skill_gateway.approval_service import GrantCheckResult
from app.services.mcp_skill_gateway.handler import dispatch_authenticated


@pytest.mark.asyncio
async def test_genehub_register_to_hermes_creates_job():
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
        gene_slug="contact-to-order",
        gene_version="1.0.0",
        skill_name="contact-to-order",
        profile_id="default",
        action="install",
        message="Install job created. Copilot Desktop will apply it locally after user confirmation.",
    )

    with patch(
        "app.services.mcp_skill_gateway.genehub_tools.genehub_service.create_mcp_registration_job",
        new=AsyncMock(return_value=job_result),
    ), patch(
        "app.services.mcp_skill_gateway.genehub_tools.resolve_desktop_profile",
        new=AsyncMock(return_value=MagicMock(id="profile-1", profile_name="default")),
    ), patch(
        "app.services.mcp_skill_gateway.genehub_tools._load_user",
        new=AsyncMock(return_value=user),
    ), patch(
        "app.services.mcp_skill_gateway.handler.check_tool_grant",
        new=AsyncMock(return_value=GrantCheckResult(allowed=True)),
    ), patch(
        "app.services.mcp_skill_gateway.handler.log_mcp_call",
        new=AsyncMock(),
    ):
        result = await dispatch_authenticated(body, (user, org), db)

    payload = json.loads(result["result"]["content"][0]["text"])
    assert payload["job_id"] == "job-1"
    assert payload["status"] == "pending"


@pytest.mark.asyncio
async def test_genehub_register_duplicate_active_job():
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
    job_result = McpRegistrationJobResult(
        job_id="job-existing",
        status="pending",
        gene_slug="contact-to-order",
        gene_version="1.0.0",
        skill_name="contact-to-order",
        profile_id="default",
        action="install",
        message="Existing install job returned.",
    )

    with patch(
        "app.services.mcp_skill_gateway.genehub_tools.genehub_service.create_mcp_registration_job",
        new=AsyncMock(return_value=job_result),
    ), patch(
        "app.services.mcp_skill_gateway.genehub_tools.resolve_desktop_profile",
        new=AsyncMock(return_value=MagicMock(id="profile-1", profile_name="default")),
    ), patch(
        "app.services.mcp_skill_gateway.genehub_tools._load_user",
        new=AsyncMock(return_value=user),
    ), patch(
        "app.services.mcp_skill_gateway.handler.check_tool_grant",
        new=AsyncMock(return_value=GrantCheckResult(allowed=True)),
    ), patch(
        "app.services.mcp_skill_gateway.handler.log_mcp_call",
        new=AsyncMock(),
    ):
        result = await dispatch_authenticated(body, (user, org), db)

    payload = json.loads(result["result"]["content"][0]["text"])
    assert payload["job_id"] == "job-existing"
