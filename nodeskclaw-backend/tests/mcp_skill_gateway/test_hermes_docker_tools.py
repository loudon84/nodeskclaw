import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.exceptions import BadRequestError
from app.services.mcp_skill_gateway.errors import MCP_INVALID_ARGUMENTS
from app.services.mcp_skill_gateway.hermes_docker_tools import (
    HermesDockerToolProvider,
    list_tools,
)
from app.services.mcp_skill_gateway.hermes_instance_resolver import resolve_instance_ref


def test_list_tools_includes_read_and_write_tools_with_annotations():
    tools = list_tools()
    names = {tool["name"] for tool in tools}

    assert names == {
        "hermes.instances.list",
        "hermes.instance.status",
        "hermes.skills.list",
        "hermes.skills.install_builtin",
        "hermes.skills.uninstall",
        "hermes.instance.restart",
    }
    read_tools = [tool for tool in tools if tool["annotations"]["permission"] == "read"]
    write_tools = [tool for tool in tools if tool["annotations"]["permission"] in ("write", "admin")]
    assert len(read_tools) == 3
    assert len(write_tools) == 3
    for tool in write_tools:
        assert tool["annotations"]["requiresApproval"] is True
        assert tool["annotations"]["approvalMode"] == "server"


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
async def test_call_tool_write_requires_arguments():
    provider = HermesDockerToolProvider(AsyncMock())
    user = MagicMock()

    with patch(
        "app.services.mcp_skill_gateway.hermes_docker_tools._load_user",
        new=AsyncMock(return_value=user),
    ), patch(
        "app.services.mcp_skill_gateway.hermes_docker_tools.get_tool",
        return_value=MagicMock(enabled=True, permission="write"),
    ):
        with pytest.raises(BadRequestError) as exc_info:
            await provider.call_tool("hermes.skills.install_builtin", {}, "org-1", "user-1")

    assert exc_info.value.message_key == MCP_INVALID_ARGUMENTS
