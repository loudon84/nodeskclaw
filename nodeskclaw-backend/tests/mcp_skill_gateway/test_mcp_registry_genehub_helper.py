from app.services.mcp_skill_gateway.mcp_tool_registry import (
    get_tool,
    is_desktop_confirmation_tool,
    is_genehub_registry_tool,
    resolve_approval_mode,
)


def test_is_genehub_registry_tool_matches_genehub_category():
    assert is_genehub_registry_tool("genehub.skills.search") is True
    assert is_genehub_registry_tool("genehub.skill.register_to_hermes") is True
    assert is_genehub_registry_tool("hermes.instances.list") is False


def test_is_desktop_confirmation_tool_matches_register_tool():
    assert is_desktop_confirmation_tool("genehub.skill.register_to_hermes") is True
    assert is_desktop_confirmation_tool("genehub.skills.search") is False


def test_register_tool_uses_desktop_approval_mode():
    tool = get_tool("genehub.skill.register_to_hermes")
    assert tool is not None
    assert resolve_approval_mode(tool) == "desktop"
    assert tool.desktop_confirmation_required is True
    assert tool.requires_approval is False
