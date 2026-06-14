import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import ForbiddenError
from app.services.mcp_skill_gateway.handler import dispatch_authenticated


@pytest.mark.asyncio
async def test_genehub_skill_forbidden():
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
            "arguments": {"gene_slug": "secret-skill"},
        },
    }
    db = AsyncMock()

    with patch(
        "app.services.mcp_skill_gateway.genehub_tools.genehub_service.get_desktop_skill_detail",
        new=AsyncMock(
            side_effect=ForbiddenError(
                "forbidden",
                "errors.genehub.install_job_permission_denied",
            )
        ),
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

    assert result["error"]["data"]["errorCode"] == "GENEHUB_INSTALL_NOT_ALLOWED"
