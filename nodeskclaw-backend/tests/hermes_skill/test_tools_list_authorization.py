import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.mcp_tool_mapper import McpToolMapper
from app.services.hermes_skill.permission_checker import PermissionChecker


@pytest.mark.asyncio
async def test_admin_list_tools_skips_member_grant_filter():
    db = AsyncMock()
    skill = MagicMock()
    skill.id = "db-1"
    skill.skill_id = "skill-1"
    skill.tool_name = "tool_a"
    skill.title = "Tool"
    skill.name = "tool"
    skill.description = ""
    skill.input_schema = {}
    skill.version = "1"
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [skill]
    db.execute = AsyncMock(return_value=mock_result)

    mapper = McpToolMapper(db)
    with patch.object(PermissionChecker, "has_permission", AsyncMock(return_value=True)), \
         patch.object(PermissionChecker, "get_user_role", AsyncMock(return_value="admin")):
        tools = await mapper.list_tools("org-1", "admin-user")
    assert len(tools) == 1
    assert tools[0]["name"] == "tool_a"
