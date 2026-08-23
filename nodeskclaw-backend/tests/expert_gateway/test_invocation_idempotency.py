from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.models.hermes_skill.hermes_task import TaskStatus
from app.schemas.hermes_skill.runtime_skill_run import RuntimeSkillRunResult
from app.services.expert_gateway.expert_run_service import ExpertRunService


@pytest.mark.asyncio
async def test_idempotency_key_reuses_existing_task():
    db = AsyncMock()
    service = ExpertRunService(db)
    existing_task = SimpleNamespace(
        id="task-existing",
        task_no="TASK-EXISTING",
        event_url="/events",
        artifact_url="/artifacts",
        status=TaskStatus.QUEUED,
        output_policy={"artifact_mode": "pull_only"},
    )
    run_result = RuntimeSkillRunResult(
        task=existing_task,
        sse_token="tok",
        structured_content={"task_id": "task-existing", "committed": True},
    )

    with patch(
        "app.services.expert_gateway.expert_run_service.RuntimeSkillRunService.start",
        new=AsyncMock(return_value=run_result),
    ) as mock_start:
        await service._start_runtime_skill_run(
            org_id="org-1",
            user_id="user-1",
            skill=SimpleNamespace(
                upstream_tool_name="tool.a",
                skill_name="customer-profiling",
            ),
            agent=SimpleNamespace(id="agent-1", instance_id="inst-1"),
            agent_profile="writer",
            arguments={"prompt": "hello"},
            client_context={},
            output_policy={"artifact_mode": "pull_only"},
            log=SimpleNamespace(id="log-1"),
            catalog_kind="expert",
            catalog_slug="call-prep",
            extra_route_snapshot={},
            headers={"X-Idempotency-Key": "idem-1"},
        )

    request = mock_start.await_args.args[0]
    assert request.idempotency_key == "idem-1"
    assert request.catalog_slug == "call-prep"


@pytest.mark.asyncio
async def test_runtime_skill_run_returns_existing_task_without_create():
    from app.services.hermes_skill.runtime_skill_run_service import RuntimeSkillRunService
    from app.schemas.hermes_skill.runtime_skill_run import StartRuntimeSkillRunRequest

    db = AsyncMock()
    existing = SimpleNamespace(
        id="task-existing",
        task_no="TASK-1",
        status=TaskStatus.QUEUED,
        event_url="/events",
        artifact_url="/artifacts",
        server_artifacts=[],
        output_policy={"artifact_mode": "pull_only"},
    )
    service = RuntimeSkillRunService(db)
    service._finalize_run = AsyncMock(return_value=RuntimeSkillRunResult(task=existing, sse_token="t", structured_content={}))

    with patch(
        "app.services.hermes_skill.runtime_skill_run_service.TaskService.find_idempotent_task",
        new=AsyncMock(return_value=existing),
    ):
        request = StartRuntimeSkillRunRequest(
            org_id="org-1",
            user_id="user-1",
            tool_name="tool.a",
            runtime_skill_id="skill.a",
            agent_profile="writer",
            hermes_agent_instance_id="agent-1",
            agent_id="inst-1",
            arguments={"prompt": "hello"},
            client_context={},
            output_policy={"artifact_mode": "pull_only"},
            task_source="expert_mcp",
            skill_id="skill.a",
            catalog_slug="call-prep",
            idempotency_key="idem-1",
        )
        result = await service.start(request)

    assert result.task.id == "task-existing"
    service._finalize_run.assert_awaited_once()
