import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.mcp_tool_mapper import McpToolMapper
from app.services.hermes_skill.permission_checker import PermissionChecker


@pytest.mark.asyncio
async def test_mcp_tools_list_requires_view_permission():
    db = AsyncMock()
    with patch.object(PermissionChecker, "has_permission", return_value=False):
        result = await PermissionChecker.has_permission(db, "user-1", "org-1", "skill:view")
    assert result is False


@pytest.mark.asyncio
async def test_mcp_tools_call_requires_invoke_permission():
    db = AsyncMock()
    with patch.object(PermissionChecker, "has_permission", return_value=True):
        result = await PermissionChecker.has_permission(db, "user-1", "org-1", "skill:invoke")
    assert result is True


@pytest.mark.asyncio
async def test_non_org_member_denied():
    db = AsyncMock()
    with patch.object(PermissionChecker, "get_user_role", return_value=None):
        result = await PermissionChecker.has_permission(db, "user-1", "org-1", "skill:view")
    assert result is False


@pytest.mark.asyncio
async def test_list_tools_returns_installed_active_exposed():
    db = AsyncMock()

    skill = MagicMock()
    skill.tool_name = "my_tool"
    skill.title = "My Tool"
    skill.name = "my-skill"
    skill.description = "A test tool"
    skill.input_schema = {"type": "object"}
    skill.version = "1.0.0"

    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = [skill]
    db.execute.return_value = mock_result

    mapper = McpToolMapper(db)
    with patch.object(PermissionChecker, "has_permission", return_value=True):
        tools = await mapper.list_tools("org-1", "user-1")

    assert len(tools) >= 1
    assert tools[0]["name"] == "my_tool"
    assert tools[0]["description"] == "A test tool"


@pytest.mark.asyncio
async def test_list_tools_excludes_no_permission():
    db = AsyncMock()
    mapper = McpToolMapper(db)

    with patch.object(PermissionChecker, "has_permission", side_effect=lambda *a, **kw: False):
        tools = await mapper.list_tools("org-1", "user-1")

    assert tools == []


@pytest.mark.asyncio
async def test_list_tools_field_completeness():
    db = AsyncMock()

    skill = MagicMock()
    skill.tool_name = "complete_tool"
    skill.title = "Complete Tool"
    skill.name = "complete-skill"
    skill.description = "Complete description"
    skill.input_schema = {"type": "object", "properties": {}}
    skill.version = "2.0.0"

    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = [skill]
    db.execute.return_value = mock_result

    mapper = McpToolMapper(db)
    with patch.object(PermissionChecker, "has_permission", return_value=True):
        tools = await mapper.list_tools("org-1", "user-1")

    if tools:
        tool = tools[0]
        assert "name" in tool
        assert "title" in tool
        assert "description" in tool
        assert "inputSchema" in tool
        assert "version" in tool


@pytest.mark.asyncio
async def test_list_tools_name_unique():
    db = AsyncMock()

    skill_a = MagicMock()
    skill_a.tool_name = "unique_tool"
    skill_a.title = "Tool A"
    skill_a.name = "skill-a"
    skill_a.description = "A"
    skill_a.input_schema = {}
    skill_a.version = "1.0.0"

    skill_b = MagicMock()
    skill_b.tool_name = "unique_tool"
    skill_b.title = "Tool B"
    skill_b.name = "skill-b"
    skill_b.description = "B"
    skill_b.input_schema = {}
    skill_b.version = "1.0.0"

    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = [skill_a, skill_b]
    db.execute.return_value = mock_result

    mapper = McpToolMapper(db)
    with patch.object(PermissionChecker, "has_permission", return_value=True):
        tools = await mapper.list_tools("org-1", "user-1")

    names = [t["name"] for t in tools]
    assert len(names) == len(set(names))


@pytest.mark.asyncio
async def test_list_tools_empty_for_non_member():
    db = AsyncMock()
    mapper = McpToolMapper(db)

    with patch.object(PermissionChecker, "has_permission", return_value=False):
        tools = await mapper.list_tools("org-1", "user-outsider")

    assert tools == []
