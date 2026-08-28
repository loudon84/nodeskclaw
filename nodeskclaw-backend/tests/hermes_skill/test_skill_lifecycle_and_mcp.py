import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.hermes_skill.skill import HermesSkill
from app.models.hermes_skill.skill_release import HermesSkillRelease, SkillReleaseStatus
from app.schemas.hermes_skill.skill import (
    SkillCreate,
    SkillUpdate,
    SkillForkBody,
    SkillValidateRequest,
)
from app.services.hermes_skill.mcp_tool_mapper import McpToolMapper
from app.services.hermes_skill.skill_installer import SkillInstaller


@pytest.mark.asyncio
async def test_mcp_tool_mapper_strips_physical_identities():
    db = AsyncMock()
    mapper = McpToolMapper(db)

    # Mock connector query
    connector_tool = MagicMock()
    connector_tool.tool_name = "test_connector"
    connector_tool.title = "Test Connector"
    connector_tool.description = "A connector tool"
    connector_tool.input_schema = {}
    connector_tool.extra_metadata = {"requires_approval": False}

    instance = MagicMock()
    instance.placement = "edge"
    instance.edge_node_id = "node-secret-123"
    instance.is_active = True

    mock_res = MagicMock()
    mock_res.all.return_value = [(connector_tool, instance)]
    db.execute = AsyncMock(return_value=mock_res)

    with patch("app.services.hermes_skill.mcp_tool_mapper.is_edge_node_online", return_value=True):
        tools = await mapper._list_public_connector_tools("org-1")

    assert len(tools) == 1
    tool = tools[0]
    assert tool["name"] == "test_connector"
    assert tool["sourceType"] == "connector"
    # Ensure no leaked internal physical IDs
    assert "node_id" not in tool
    assert "edge_node_id" not in tool
    assert "agent_id" not in tool
    assert "placement" not in tool


@pytest.mark.asyncio
async def test_skill_installer_is_desired_only_zero_fs():
    db = AsyncMock()
    skill = HermesSkill(
        id="skill-db-1",
        org_id="org-1",
        skill_id="test.skill",
        name="Test Skill",
        version="1.0.0",
        is_active=True,
    )
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = skill
    db.execute = AsyncMock(return_value=mock_res)

    installer = SkillInstaller(db)
    inst = await installer.install(
        skill_id="test.skill",
        agent_id="agent-1",
        org_id="org-1",
    )
    assert inst.status == "installed"
    assert inst.skill_id == "test.skill"
    assert inst.agent_id == "agent-1"

    # Uninstall
    db.get = AsyncMock(return_value=inst)
    uninst = await installer.uninstall(inst.id, "org-1")
    assert uninst.status == "removed"
