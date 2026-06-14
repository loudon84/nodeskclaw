import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.genehub import McpRegistrationInfo
from app.services.mcp_skill_gateway.handler import dispatch_authenticated


@pytest.mark.asyncio
async def test_genehub_registration_status_by_job_id():
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
            "arguments": {"job_id": "job-1"},
        },
    }
    db = AsyncMock()
    registration = McpRegistrationInfo(
        job_id="job-1",
        gene_slug="contact-to-order",
        gene_version="1.0.0",
        skill_name="contact-to-order",
        profile_id="default",
        action="install",
        status="installed",
    )

    with patch(
        "app.services.mcp_skill_gateway.genehub_tools.genehub_service.get_registration_status",
        new=AsyncMock(return_value=registration),
    ), patch(
        "app.services.mcp_skill_gateway.genehub_tools._load_user",
        new=AsyncMock(return_value=user),
    ), patch(
        "app.services.mcp_skill_gateway.handler.log_mcp_call",
        new=AsyncMock(),
    ):
        result = await dispatch_authenticated(body, (user, org), db)

    payload = json.loads(result["result"]["content"][0]["text"])
    assert payload["registration"]["status"] == "installed"


@pytest.mark.asyncio
async def test_genehub_registration_status_by_gene_slug():
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
            "arguments": {"gene_slug": "contact-to-order", "profile_id": "default"},
        },
    }
    db = AsyncMock()
    registration = McpRegistrationInfo(
        job_id="job-1",
        gene_slug="contact-to-order",
        status="pending",
    )

    with patch(
        "app.services.mcp_skill_gateway.genehub_tools.genehub_service.get_registration_status",
        new=AsyncMock(return_value=registration),
    ), patch(
        "app.services.mcp_skill_gateway.genehub_tools.resolve_desktop_profile",
        new=AsyncMock(return_value=MagicMock(id="profile-1")),
    ), patch(
        "app.services.mcp_skill_gateway.genehub_tools._load_user",
        new=AsyncMock(return_value=user),
    ), patch(
        "app.services.mcp_skill_gateway.handler.log_mcp_call",
        new=AsyncMock(),
    ):
        result = await dispatch_authenticated(body, (user, org), db)

    payload = json.loads(result["result"]["content"][0]["text"])
    assert payload["registration"]["gene_slug"] == "contact-to-order"
