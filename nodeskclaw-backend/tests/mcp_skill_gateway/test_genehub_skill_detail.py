import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.genehub import GeneHubManifestPreview, GeneHubSkillPermissions, McpGeneHubSkillDetail
from app.services.mcp_skill_gateway.handler import dispatch_authenticated


@pytest.mark.asyncio
async def test_genehub_skill_detail_returns_manifest_preview():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    body = {
        "jsonrpc": "2.0",
        "id": "call-1",
        "method": "tools/call",
        "params": {
            "name": "genehub.skill.detail",
            "arguments": {"gene_slug": "contact-to-order"},
        },
    }
    db = AsyncMock()
    detail = McpGeneHubSkillDetail(
        gene_slug="contact-to-order",
        gene_version="1.0.0",
        skill_name="contact-to-order",
        display_name="Contact To Order",
        installable=True,
        permissions=GeneHubSkillPermissions(can_install=True),
        manifest_preview=GeneHubManifestPreview(
            has_skill=True,
            file_count=3,
            has_scripts=False,
            requires_signature=True,
        ),
    )

    with patch(
        "app.services.mcp_skill_gateway.genehub_tools.genehub_service.get_desktop_skill_detail",
        new=AsyncMock(return_value=detail),
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
    assert payload["skill"]["manifest_preview"]["file_count"] == 3
    assert "bundle" not in payload["skill"]
