from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import BadRequestError
from app.models.expert import Expert
from app.models.expert_skill import ExpertSkill
from app.models.expert_team_skill import ExpertTeamSkill
from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance
from app.services.expert_gateway.expert_catalog_service import ExpertCatalogService
from app.services.expert_gateway.expert_skill_service import ExpertSkillService
from app.services.expert_gateway.expert_team_skill_service import ExpertTeamSkillService


def _agent(**kwargs) -> HermesAgentInstance:
    record = HermesAgentInstance(
        id="agent-1",
        org_id="org-1",
        profile_name="writer",
        container_name="hermes-writer",
        docker_status="running",
        gateway_status="ready",
        gateway_runtime_status="ready",
        mcp_status="callable",
        mcp_gateway_env_synced=False,
        mcp_router_enabled=False,
        mcp_router_last_synced_at=None,
    )
    for key, value in kwargs.items():
        setattr(record, key, value)
    return record


def _expert_skill(**kwargs) -> ExpertSkill:
    skill = ExpertSkill(
        org_id="org-1",
        expert_id="exp-1",
        skill_name="skill-a",
        upstream_tool_name="tool.a",
        is_public=False,
        call_enabled=False,
    )
    for key, value in kwargs.items():
        setattr(skill, key, value)
    return skill


def _team_skill(**kwargs) -> ExpertTeamSkill:
    skill = ExpertTeamSkill(
        org_id="org-1",
        expert_team_id="team-1",
        skill_name="skill-a",
        upstream_tool_name="tool.a",
        is_public=False,
        call_enabled=False,
    )
    for key, value in kwargs.items():
        setattr(skill, key, value)
    return skill


@pytest.mark.parametrize(
    ("service_cls", "skill_factory"),
    [
        (ExpertSkillService, _expert_skill),
        (ExpertTeamSkillService, _team_skill),
    ],
)
def test_apply_flag_rules_public_false(service_cls, skill_factory):
    skill = skill_factory(is_public=True, call_enabled=True)
    skill.is_public = False
    service_cls._apply_flag_rules(skill, False, None)
    assert skill.is_public is False
    assert skill.call_enabled is False


@pytest.mark.parametrize(
    ("service_cls", "skill_factory"),
    [
        (ExpertSkillService, _expert_skill),
        (ExpertTeamSkillService, _team_skill),
    ],
)
def test_apply_flag_rules_call_enabled_true(service_cls, skill_factory):
    skill = skill_factory(is_public=False, call_enabled=False)
    skill.call_enabled = True
    service_cls._apply_flag_rules(skill, None, True)
    assert skill.is_public is True
    assert skill.call_enabled is True


@pytest.mark.parametrize(
    ("service_cls", "skill_factory"),
    [
        (ExpertSkillService, _expert_skill),
        (ExpertTeamSkillService, _team_skill),
    ],
)
def test_apply_flag_rules_public_false_wins(service_cls, skill_factory):
    skill = skill_factory(is_public=True, call_enabled=True)
    skill.is_public = False
    skill.call_enabled = True
    service_cls._apply_flag_rules(skill, False, True)
    assert skill.is_public is False
    assert skill.call_enabled is False


@pytest.mark.asyncio
async def test_validate_publish_ignores_legacy_mcp_gateway():
    expert = Expert(
        org_id="org-1",
        hermes_agent_id="agent-1",
        expert_slug="writer",
        display_name="Writer",
    )
    expert.id = "exp-1"
    svc = ExpertCatalogService(AsyncMock())
    svc._get_agent = AsyncMock(return_value=_agent())
    svc._count_public_skills = AsyncMock(return_value=1)

    await svc.validate_publish("org-1", expert)


@pytest.mark.asyncio
async def test_validate_publish_fails_without_public_skill():
    expert = Expert(
        org_id="org-1",
        hermes_agent_id="agent-1",
        expert_slug="writer",
        display_name="Writer",
    )
    expert.id = "exp-1"
    svc = ExpertCatalogService(AsyncMock())
    svc._get_agent = AsyncMock(return_value=_agent())
    svc._count_public_skills = AsyncMock(return_value=0)

    with pytest.raises(BadRequestError) as exc:
        await svc.validate_publish("org-1", expert)

    issues = exc.value.message_params["issues"]
    assert issues == ["no_public_skill"]


@pytest.mark.asyncio
async def test_validate_publish_collects_missing_meta():
    expert = Expert(
        org_id="org-1",
        hermes_agent_id="agent-1",
        expert_slug="",
        display_name="",
    )
    expert.id = "exp-1"
    svc = ExpertCatalogService(AsyncMock())
    svc._get_agent = AsyncMock(return_value=_agent())
    svc._count_public_skills = AsyncMock(return_value=0)

    with pytest.raises(BadRequestError) as exc:
        await svc.validate_publish("org-1", expert)

    issues = exc.value.message_params["issues"]
    assert "missing_slug" in issues
    assert "missing_display_name" in issues
    assert "no_public_skill" in issues
