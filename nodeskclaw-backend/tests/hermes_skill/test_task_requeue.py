import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.hermes_skill.hermes_task import TaskStatus
from app.services.hermes_skill.hermes_runtime_control_service import HermesRuntimeControlService


@pytest.mark.asyncio
async def test_requeue_from_timeout():
    db = AsyncMock()
    svc = HermesRuntimeControlService(db)
    task = MagicMock()
    task.status = TaskStatus.TIMEOUT
    with patch("app.services.hermes_skill.task_service.TaskService") as ts_cls:
        ts_cls.return_value._append_status_event = AsyncMock()
        await svc.requeue_task(task)
    assert task.status == TaskStatus.QUEUED
