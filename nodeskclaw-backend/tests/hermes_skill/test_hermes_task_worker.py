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
    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute.return_value = mock_result
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

    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = [task]
    db.execute.return_value = mock_result

    with patch("app.services.hermes_skill.hermes_task_worker.TaskEventService") as mock_event_svc, \
         patch("app.services.hermes_skill.hermes_task_worker.SkillAuditLogger") as mock_audit:
        mock_event_svc_inst = AsyncMock()
        mock_event_svc.return_value = mock_event_svc_inst
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

    mock_result = AsyncMock()
    mock_result.scalars.return_value.all.return_value = [task]
    db.execute.return_value = mock_result

    with patch("app.services.hermes_skill.hermes_task_worker.TaskEventService") as mock_event_svc:
        mock_event_svc.return_value = AsyncMock()
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
         patch("app.services.hermes_skill.hermes_task_worker.SkillAuditLogger") as mock_audit:
        mock_adapter = AsyncMock()
        mock_adapter.submit_run.side_effect = Exception("Agent unreachable")
        mock_adapter_cls.return_value = mock_adapter
        mock_event_svc.return_value = AsyncMock()
        mock_audit.return_value = AsyncMock()

        await worker._execute_task(db, task)

    assert task.status == TaskStatus.FAILED
    assert task.error_code == "AGENT_UNREACHABLE"
