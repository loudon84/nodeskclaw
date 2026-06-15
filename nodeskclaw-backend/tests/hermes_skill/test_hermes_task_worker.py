import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from app.services.hermes_skill.hermes_task_worker import HermesTaskWorker
from app.models.hermes_skill.hermes_task import TaskStatus, EventType


def test_worker_initial_state():
    worker = HermesTaskWorker()
    assert worker._running is False
    assert len(worker._worker_id) == 12


def test_worker_stop():
    worker = HermesTaskWorker()
    worker._running = True
    worker.stop()
    assert worker._running is False


@pytest.mark.asyncio
async def test_check_timeouts_skips_when_no_running():
    worker = HermesTaskWorker()
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=mock_result)
    await worker._check_timeouts(db)


@pytest.mark.asyncio
async def test_check_timeouts_marks_overdue_task():
    worker = HermesTaskWorker()
    db = AsyncMock()

    task = MagicMock()
    task.id = "task-1"
    task.org_id = "org-1"
    task.status = TaskStatus.RUNNING
    task.run_started_at = datetime.now(timezone.utc) - timedelta(seconds=2000)
    task.timeout_seconds = 900
    task.deleted_at = None

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [task]
    db.execute = AsyncMock(return_value=mock_result)

    with patch("app.services.hermes_skill.hermes_task_worker.TaskEventService") as mock_event_svc, \
         patch("app.services.hermes_skill.hermes_task_worker.TaskService") as mock_task_svc_cls, \
         patch("app.services.hermes_skill.hermes_task_worker.SkillAuditLogger") as mock_audit:
        mock_event_svc_inst = AsyncMock()
        mock_event_svc.return_value = mock_event_svc_inst
        mock_task_svc = AsyncMock()
        mock_task_svc.mark_timeout.side_effect = lambda task, elapsed, **kwargs: setattr(task, "status", TaskStatus.TIMEOUT) or task
        mock_task_svc_cls.return_value = mock_task_svc
        mock_audit.return_value = AsyncMock()

        await worker._check_timeouts(db)

    assert task.status == TaskStatus.TIMEOUT
    assert task.worker_id is None
    assert task.locked_at is None


@pytest.mark.asyncio
async def test_fetch_and_lock_sets_accepted():
    worker = HermesTaskWorker()
    db = AsyncMock()

    task = MagicMock()
    task.id = "task-2"
    task.org_id = "org-1"
    task.status = TaskStatus.QUEUED
    task.deleted_at = None
    task.dispatch_attempts = 0
    task.worker_id = None
    task.locked_at = None

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [task]
    db.execute = AsyncMock(return_value=mock_result)

    with patch("app.services.hermes_skill.hermes_task_worker.TaskService") as mock_task_svc_cls:
        mock_task_svc = AsyncMock()
        mock_task_svc.mark_accepted.side_effect = lambda task, **kwargs: setattr(task, "status", TaskStatus.ACCEPTED) or task
        mock_task_svc_cls.return_value = mock_task_svc
        tasks = await worker._fetch_and_lock(db)

    assert len(tasks) == 1
    assert task.status == TaskStatus.ACCEPTED
    assert task.dispatch_attempts == 1
    assert task.worker_id == worker._worker_id


