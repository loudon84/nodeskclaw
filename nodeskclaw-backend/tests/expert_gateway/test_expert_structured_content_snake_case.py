from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.models.expert import Expert
from app.models.expert_invocation_log import ExpertInvocationLog
from app.models.expert_skill import ExpertSkill
from app.models.hermes_skill.hermes_task import TaskStatus
from app.services.expert_gateway.expert_run_service import ExpertRunService
from app.services.hermes_skill.runtime_skill_run_service import RuntimeSkillRunResult


def _run_result() -> RuntimeSkillRunResult:
    task = SimpleNamespace(
        id="task-1",
        task_no="TASK-org1-abcd1234",
        event_url="/api/v1/hermes/tasks/task-1/events",
        artifact_url="/api/v1/hermes/tasks/task-1/artifacts",
        status=TaskStatus.QUEUED,
    )
    return RuntimeSkillRunResult(
        task=task,
        sse_token="sse_token",
        structured_content={
            "task_id": "task-1",
            "task_no": task.task_no,
            "status": "running",
            "execution_mode": "async_event",
            "event_stream": "/api/v1/hermes/tasks/task-1/events?token=sse_token",
            "event_url": task.event_url,
            "artifact_url": task.artifact_url,
            "result_url": "/api/v1/hermes/tasks/task-1/result",
            "committed": True,
            "entrypoint": "expert_mcp_gateway",
            "task_source": "expert_mcp",
            "catalog_kind": "expert",
            "catalog_slug": "call-prep",
            "skill_name": "customer-profiling",
            "invocation_id": "log-1",
        },
    )


@pytest.mark.asyncio
async def test_expert_structured_content_is_snake_case():
    db = AsyncMock()
    expert = Expert(
        id="exp-1",
        org_id="org-1",
        hermes_agent_id="agent-1",
        expert_slug="call-prep",
        display_name="客户研究员",
        published=True,
        enabled=True,
    )
    skill = ExpertSkill(
        id="skill-1",
        org_id="org-1",
        expert_id="exp-1",
        skill_name="customer-profiling",
        upstream_tool_name="hermes_writer__customer-profiling",
        is_public=True,
        call_enabled=True,
    )
    log = ExpertInvocationLog(
        id="log-1",
        org_id="org-1",
        status="started",
        started_at=datetime.now(timezone.utc),
    )

    service = ExpertRunService(db)
    service._resolve_execution_agent = AsyncMock(
        return_value=SimpleNamespace(
            id="hermes-agent-1",
            instance_id="inst-1",
            profile_name="writer",
        )
    )
    service.logs.attach_task = AsyncMock()

    with patch(
        "app.services.expert_gateway.expert_run_service.RuntimeSkillRunService.start",
        new=AsyncMock(return_value=_run_result()),
    ):
        result = await service.start_expert_skill_run(
            "org-1",
            "user-1",
            expert,
            skill,
            {"prompt": "研究客户"},
            catalog_slug="call-prep",
            log=log,
            jsonrpc_id="1",
        )

    structured = result["result"]["structuredContent"]
    assert structured["task_id"] == "task-1"
    assert structured["event_stream"].startswith("/api/v1/hermes/tasks/")
    assert structured["result_url"] == "/api/v1/hermes/tasks/task-1/result"
    assert structured["invocation_id"] == "log-1"
    assert structured["execution_mode"] == "async_event"
    assert "taskId" not in structured
    assert "eventSseUrl" not in structured
    assert "invocationId" not in structured
    assert "orchestrationMode" not in structured
