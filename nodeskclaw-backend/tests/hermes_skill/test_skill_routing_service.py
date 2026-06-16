import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.hermes_skill.skill_routing_service import (
    SkillRoutingService,
    ROUTING_REASON_DEFAULT,
    ROUTING_REASON_PRIORITY,
    ROUTING_REASON_EXPLICIT_AGENT,
)
from app.core.exceptions import BadRequestError


def _installation(agent_id: str, skill_id: str = "writer", is_default=False, priority=0, workspace_id=None):
    inst = MagicMock()
    inst.id = f"inst-{agent_id}"
    inst.agent_id = agent_id
    inst.skill_id = skill_id
    inst.profile_id = f"profile-{agent_id}"
    inst.workspace_id = workspace_id
    inst.is_default = is_default
    inst.priority = priority
    inst.status = "installed"
    return inst


@pytest.mark.asyncio
async def test_routing_picks_default_installation():
    db = AsyncMock()
    skill = MagicMock()
    skill.skill_id = "writer"
    skill.title = "Writer"
    installations = [
        _installation("agent-a", priority=10),
        _installation("agent-b", is_default=True, priority=0),
    ]
    svc = SkillRoutingService(db)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(svc, "_get_skill_by_tool_name", AsyncMock(return_value=skill))
        mp.setattr(svc, "_list_installed", AsyncMock(return_value=installations))
        result = await svc.resolve_by_tool_name("writer_tool", "org-1")
    assert result.matched is True
    assert result.agent_id == "agent-b"
    assert result.reason == ROUTING_REASON_DEFAULT


@pytest.mark.asyncio
async def test_routing_explicit_agent():
    db = AsyncMock()
    skill = MagicMock()
    skill.skill_id = "writer"
    installations = [
        _installation("agent-a", is_default=True),
        _installation("agent-b"),
    ]
    svc = SkillRoutingService(db)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(svc, "_get_skill_by_tool_name", AsyncMock(return_value=skill))
        mp.setattr(svc, "_list_installed", AsyncMock(return_value=installations))
        result = await svc.resolve_by_tool_name(
            "writer_tool",
            "org-1",
            routing={"agent_id": "agent-b"},
        )
    assert result.agent_id == "agent-b"
    assert result.reason == ROUTING_REASON_EXPLICIT_AGENT


def test_extract_routing_strips_from_arguments():
    args = {"topic": "hello", "_routing": {"agent_id": "a1"}}
    cleaned, routing = SkillRoutingService.extract_routing(args)
    assert routing == {"agent_id": "a1"}
    assert "_routing" not in cleaned
    assert cleaned["topic"] == "hello"
