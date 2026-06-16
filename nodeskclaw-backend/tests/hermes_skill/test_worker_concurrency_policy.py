import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.hermes_skill.hermes_task import TaskStatus
from app.services.hermes_skill.hermes_task_worker import HermesTaskWorker


@pytest.mark.asyncio
async def test_fetch_and_lock_skips_paused_org():
    db = AsyncMock()
    worker = HermesTaskWorker()
    task = MagicMock()
    task.org_id = "org-1"
    task.not_before = None
    task.status = TaskStatus.QUEUED
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [task]
    db.execute = AsyncMock(return_value=mock_result)
    db.flush = AsyncMock()

    with patch("app.services.hermes_skill.hermes_task_worker.HermesRuntimeControlService") as ctrl_cls, \
         patch("app.services.hermes_skill.hermes_task_worker.HermesQueuePolicyService") as policy_cls:
        ctrl_cls.return_value.is_worker_paused = AsyncMock(return_value=True)
        policy_cls.return_value.can_dispatch = AsyncMock(return_value=(True, None))
        accepted = await worker._fetch_and_lock(db)
    assert accepted == []