@pytest.mark.asyncio
async def test_execute_task_agent_unreachable():
    worker = HermesTaskWorker()
    db = AsyncMock()

    task = MagicMock()
    task.id = "task-3"
    task.org_id = "org-1"
    task.skill_id = "skill-1"
    task.tool_name = "test_tool"
    task.agent_id = "agent-1"
    task.status = TaskStatus.ACCEPTED
    task.arguments = {}
    task.deleted_at = None
    task.user_id = "user-1"

    with patch("app.services.hermes_skill.hermes_task_worker.HermesAgentAdapter") as mock_adapter_cls, \
         patch("app.services.hermes_skill.hermes_task_worker.TaskEventService") as mock_event_svc, \
         patch("app.services.hermes_skill.hermes_task_worker.TaskService") as mock_task_svc_cls, \
         patch("app.services.hermes_skill.hermes_task_worker.SkillAuditLogger") as mock_audit:
        mock_adapter = AsyncMock()
        mock_adapter.submit_run.side_effect = Exception("Agent unreachable")
        mock_adapter_cls.return_value = mock_adapter
        mock_event_svc.return_value = AsyncMock()
        mock_task_svc = AsyncMock()
        mock_task_svc.mark_failed.side_effect = lambda task, **kwargs: setattr(task, "status", TaskStatus.FAILED) or setattr(task, "error_code", kwargs.get("error_code")) or task
        mock_task_svc_cls.return_value = mock_task_svc
        mock_audit.return_value = AsyncMock()

        await worker._execute_task(db, task)

    assert task.status == TaskStatus.FAILED
    assert task.error_code == "AGENT_UNREACHABLE"


def _empty_event_stream():
    async def _gen():
        if False:
            yield {}
    return _gen()


def _broken_event_stream():
    async def _gen():
        raise ConnectionError("Stream interrupted")
        yield {}
    return _gen()


@pytest.mark.asyncio
async def test_execute_task_full_lifecycle():
    worker = HermesTaskWorker()
    db = AsyncMock()

    task = MagicMock()
    task.id = "task-lifecycle"
    task.org_id = "org-1"
    task.skill_id = "skill-1"
    task.tool_name = "lifecycle_tool"
    task.agent_id = "agent-1"
    task.status = TaskStatus.ACCEPTED
    task.arguments = {}
    task.deleted_at = None
    task.user_id = "user-1"

    with patch("app.services.hermes_skill.hermes_task_worker.HermesAgentAdapter") as mock_adapter_cls, \
         patch("app.services.hermes_skill.hermes_task_worker.TaskEventService") as mock_event_svc, \
         patch("app.services.hermes_skill.hermes_task_worker.TaskService") as mock_task_svc_cls, \
         patch("app.services.hermes_skill.hermes_task_worker.SkillAuditLogger") as mock_audit:
        mock_adapter = AsyncMock()
        mock_adapter.read_run_events = MagicMock(side_effect=lambda _task: _empty_event_stream())
        mock_adapter.submit_run.return_value = {"run_id": "run-1"}
        mock_adapter_cls.return_value = mock_adapter
        mock_event_svc_inst = AsyncMock()
        mock_event_svc_inst.has_event.return_value = False
        mock_event_svc.return_value = mock_event_svc_inst
        mock_task_svc = AsyncMock()
        mock_task_svc.mark_running.return_value = task
        mock_task_svc.mark_completed.side_effect = lambda t, **kwargs: setattr(t, "status", TaskStatus.COMPLETED) or t
        mock_task_svc_cls.return_value = mock_task_svc
        mock_audit.return_value = AsyncMock()
        db.refresh = AsyncMock()

        with patch.object(worker, "_scan_artifacts", new_callable=AsyncMock):
            await worker._execute_task(db, task)

    assert task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_execute_task_stream_interrupted_marks_failed():
    worker = HermesTaskWorker()
    db = AsyncMock()

    task = MagicMock()
    task.id = "task-stream-int"
    task.org_id = "org-1"
    task.skill_id = "skill-1"
    task.tool_name = "stream_tool"
    task.agent_id = "agent-1"
    task.status = TaskStatus.ACCEPTED
    task.arguments = {}
    task.deleted_at = None
    task.user_id = "user-1"

    with patch("app.services.hermes_skill.hermes_task_worker.HermesAgentAdapter") as mock_adapter_cls, \
         patch("app.services.hermes_skill.hermes_task_worker.TaskEventService") as mock_event_svc, \
         patch("app.services.hermes_skill.hermes_task_worker.TaskService") as mock_task_svc_cls, \
         patch("app.services.hermes_skill.hermes_task_worker.SkillAuditLogger") as mock_audit:
        mock_adapter = AsyncMock()
        mock_adapter.submit_run.return_value = {"run_id": "run-stream"}
        mock_adapter.read_run_events = MagicMock(side_effect=lambda _task: _broken_event_stream())
        mock_adapter.get_run_status.return_value = {"status": "failed"}
        mock_adapter_cls.return_value = mock_adapter
        mock_event_svc_inst = AsyncMock()
        mock_event_svc_inst.has_event.return_value = False
        mock_event_svc.return_value = mock_event_svc_inst
        mock_task_svc = AsyncMock()
        mock_task_svc.mark_running.return_value = task
        mock_task_svc.mark_failed.side_effect = lambda t, **kwargs: setattr(t, "status", TaskStatus.FAILED) or t
        mock_task_svc_cls.return_value = mock_task_svc
        mock_audit.return_value = AsyncMock()
        db.refresh = AsyncMock()

        await worker._execute_task(db, task)

    assert task.status == TaskStatus.FAILED


