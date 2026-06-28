from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.models.expert import Expert
from app.models.expert_invocation_log import ExpertInvocationLog
from app.models.expert_skill import ExpertSkill
from app.models.hermes_skill.hermes_task import TaskStatus
from app.services.expert_gateway.expert_run_service import ExpertRunService


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
async def test_start_expert_skill_run_creates_task_with_route_snapshot():
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
        timeout_seconds=900,
        output_policy=None,
        routing_metadata=None,
    )

    with patch.object(
        ExpertRunService,
        "_create_task_run",
        new=AsyncMock(
            return_value=SimpleNamespace(
                task=task,
                log=log,
                event_token="sse_token",
                event_sse_url="/api/v1/hermes/tasks/task-1/events?token=sse_token",
                structured_content={
                    "taskId": "task-1",
                    "taskNo": task.task_no,
                    "eventSseUrl": "/api/v1/hermes/tasks/task-1/events?token=sse_token",
                    "streaming": True,
                },
            )
        ),
    ):
        service = ExpertRunService(db)
        service.catalog.resolve_agent_profile = AsyncMock(return_value="writer")
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

    assert result["result"]["structuredContent"]["taskId"] == "task-1"
    assert result["result"]["structuredContent"]["streaming"] is True
    assert result["result"]["isError"] is False


def test_build_expert_route_snapshot():
    expert = _expert()
    skill = _skill()
    snapshot = ExpertRunService._build_expert_route_snapshot(
        expert=expert,
        skill=skill,
        agent_profile="writer",
        catalog_slug="call-prep",
    )
    assert snapshot["route_type"] == "expert_agent_event_stream"
    assert snapshot["catalog_kind"] == "expert"
    assert snapshot["runtime_skill_id"] == "customer-profiling"
    assert snapshot["expert"]["slug"] == "call-prep"
