import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.hermes_skill.hermes_task import TaskStatus
from app.services.hermes_skill.hermes_runtime_control_service import HermesRuntimeControlService


@pytest.mark.asyncio
async def test_worker_pause_flag():
    db = AsyncMock()
    svc = HermesRuntimeControlService(db)
    control = MagicMock()
    control.control_value = "true"
    with patch.object(svc, "_get_control", AsyncMock(return_value=control)):
        assert await svc.is_worker_paused("org-1") is True


@pytest.mark.asyncio
async def test_requeue_task_sets_queued():
    db = AsyncMock()
    svc = HermesRuntimeControlService(db)
    task = MagicMock()
    task.status = TaskStatus.FAILED
    task.id = "task-1"
    task.org_id = "org-1"
    with patch("app.services.hermes_skill.task_service.TaskService") as ts_cls:
        ts_cls.return_value._append_status_event = AsyncMock()
        result = await svc.requeue_task(task, actor_id="user-1")
    assert result.status == TaskStatus.QUEUED
    assert task.worker_id is None