@pytest.mark.asyncio
async def test_scan_failed_does_not_override_completed():
    worker = HermesTaskWorker()
    db = AsyncMock()

    task = MagicMock()
    task.id = "task-scan-fail"
    task.org_id = "org-1"
    task.skill_id = "skill-1"
    task.tool_name = "scan_fail_tool"
    task.agent_id = "agent-1"
    task.status = TaskStatus.ACCEPTED
    task.arguments = {}
    task.deleted_at = None
    task.user_id = "user-1"

    with patch("app.services.hermes_skill.hermes_task_worker.HermesAgentAdapter") as mock_adapter_cls, \
         patch("app.services.hermes_skill.hermes_task_worker.TaskEventService") as mock_event_svc, \
         patch("app.services.hermes_skill.hermes_task_worker.TaskService") as mock_task_svc_cls, \
         patch("app.services.hermes_skill.hermes_task_worker.SkillAuditLogger") as mock_audit:
        mock_adapter = AsyncMock()
        mock_adapter.submit_run.return_value = {"run_id": "run-scan"}
        mock_adapter.read_run_events = MagicMock(side_effect=lambda _task: _empty_event_stream())
        mock_adapter_cls.return_value = mock_adapter
        mock_event_svc_inst = AsyncMock()
        mock_event_svc_inst.has_event.return_value = False
        mock_event_svc.return_value = mock_event_svc_inst
        mock_task_svc = AsyncMock()
        mock_task_svc.mark_running.return_value = task
        mock_task_svc.mark_completed.side_effect = lambda t, **kwargs: setattr(t, "status", TaskStatus.COMPLETED) or t
        mock_task_svc_cls.return_value = mock_task_svc
        mock_audit.return_value = AsyncMock()
        db.refresh = AsyncMock()

        with patch("app.services.hermes_skill.artifact_service.ArtifactService") as mock_artifact_svc_cls:
            mock_artifact_svc = AsyncMock()
            mock_artifact_svc.scan_and_register.side_effect = Exception("Scan failed")
            mock_artifact_svc_cls.return_value = mock_artifact_svc
            await worker._execute_task(db, task)

    assert task.status == TaskStatus.COMPLETED


@pytest.mark.asyncio
async def test_output_dir_not_exist_scan_empty():
    from app.services.hermes_skill.artifact_service import ArtifactService
    from app.core.config import settings

    db = AsyncMock()
    service = ArtifactService(db)

    task = MagicMock()
    task.id = "task-no-outputs"
    task.org_id = "org-1"
    task.deleted_at = None
    task.workspace_id = None
    task.agent_id = None

    db.get = AsyncMock(return_value=task)

    with patch.object(service, "compute_outputs_dir", new_callable=AsyncMock, return_value=None), \
         patch("app.services.hermes_skill.artifact_service.TaskEventService") as mock_event_svc:
        mock_event_svc.return_value = AsyncMock()
        artifacts = await service.scan_and_register("task-no-outputs", "org-1")

    assert artifacts == []
