import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus
from app.services.hermes_skill.hermes_task_worker import HermesTaskWorker


@pytest.mark.asyncio
async def test_hermes_task_worker_ignores_non_backend_and_missing_owner():
    db = AsyncMock()
    now = datetime.now(timezone.utc)

    task_agent = HermesTask(
        id="task-1",
        org_id="org-1",
        tool_name="tool_agent",
        status=TaskStatus.QUEUED,
        routing_metadata={"execution_owner": "agent"},
        created_at=now,
        priority=0,
    )
    task_missing = HermesTask(
        id="task-2",
        org_id="org-1",
        tool_name="tool_missing",
        status=TaskStatus.QUEUED,
        routing_metadata={},
        created_at=now,
        priority=0,
    )
    task_backend = HermesTask(
        id="task-3",
        org_id="org-1",
        tool_name="tool_backend",
        status=TaskStatus.QUEUED,
        routing_metadata={"execution_owner": "backend"},
        created_at=now,
        priority=0,
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [task_agent, task_missing, task_backend]
    db.execute.return_value = mock_result

    with patch("app.services.hermes_skill.hermes_task_worker.HermesRuntimeControlService") as control_cls, \
         patch("app.services.hermes_skill.hermes_task_worker.HermesQueuePolicyService") as policy_cls, \
         patch("app.services.hermes_skill.hermes_task_worker.TaskService") as task_svc_cls:

        control_svc = AsyncMock()
        control_svc.is_worker_paused.return_value = False
        control_cls.return_value = control_svc

        policy_svc = AsyncMock()
        policy_svc.can_dispatch.return_value = (True, None)
        policy_cls.return_value = policy_svc

        task_svc = AsyncMock()
        task_svc_cls.return_value = task_svc

        worker = HermesTaskWorker()
        accepted = await worker._fetch_and_lock(db)

        assert len(accepted) == 1
        assert accepted[0].id == "task-3"
        assert accepted[0].tool_name == "tool_backend"
