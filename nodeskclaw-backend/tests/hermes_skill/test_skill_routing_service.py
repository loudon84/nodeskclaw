import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.hermes_skill.skill_routing_service import (
    SkillRoutingService,
    ROUTING_REASON_DEFAULT,
    ROUTING_REASON_PRIORITY,
    ROUTING_REASON_EXPLICIT_AGENT,
    ROUTING_REASON_RUNTIME_FIXED_DEFAULT,
    ROUTING_REASON_RUNTIME_FIXED_SINGLE,
)
from app.core.exceptions import BadRequestError, NotFoundError


def _installation(agent_id: str, skill_id: str = "writer", is_default=False, priority=0, workspace_id=None, routing_metadata=None):
    inst = MagicMock()
    inst.id = f"inst-{agent_id}"
    inst.agent_id = agent_id
    inst.skill_id = skill_id
    inst.profile_id = f"profile-{agent_id}"
    inst.workspace_id = workspace_id
    inst.is_default = is_default
    inst.priority = priority
    inst.status = "installed"
    inst.routing_metadata = routing_metadata
    return inst


def _runtime_route_metadata():
    return {
        "route_type": "hermes_api_server",
        "force_instance": True,
        "hermes_agent_instance_id": "binding-1",
        "agent_profile": "common-writer",
        "runtime_skill_id": "customer-profiling",
    }


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


@pytest.mark.asyncio
async def test_runtime_fixed_route_picks_default_installation():
    db = AsyncMock()
    skill = MagicMock()
    skill.skill_id = "hermes_common_writer__customer-profiling"
    skill.source_type = "hermes_api_server"
    installations = [
        _installation("agent-a", routing_metadata=_runtime_route_metadata()),
        _installation(
            "agent-b",
            is_default=True,
            routing_metadata=_runtime_route_metadata(),
        ),
    ]
    svc = SkillRoutingService(db)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(svc, "_get_skill_by_tool_name", AsyncMock(return_value=skill))
        mp.setattr(svc, "_list_installed", AsyncMock(return_value=installations))
        result = await svc.resolve_runtime_skill_fixed_route(
            "hermes_common_writer__customer-profiling",
            "org-1",
        )
    assert result.agent_id == "agent-b"
    assert result.reason == ROUTING_REASON_RUNTIME_FIXED_DEFAULT


@pytest.mark.asyncio
async def test_runtime_fixed_route_single_installation():
    db = AsyncMock()
    skill = MagicMock()
    skill.skill_id = "hermes_common_writer__customer-profiling"
    skill.source_type = "hermes_api_server"
    installations = [
        _installation("agent-a", routing_metadata=_runtime_route_metadata()),
    ]
    svc = SkillRoutingService(db)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(svc, "_get_skill_by_tool_name", AsyncMock(return_value=skill))
        mp.setattr(svc, "_list_installed", AsyncMock(return_value=installations))
        result = await svc.resolve_runtime_skill_fixed_route(
            "hermes_common_writer__customer-profiling",
            "org-1",
        )
    assert result.agent_id == "agent-a"
    assert result.reason == ROUTING_REASON_RUNTIME_FIXED_SINGLE


@pytest.mark.asyncio
async def test_runtime_fixed_route_ambiguous_without_default():
    db = AsyncMock()
    skill = MagicMock()
    skill.skill_id = "hermes_common_writer__customer-profiling"
    skill.source_type = "hermes_api_server"
    installations = [
        _installation("agent-a", routing_metadata=_runtime_route_metadata()),
        _installation("agent-b", routing_metadata=_runtime_route_metadata()),
    ]
    svc = SkillRoutingService(db)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(svc, "_get_skill_by_tool_name", AsyncMock(return_value=skill))
        mp.setattr(svc, "_list_installed", AsyncMock(return_value=installations))
        with pytest.raises(BadRequestError) as exc_info:
            await svc.resolve_runtime_skill_fixed_route(
                "hermes_common_writer__customer-profiling",
                "org-1",
            )
    assert exc_info.value.message_key == "errors.skill.installation_ambiguous"


@pytest.mark.asyncio
async def test_runtime_fixed_route_invalid_route_config():
    db = AsyncMock()
    skill = MagicMock()
    skill.skill_id = "hermes_common_writer__customer-profiling"
    skill.source_type = "hermes_api_server"
    installations = [
        _installation("agent-a", is_default=True, routing_metadata=None),
    ]
    svc = SkillRoutingService(db)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(svc, "_get_skill_by_tool_name", AsyncMock(return_value=skill))
        mp.setattr(svc, "_list_installed", AsyncMock(return_value=installations))
        with pytest.raises(BadRequestError) as exc_info:
            await svc.resolve_runtime_skill_fixed_route(
                "hermes_common_writer__customer-profiling",
                "org-1",
            )
    assert exc_info.value.message_key == "errors.skill.route_config_invalid"
