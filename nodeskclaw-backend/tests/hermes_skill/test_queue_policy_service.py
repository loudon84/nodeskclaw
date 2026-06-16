import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.hermes_skill.hermes_queue_policy_service import HermesQueuePolicyService


@pytest.mark.asyncio
async def test_can_enqueue_rejects_when_queue_paused():
    db = AsyncMock()
    svc = HermesQueuePolicyService(db)
    with patch("app.services.hermes_skill.hermes_queue_policy_service.HermesRuntimeControlService") as ctrl_cls:
        ctrl_cls.return_value.is_queue_paused = AsyncMock(return_value=True)
        ok, key = await svc.can_enqueue("org-1", "user-1", "agent-1", "skill-1")
    assert ok is False
    assert key == "errors.hermes.queue_paused"


@pytest.mark.asyncio
async def test_can_dispatch_respects_not_before():
    db = AsyncMock()
    svc = HermesQueuePolicyService(db)
    task = MagicMock()
    task.org_id = "org-1"
    task.not_before = __import__("datetime").datetime(2099, 1, 1, tzinfo=__import__("datetime").timezone.utc)
    task.agent_id = None
    with patch("app.services.hermes_skill.hermes_queue_policy_service.HermesRuntimeControlService") as ctrl_cls:
        ctrl_cls.return_value.is_queue_paused = AsyncMock(return_value=False)
        ctrl_cls.return_value.is_worker_paused = AsyncMock(return_value=False)
        ok, reason = await svc.can_dispatch(task)
    assert ok is False
    assert reason == "not_before"
