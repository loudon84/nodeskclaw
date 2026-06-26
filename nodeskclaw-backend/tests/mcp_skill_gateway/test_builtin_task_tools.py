from unittest.mock import patch

from app.services.mcp_skill_gateway.builtin_task_tools import (
    BUILTIN_TASK_TOOL_NAMES,
    is_builtin_task_tool,
    list_builtin_task_tool_descriptors,
)


def test_is_builtin_task_tool():
    assert is_builtin_task_tool("nodeskclaw_task_result") is True
    assert is_builtin_task_tool("hermes_common_writer__customer-profiling") is False


def test_list_builtin_task_tool_descriptors_includes_core_tools():
    with patch("app.services.mcp_skill_gateway.builtin_task_tools.settings") as mock_settings:
        mock_settings.MCP_TASK_TOOLS_ENABLED = True
        mock_settings.MCP_TASK_WAIT_ENABLED = True
        tools = list_builtin_task_tool_descriptors()
    names = {tool["name"] for tool in tools}
    assert "nodeskclaw_task_timeline" in names
    assert "nodeskclaw_task_result" in names
    assert "nodeskclaw_task_artifacts" in names
    assert "nodeskclaw_artifact_preview" in names
    assert "nodeskclaw_artifact_download_info" in names
    assert "nodeskclaw_task_wait" in names
    assert names.issubset(BUILTIN_TASK_TOOL_NAMES)


def test_list_builtin_task_tool_descriptors_respects_wait_flag():
    with patch("app.services.mcp_skill_gateway.builtin_task_tools.settings") as mock_settings:
        mock_settings.MCP_TASK_TOOLS_ENABLED = True
        mock_settings.MCP_TASK_WAIT_ENABLED = False
        tools = list_builtin_task_tool_descriptors()
    names = {tool["name"] for tool in tools}
    assert "nodeskclaw_task_wait" not in names
    assert "nodeskclaw_task_result" in names


def test_list_builtin_task_tool_descriptors_disabled():
    with patch("app.services.mcp_skill_gateway.builtin_task_tools.settings") as mock_settings:
        mock_settings.MCP_TASK_TOOLS_ENABLED = False
        mock_settings.MCP_TASK_WAIT_ENABLED = True
        assert list_builtin_task_tool_descriptors() == []
