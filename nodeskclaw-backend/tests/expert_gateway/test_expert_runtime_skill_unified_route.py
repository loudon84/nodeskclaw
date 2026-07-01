from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.models.expert import Expert
from app.models.expert_invocation_log import ExpertInvocationLog
from app.models.expert_skill import ExpertSkill
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
async def test_start_expert_skill_run_uses_hermes_api_server_route():
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
        routing_metadata=None,
        hermes_run_id=None,
    )
    run_result = RuntimeSkillRunResult(
        task=task,
        sse_token="sse_token",
        structured_content={
            "task_id": "task-1",
            "event_stream": "/api/v1/hermes/tasks/task-1/events?token=sse_token",
            "execution_mode": "async_event",
        },
    )

    service = ExpertRunService(db)
    service._resolve_execution_agent = AsyncMock(return_value=_hermes_agent())
    service.logs.attach_task = AsyncMock()

    captured_request = {}

    async def capture_start(request):
        captured_request["request"] = request
        return run_result

    with patch(
        "app.services.expert_gateway.expert_run_service.RuntimeSkillRunService.start",
        new=AsyncMock(side_effect=capture_start),
    ):
        await service.start_expert_skill_run(
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

    req = captured_request["request"]
    assert req.task_source == "expert_mcp"
    assert req.entrypoint == "expert_mcp_gateway"
    assert req.hermes_agent_instance_id == expert.hermes_agent_id
    assert req.agent_id == "inst-1"
    service.logs.attach_task.assert_awaited_once()


@pytest.mark.asyncio
async def test_resolve_execution_agent_requires_instance_id():
    db = AsyncMock()
    service = ExpertRunService(db)
    service.catalog._get_agent = AsyncMock(return_value=_hermes_agent(instance_id=None))

    from app.core.exceptions import BadRequestError

    with pytest.raises(BadRequestError) as exc_info:
        await service._resolve_execution_agent("org-1", "hermes-agent-1")

    assert exc_info.value.message_key == "errors.expert.agent_instance_not_bound"
