import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import ForbiddenError
from app.services.mcp_skill_gateway.errors import MCP_TOOL_PROTECTED_RESOURCE
from app.services.mcp_skill_gateway.hermes_docker_tools import HermesDockerToolProvider


@pytest.mark.asyncio
async def test_mcp_uninstall_protected_skill_blocked():
    db = AsyncMock()
    user = MagicMock()
    provider = HermesDockerToolProvider(db)

    with patch(
        "app.services.mcp_skill_gateway.hermes_docker_tools._load_user",
        new=AsyncMock(return_value=user),
    ), patch(
        "app.services.mcp_skill_gateway.hermes_docker_tools.resolve_instance_ref",
        new=AsyncMock(return_value=MagicMock(id="inst-1")),
    ), patch(
        "app.services.mcp_skill_gateway.hermes_docker_tools.get_tool",
        return_value=MagicMock(enabled=True, permission="write"),
    ):
        with pytest.raises(ForbiddenError) as exc:
            await provider.call_tool(
                "hermes.skills.uninstall",
                {"instance_ref": "demo", "skill_name": "hermes-agent"},
                "org-1",
                "user-1",
            )

    assert exc.value.message_key == MCP_TOOL_PROTECTED_RESOURCE
