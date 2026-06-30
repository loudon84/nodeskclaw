import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.hermes_task_worker import HermesTaskWorker
from app.models.hermes_skill.hermes_task import TaskStatus, EventType


def _make_task(
    *,
    route_type="hermes_api_server",
    runtime_invocation="chat_completions",
):
    task = MagicMock()
    task.id = "task-1"
    task.org_id = "org-1"
    task.task_no = "TASK-0001"
    task.tool_name = "hermes_xieyi__customer-profiling"
    task.skill_id = "customer-profiling"
    task.agent_id = "agent-1"
    task.status = TaskStatus.QUEUED
    task.arguments = {"prompt": "test"}
    task.client_context = {"source": "copilot-desktop"}
    task.request_trace_id = "req_test"
    task.routing_metadata = {
        "route_snapshot": {"route_type": route_type},
        "execution_contract": {
            "mode": "async_event",
            "runtime_invocation": runtime_invocation,
            "timeline_provider": "nodeskclaw_task_events",
            "desktop_route_override_allowed": False,
        },
    }
    task.hermes_run_id = None
    task.worker_id = None
    task.locked_at = None
    task.dispatch_status = None
    task.run_started_at = None
    task.deleted_at = None
    return task


@pytest.mark.asyncio
async def test_contract_violation_blocks_v1_runs():
    task = _make_task(route_type="expert_agent_event_stream")
    db = AsyncMock()

    with (
        patch("app.services.hermes_skill.hermes_task_worker.TaskService") as task_svc_cls,
        patch("app.services.hermes_skill.hermes_task_worker.TaskEventService") as event_svc_cls,
        patch("app.services.hermes_skill.hermes_task_worker.SkillAuditLogger") as audit_cls,
    ):
        task_svc = task_svc_cls.return_value
        task_svc.mark_running = AsyncMock()
        task_svc.mark_failed = AsyncMock()
        event_svc = event_svc_cls.return_value
        event_svc.has_event = AsyncMock(return_value=False)
        event_svc.write_event = AsyncMock()
        audit_cls.return_value = AsyncMock()

        worker = HermesTaskWorker()
        await worker._execute_task(db, task)

    task_svc.mark_failed.assert_called_once()
    call_kwargs = task_svc.mark_failed.call_args
    assert call_kwargs.kwargs.get("error_code") == "RUNTIME_ROUTE_CONTRACT_VIOLATION" or \
           call_kwargs[1].get("error_code") == "RUNTIME_ROUTE_CONTRACT_VIOLATION"

    event_svc.write_event.assert_called()
    event_call = event_svc.write_event.call_args
    event_kwargs = event_call.kwargs if event_call.kwargs else {}
    assert event_kwargs.get("event_type") == "task.failed"
    assert event_kwargs.get("payload", {}).get("error_code") == "RUNTIME_ROUTE_CONTRACT_VIOLATION"


@pytest.mark.asyncio
async def test_correct_route_does_not_violate_contract():
    task = _make_task(route_type="hermes_api_server")
    db = AsyncMock()

    with (
        patch("app.services.hermes_skill.hermes_task_worker.TaskService") as task_svc_cls,
        patch("app.services.hermes_skill.hermes_task_worker.TaskEventService") as event_svc_cls,
        patch("app.services.hermes_skill.hermes_task_worker.SkillAuditLogger") as audit_cls,
        patch.object(HermesTaskWorker, "_execute_api_server_task", AsyncMock()) as exec_api,
    ):
        task_svc = task_svc_cls.return_value
        task_svc.mark_running = AsyncMock()
        task_svc.mark_failed = AsyncMock()
        event_svc = event_svc_cls.return_value
        event_svc.has_event = AsyncMock(return_value=False)
        audit_cls.return_value = AsyncMock()

        worker = HermesTaskWorker()
        await worker._execute_task(db, task)

    task_svc.mark_failed.assert_not_called()
    exec_api.assert_called_once()


@pytest.mark.asyncio
async def test_legacy_route_enters_agent_run_stream_with_warning():
    task = _make_task(route_type="expert_agent_event_stream", runtime_invocation=None)
    task.routing_metadata["execution_contract"]["runtime_invocation"] = None
    db = AsyncMock()

    with (
        patch("app.services.hermes_skill.hermes_task_worker.TaskService") as task_svc_cls,
        patch("app.services.hermes_skill.hermes_task_worker.TaskEventService") as event_svc_cls,
        patch("app.services.hermes_skill.hermes_task_worker.SkillAuditLogger") as audit_cls,
        patch.object(HermesTaskWorker, "_execute_agent_run_stream", AsyncMock()) as exec_legacy,
    ):
        task_svc = task_svc_cls.return_value
        task_svc.mark_running = AsyncMock()
        task_svc.mark_failed = AsyncMock()
        event_svc = event_svc_cls.return_value
        event_svc.has_event = AsyncMock(return_value=False)
        audit_cls.return_value = AsyncMock()

        worker = HermesTaskWorker()
        await worker._execute_task(db, task)

    task_svc.mark_failed.assert_not_called()
    exec_legacy.assert_called_once()
