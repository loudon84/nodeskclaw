from app.services.mcp_skill_gateway.mcp_tool_registry import build_tool_descriptor, get_tool


def test_register_tool_descriptor_uses_desktop_approval_mode():
    tool = get_tool("genehub.skill.register_to_hermes")
    assert tool is not None
    descriptor = build_tool_descriptor(tool)
    annotations = descriptor["annotations"]
    assert annotations["approvalMode"] == "desktop"
    assert annotations["requiresApproval"] is False
    assert annotations["desktopConfirmationRequired"] is True
    assert annotations["authorized"] is True
    assert annotations["grantStatus"] == "desktop_pending"
