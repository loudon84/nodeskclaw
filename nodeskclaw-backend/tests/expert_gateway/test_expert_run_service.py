from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import BadRequestError
from app.models.expert import Expert
from app.models.expert_invocation_log import ExpertInvocationLog
from app.models.expert_skill import ExpertSkill
from app.models.expert_team import ExpertTeam
from app.models.expert_team_skill import ExpertTeamSkill
from app.models.hermes_skill.hermes_agent_instance import HermesAgentInstance
from app.models.hermes_skill.hermes_task import TaskStatus
from app.services.expert_gateway.expert_run_service import ExpertRunService
from app.services.hermes_skill.runtime_skill_run_service import RuntimeSkillRunResult


def _hermes_agent(*, instance_id: str | None = "inst-1") -> HermesAgentInstance:
    return HermesAgentInstance(
        id="hermes-agent-1",
        org_id="org-1",
        instance_id=instance_id,
        profile_name="writer",
        container_name="hermes-writer",
    )


def _expert() -> Expert:
    return Expert(
        id="exp-1",
        org_id="org-1",
        hermes_agent_id="agent-1",
        expert_slug="call-prep",
        display_name="客户研究员",
        published=True,
        enabled=True,
    )


def _skill() -> ExpertSkill:
    return ExpertSkill(
        id="skill-1",
        org_id="org-1",
        expert_id="exp-1",
        skill_name="customer-profiling",
        upstream_tool_name="hermes_writer__customer-profiling",
        is_public=True,
        call_enabled=True,
    )


def _log() -> ExpertInvocationLog:
    return ExpertInvocationLog(
        id="log-1",
        org_id="org-1",
        status="started",
        started_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_start_expert_skill_run_returns_snake_case_structured_content():
    db = AsyncMock()
    expert = _expert()
    skill = _skill()
    log = _log()
    task = SimpleNamespace(
        id="task-1",
        task_no="TASK-org1-abcd1234",
        event_url="/api/v1/hermes/tasks/task-1/events",
        artifact_url="/api/v1/hermes/tasks/task-1/artifacts",
        status=TaskStatus.QUEUED,
    )
    run_result = RuntimeSkillRunResult(
        task=task,
        sse_token="sse_token",
        structured_content={
            "task_id": "task-1",
            "task_no": task.task_no,
            "event_stream": "/api/v1/hermes/tasks/task-1/events?token=sse_token",
            "execution_mode": "async_event",
            "committed": True,
        },
    )

    service = ExpertRunService(db)
    service._resolve_execution_agent = AsyncMock(return_value=_hermes_agent())
    service.logs.attach_task = AsyncMock()

    with patch(
        "app.services.expert_gateway.expert_run_service.RuntimeSkillRunService.start",
        new=AsyncMock(return_value=run_result),
    ):
        result = await service.start_expert_skill_run(
            "org-1",
            "user-1",
            expert,
            skill,
            {"prompt": "研究客户"},
            catalog_slug="call-prep",
            headers={"x-client": "copilot-desktop"},
            log=log,
            jsonrpc_id="1",
        )

    assert result["result"]["structuredContent"]["task_id"] == "task-1"
    assert result["result"]["structuredContent"]["execution_mode"] == "async_event"
    assert result["result"]["isError"] is False


@pytest.mark.asyncio
async def test_resolve_execution_agent_requires_instance_id():
    db = AsyncMock()
    service = ExpertRunService(db)
    service.catalog._get_agent = AsyncMock(return_value=_hermes_agent(instance_id=None))

    with pytest.raises(BadRequestError) as exc_info:
        await service._resolve_execution_agent("org-1", "hermes-agent-1")

    assert exc_info.value.message_key == "errors.expert.agent_instance_not_bound"


@pytest.mark.asyncio
async def test_start_expert_skill_run_uses_instance_id_for_task_agent():
    db = AsyncMock()
    expert = _expert()
    skill = _skill()
    log = _log()
    agent = _hermes_agent(instance_id="instance-uuid-1")
    captured: dict[str, str | None] = {}

    async def capture_start(request):
        captured["agent_id"] = request.agent_id
        captured["agent_profile"] = request.agent_profile
        captured["hermes_agent_instance_id"] = request.hermes_agent_instance_id
        return RuntimeSkillRunResult(
            task=SimpleNamespace(id="task-1", task_no="TASK-1"),
            sse_token="token",
            structured_content={"task_id": "task-1"},
        )

    service = ExpertRunService(db)
    service._resolve_execution_agent = AsyncMock(return_value=agent)
    service.logs.attach_task = AsyncMock()

    with patch(
        "app.services.expert_gateway.expert_run_service.RuntimeSkillRunService.start",
        new=AsyncMock(side_effect=capture_start),
    ):
        await service.start_expert_skill_run(
            "org-1",
            "member-user-1",
            expert,
            skill,
            {"prompt": "研究客户"},
            catalog_slug="call-prep",
            headers={"x-client": "copilot-desktop"},
            log=log,
            jsonrpc_id="1",
        )

    assert captured["agent_id"] == "instance-uuid-1"
    assert captured["agent_profile"] == "writer"
    assert captured["hermes_agent_instance_id"] == expert.hermes_agent_id


@pytest.mark.asyncio
async def test_start_team_skill_run_uses_instance_id_for_task_agent():
    db = AsyncMock()
    team = ExpertTeam(
        id="team-1",
        org_id="org-1",
        team_slug="sales-tianji",
        display_name="销售准备团队",
        hermes_agent_id="hermes-agent-1",
        published=True,
        enabled=True,
    )
    skill = ExpertTeamSkill(
        id="team-skill-1",
        org_id="org-1",
        expert_team_id="team-1",
        skill_name="call-prep",
        upstream_tool_name="tool.a",
        is_public=True,
        call_enabled=True,
    )
    log = _log()
    agent = _hermes_agent(instance_id="instance-uuid-2")
    captured: dict[str, str | None] = {}

    async def capture_start(request):
        captured["agent_id"] = request.agent_id
        captured["catalog_kind"] = request.catalog_kind
        return RuntimeSkillRunResult(
            task=SimpleNamespace(id="task-2", task_no="TASK-2"),
            sse_token="token",
            structured_content={"task_id": "task-2"},
        )

    service = ExpertRunService(db)
    service._resolve_execution_agent = AsyncMock(return_value=agent)
    service.logs.attach_task = AsyncMock()

    with patch(
        "app.services.expert_gateway.expert_run_service.RuntimeSkillRunService.start",
        new=AsyncMock(side_effect=capture_start),
    ):
        await service.start_team_skill_run(
            "org-1",
            "member-user-1",
            team,
            skill,
            {"prompt": "团队任务"},
            catalog_slug="sales-tianji",
            orchestration_mode="upstream_skill",
            headers={"x-client": "copilot-desktop"},
            log=log,
            jsonrpc_id="2",
        )

    assert captured["agent_id"] == "instance-uuid-2"
    assert captured["catalog_kind"] == "expert_team"
