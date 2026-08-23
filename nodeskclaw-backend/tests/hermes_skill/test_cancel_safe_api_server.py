from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.models.hermes_skill.hermes_task import EventType, TaskStatus
from app.services.hermes_skill.hermes_task_worker import HermesTaskWorker


@pytest.mark.asyncio
async def test_api_server_discards_result_when_cancel_requested():
    worker = HermesTaskWorker()
    db = AsyncMock()
    db.refresh = AsyncMock()
    task = SimpleNamespace(
        id="task-1",
        org_id="org-1",
        status=TaskStatus.RUNNING,
        arguments={"prompt": "hello"},
        routing_metadata={"output_policy": {}},
        client_context={},
        worker_id="w1",
        locked_at=None,
        dispatch_status="running",
        tool_name="tool.a",
        skill_id="skill.a",
        task_no="TASK-1",
        server_artifacts=None,
        result_summary=None,
        agent_id=None,
    )
    event_service = SimpleNamespace(
        write_event=AsyncMock(),
        has_event=AsyncMock(return_value=True),
    )
    task_service = SimpleNamespace(
        mark_completed=AsyncMock(),
        mark_failed=AsyncMock(),
    )
    audit_logger = SimpleNamespace(log=AsyncMock())

    binding_record = SimpleNamespace(
        id="agent-1",
        gateway_url="http://example.com",
        env_file="/tmp/env",
    )

    with patch(
        "app.services.hermes_skill.hermes_task_worker.execute_runtime_skill_via_api_server",
        new=AsyncMock(return_value="full result text"),
    ):
        with patch(
            "app.services.hermes_skill.hermes_task_worker.HermesDockerBindingService",
            return_value=SimpleNamespace(get_by_profile=AsyncMock(return_value=binding_record)),
        ):
            with patch(
                "app.services.hermes_external.hermes_bound_agent_scope_service.HermesBoundAgentScopeService.assert_dispatchable_instance",
                new=AsyncMock(),
            ):
                await worker._execute_api_server_task(
                    db,
                    task,
                    {
                        "agent_profile": "writer",
                        "hermes_agent_instance_id": "agent-1",
                        "runtime_skill_id": "skill.a",
                    },
                    task_service,
                    event_service,
                    audit_logger,
                )

    task_service.mark_completed.assert_not_called()
    assert task.dispatch_status == "cancelled"
