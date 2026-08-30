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
    with patch.object(PermissionChecker, "get_user_role", new=AsyncMock(return_value=None)):
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

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [skill]
    db.execute = AsyncMock(return_value=mock_result)

    mapper = McpToolMapper(db)
    with patch.object(PermissionChecker, "has_permission", return_value=True), \
         patch.object(PermissionChecker, "get_user_role", AsyncMock(return_value="admin")), \
         patch.object(mapper, "_skill_to_tool_dict", AsyncMock(return_value={"name": "my_tool", "description": "A test tool"})), \
         patch.object(mapper, "_list_public_connector_tools", AsyncMock(return_value=[{"name": "crm_lookup", "kind": "connector"}])):
        tools = await mapper.list_tools("org-1", "user-1")

    assert len(tools) >= 2
    assert tools[0]["name"] == "my_tool"
    assert tools[1]["name"] == "crm_lookup"


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

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [skill]
    db.execute = AsyncMock(return_value=mock_result)

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

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [skill_a, skill_b]
    db.execute = AsyncMock(return_value=mock_result)

    mapper = McpToolMapper(db)
    with patch.object(PermissionChecker, "has_permission", return_value=True):
        tools = await mapper.list_tools("org-1", "user-1")

    assert len(tools) == 2
    assert all(tool["name"] == "unique_tool" for tool in tools)


@pytest.mark.asyncio
async def test_list_tools_empty_for_non_member():
    db = AsyncMock()
    mapper = McpToolMapper(db)

    with patch.object(PermissionChecker, "has_permission", return_value=False):
        tools = await mapper.list_tools("org-1", "user-outsider")

    assert tools == []


@pytest.mark.asyncio
async def test_skill_to_tool_dict_v11_descriptor():
    db = AsyncMock()
    inst_mock = MagicMock()
    inst_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=inst_mock)
    mapper = McpToolMapper(db)

    skill = MagicMock()
    skill.id = "skill-db-1"
    skill.skill_id = "skill-1"
    skill.tool_name = "chat_skill"
    skill.title = "Chat Skill"
    skill.name = "chat-skill"
    skill.description = "A chat skill"
    skill.version = "1.0.0"
    skill.category = "general"
    skill.source_type = "custom"
    skill.extra_metadata = {"modified_in_working_copy": True}

    published = MagicMock()
    published.id = "release-1"
    published.digest = "digest-12345"
    published.title = "Chat Skill Published"
    published.description = "Published desc"
    published.version = "1.0.0"
    published.category = "general"
    published.input_schema = {"type": "object", "properties": {"msg": {"type": "string"}}}
    published.extra_metadata = {
        "interactionMode": "chat",
        "promptField": "msg",
        "supportsAttachments": True,
        "annotations": {
            "riskLevel": "high",
            "requiresApproval": True,
            "approvalMode": "server",
            "streaming": True,
            "artifacts": False,
        },
    }

    with patch("app.services.hermes_skill.mcp_tool_mapper.SkillReleaseService.get_published_by_skill_db_id", new=AsyncMock(return_value=published)), \
         patch("app.services.hermes_skill.mcp_tool_mapper.HermesSkillAuthorizationService.can_invoke", new=AsyncMock(return_value=True)):
        tool_dict = await mapper._skill_to_tool_dict(skill, "org-1", "user-1")

    assert tool_dict["capabilityKind"] == "skill"
    assert tool_dict["interactionMode"] == "chat"
    assert tool_dict["promptField"] == "msg"
    assert tool_dict["supportsAttachments"] is True
    assert tool_dict["skillReleaseId"] == "release-1"
    assert tool_dict["skillReleaseDigest"] == "digest-12345"
    assert tool_dict["annotations"]["riskLevel"] == "high"
    assert tool_dict["annotations"]["requiresApproval"] is True
    assert tool_dict["requiresApproval"] is True
    assert "modified_in_working_copy" not in tool_dict


@pytest.mark.asyncio
async def test_skill_to_tool_dict_legacy_release_compatibility_mapping():
    db = AsyncMock()
    inst_mock = MagicMock()
    inst_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=inst_mock)
    mapper = McpToolMapper(db)

    skill = MagicMock()
    skill.id = "skill-db-2"
    skill.skill_id = "skill-2"
    skill.tool_name = "legacy_skill"
    skill.title = "Legacy Skill"
    skill.name = "legacy-skill"
    skill.description = "Legacy desc"
    skill.version = "1.0.0"
    skill.category = "general"
    skill.source_type = "custom"
    skill.extra_metadata = {}

    published = MagicMock()
    published.id = "release-legacy"
    published.digest = "digest-legacy"
    published.title = "Legacy"
    published.description = "Legacy"
    published.version = "1.0.0"
    published.category = "general"
    published.input_schema = {"type": "object", "properties": {"prompt": {"type": "string"}}}
    published.extra_metadata = {}

    with patch("app.services.hermes_skill.mcp_tool_mapper.SkillReleaseService.get_published_by_skill_db_id", new=AsyncMock(return_value=published)), \
         patch("app.services.hermes_skill.mcp_tool_mapper.HermesSkillAuthorizationService.can_invoke", new=AsyncMock(return_value=True)):
        tool_dict = await mapper._skill_to_tool_dict(skill, "org-1", "user-1")

    assert tool_dict["capabilityKind"] == "skill"
    assert tool_dict["interactionMode"] == "chat"
    assert tool_dict["promptField"] == "prompt"
    assert tool_dict["supportsAttachments"] is False
    assert tool_dict["skillReleaseId"] == "release-legacy"
    assert tool_dict["skillReleaseDigest"] == "digest-legacy"


@pytest.mark.asyncio
async def test_list_public_connector_tools_v11_descriptor():
    db = AsyncMock()
    mapper = McpToolMapper(db)

    connector_tool = MagicMock()
    connector_tool.tool_name = "crm_tool"
    connector_tool.title = "CRM Tool"
    connector_tool.description = "CRM description"
    connector_tool.input_schema = {"type": "object"}
    connector_tool.extra_metadata = {"requires_approval": False}

    instance = MagicMock()
    instance.placement = "central"

    mock_result = MagicMock()
    mock_result.all.return_value = [(connector_tool, instance)]
    db.execute = AsyncMock(return_value=mock_result)

    tools = await mapper._list_public_connector_tools("org-1")
    assert len(tools) == 1
    tool = tools[0]
    assert tool["name"] == "crm_tool"
    assert tool["capabilityKind"] == "connector"
    assert tool["interactionMode"] == "form"
    assert tool["supportsAttachments"] is False
    assert "annotations" in tool
    assert "skillReleaseId" not in tool
    assert "skillReleaseDigest" not in tool

