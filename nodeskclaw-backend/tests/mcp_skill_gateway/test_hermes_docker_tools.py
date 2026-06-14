import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import ForbiddenError
from app.services.mcp_skill_gateway.errors import MCP_TOOL_DISABLED
from app.services.mcp_skill_gateway.hermes_docker_tools import (
    HermesDockerToolProvider,
    list_tools,
)
from app.services.mcp_skill_gateway.hermes_instance_resolver import resolve_instance_ref


def test_list_tools_includes_three_read_tools_with_annotations():
    tools = list_tools()
    names = {tool["name"] for tool in tools}

    assert names == {
        "hermes.instances.list",
        "hermes.instance.status",
        "hermes.skills.list",
    }
    for tool in tools:
        assert tool["annotations"]["enabled"] is True
        assert tool["annotations"]["permission"] == "read"


@pytest.mark.asyncio
async def test_resolve_instance_ref_by_profile():
    instance = MagicMock()
    instance.id = "inst-1"
    instance.slug = "demo-profile"
    instance.name = "demo-profile"
    instance.advanced_config = '{"profile": "demo-profile", "external_container_name": "hermes-demo-profile"}'
    user = MagicMock()
    user.id = "user-1"
    db = AsyncMock()

    with patch(
        "app.services.mcp_skill_gateway.hermes_instance_resolver.list_external_docker_instances",
        return_value=[instance],
    ), patch(
        "app.services.mcp_skill_gateway.hermes_instance_resolver.instance_member_service.check_instance_access",
        return_value=None,
    ):
        resolved = await resolve_instance_ref("demo-profile", "org-1", user, db)

    assert resolved.id == "inst-1"


@pytest.mark.asyncio
async def test_call_tool_rejects_hermes_write_tools():
    provider = HermesDockerToolProvider(AsyncMock())

    with pytest.raises(ForbiddenError) as exc_info:
        await provider.call_tool("hermes.skills.install_builtin", {}, "org-1", "user-1")

    assert exc_info.value.message_key == MCP_TOOL_DISABLED
