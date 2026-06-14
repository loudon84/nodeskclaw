import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.genehub import GeneHubSkillPermissions, McpGeneHubSkillItem
from app.services.mcp_skill_gateway.handler import dispatch_authenticated


@pytest.mark.asyncio
async def test_genehub_skills_search_success():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    body = {
        "jsonrpc": "2.0",
        "id": "call-1",
        "method": "tools/call",
        "params": {
            "name": "genehub.skills.search",
            "arguments": {"query": "order", "profile_id": "profile-1"},
        },
    }
    db = AsyncMock()
    skill = McpGeneHubSkillItem(
        gene_slug="contact-to-order",
        gene_version="1.0.0",
        skill_name="contact-to-order",
        display_name="Contact To Order",
        permissions=GeneHubSkillPermissions(can_install=True),
    )

    with patch(
        "app.services.mcp_skill_gateway.genehub_tools.genehub_service.search_mcp_genehub_skills",
        new=AsyncMock(return_value=[skill]),
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
    assert payload["skills"][0]["gene_slug"] == "contact-to-order"


@pytest.mark.asyncio
async def test_genehub_skills_search_profile_not_found():
    from app.core.exceptions import NotFoundError

    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    body = {
        "jsonrpc": "2.0",
        "id": "call-1",
        "method": "tools/call",
        "params": {
            "name": "genehub.skills.search",
            "arguments": {"profile_id": "missing"},
        },
    }
    db = AsyncMock()

    with patch(
        "app.services.mcp_skill_gateway.genehub_tools.resolve_desktop_profile",
        new=AsyncMock(
            side_effect=NotFoundError("missing", "errors.desktop.profile_not_found")
        ),
    ), patch(
        "app.services.mcp_skill_gateway.genehub_tools._load_user",
        new=AsyncMock(return_value=user),
    ), patch(
        "app.services.mcp_skill_gateway.handler.log_mcp_call",
        new=AsyncMock(),
    ):
        result = await dispatch_authenticated(body, (user, org), db)

    assert result["error"]["data"]["errorCode"] == "GENEHUB_PROFILE_NOT_FOUND"
