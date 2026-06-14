import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.mcp_skill_gateway.hermes_docker_tools import (
    HermesDockerToolProvider,
    list_tools,
    resolve_instance_ref,
)


def test_list_tools_includes_three_read_tools():
    tools = list_tools()
    names = {tool["name"] for tool in tools}

    assert names == {
        "hermes.instances.list",
        "hermes.instance.status",
        "hermes.skills.list",
    }


@pytest.mark.asyncio
async def test_resolve_instance_ref_by_profile():
    instance = MagicMock()
    instance.id = "inst-1"
    instance.slug = "zhang-zhen"
    instance.name = "zhang-zhen"
    instance.advanced_config = '{"profile": "zhang-zhen", "external_container_name": "hermes-zhang-zhen"}'
    db = AsyncMock()

    with patch(
        "app.services.mcp_skill_gateway.hermes_docker_tools._list_external_docker_instances",
        return_value=[instance],
    ):
        resolved = await resolve_instance_ref("zhang-zhen", "org-1", db)

    assert resolved.id == "inst-1"


@pytest.mark.asyncio
async def test_call_tool_rejects_genehub_tools():
    provider = HermesDockerToolProvider(AsyncMock())

    with pytest.raises(Exception) as exc_info:
        await provider.call_tool("genehub.skills.search", {"query": "x"}, "org-1", "user-1")

    assert exc_info.value.message_key == "MCP_NOT_IMPLEMENTED"
