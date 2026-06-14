import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.mcp_skill_gateway.handler import dispatch, dispatch_authenticated
from app.services.mcp_skill_gateway.mcp_tool_registry import build_tool_descriptor, get_tool


def _hermes_tool(name: str) -> dict:
    tool = get_tool(name)
    assert tool is not None
    return build_tool_descriptor(tool)


@pytest.mark.asyncio
async def test_tools_list_returns_hermes_tools_with_annotations():
    from app.services.mcp_skill_gateway.auth import McpAuthContext

    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    body = {"jsonrpc": "2.0", "id": "tools-1", "method": "tools/list", "params": {}}
    db = AsyncMock()

    with patch(
        "app.services.mcp_skill_gateway.handler.resolve_mcp_user",
        return_value=McpAuthContext(user=user, org=org),
    ), patch(
        "app.services.mcp_skill_gateway.handler.McpToolMapper",
    ) as mock_mapper_cls:
        mock_mapper = AsyncMock()
        mock_mapper.list_tools.return_value = []
        mock_mapper_cls.return_value = mock_mapper

        result = await dispatch(body, "Bearer valid-token", db)

    tools = result["result"]["tools"]
    assert len(tools) == 7
    genehub_tools = [t for t in tools if t["name"].startswith("genehub.")]
    assert len(genehub_tools) == 4
    for tool in tools:
        annotations = tool["annotations"]
        assert set(annotations.keys()) == {
            "category",
            "permission",
            "riskLevel",
            "requiresApproval",
            "enabled",
        }
        assert annotations["enabled"] is True
    read_genehub = [t for t in genehub_tools if t["name"] != "genehub.skill.register_to_hermes"]
    assert all(t["annotations"]["permission"] == "read" for t in read_genehub)
    register_tool = next(t for t in genehub_tools if t["name"] == "genehub.skill.register_to_hermes")
    assert register_tool["annotations"]["permission"] == "write"
    assert register_tool["annotations"]["requiresApproval"] is True


@pytest.mark.asyncio
async def test_tools_list_never_returns_null():
    user = MagicMock()
    user.id = "user-1"
    org = MagicMock()
    org.id = "org-1"
    body = {"jsonrpc": "2.0", "id": "tools-1", "method": "tools/list", "params": {}}
    db = AsyncMock()

    with patch(
        "app.services.mcp_skill_gateway.handler.McpToolMapper",
    ) as mock_mapper_cls, patch(
        "app.services.mcp_skill_gateway.handler.list_enabled_tool_descriptors",
        return_value=[_hermes_tool("hermes.instances.list")],
    ):
        mock_mapper = AsyncMock()
        mock_mapper.list_tools.return_value = [{"name": "tool.a"}]
        mock_mapper_cls.return_value = mock_mapper

        result = await dispatch_authenticated(body, (user, org), db)

    assert result["result"]["tools"] == [
        _hermes_tool("hermes.instances.list"),
        {"name": "tool.a"},
    ]


@pytest.mark.asyncio
async def test_tools_list_different_users_can_differ():
    user_a = MagicMock()
    user_a.id = "user-with-grant"
    user_b = MagicMock()
    user_b.id = "user-without-grant"
    org = MagicMock()
    org.id = "org-1"
    body = {"jsonrpc": "2.0", "id": "tools-1", "method": "tools/list", "params": {}}
    db = AsyncMock()

    with patch(
        "app.services.mcp_skill_gateway.handler.McpToolMapper",
    ) as mock_mapper_cls, patch(
        "app.services.mcp_skill_gateway.handler.list_enabled_tool_descriptors",
        return_value=[_hermes_tool("hermes.instances.list")],
    ):
        mock_mapper = AsyncMock()
        mock_mapper.list_tools.side_effect = [
            [{"name": "granted_tool"}],
            [],
        ]
        mock_mapper_cls.return_value = mock_mapper

        granted = await dispatch_authenticated(body, (user_a, org), db)
        denied = await dispatch_authenticated(body, (user_b, org), db)

    assert granted["result"]["tools"][0]["name"] == "hermes.instances.list"
    assert denied["result"]["tools"] == [_hermes_tool("hermes.instances.list")]
