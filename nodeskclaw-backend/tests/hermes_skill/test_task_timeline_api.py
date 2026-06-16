import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.hermes_skill.tasks_router import _unwrap_event_payload, _EVENT_TITLES
from app.models.hermes_skill.hermes_task import EventType


def test_unwrap_hermes_payload():
    payload = {
        "source": "hermes",
        "hermes_event_seq": 7,
        "payload": {"delta": "x"},
    }
    unwrapped = _unwrap_event_payload(payload)
    assert unwrapped["delta"] == "x"
    assert unwrapped["hermes_event_seq"] == 7


def test_event_titles_cover_core_types():
    assert _EVENT_TITLES[EventType.TASK_CREATED.value] == "任务创建"
    assert _EVENT_TITLES[EventType.HERMES_RUN_CREATED.value] == "Hermes Run 创建"


@pytest.mark.asyncio
async def test_get_task_timeline_endpoint():
    from app.api.hermes_skill import tasks_router

    task = MagicMock()
    task.id = "task-1"
    task.task_no = "TASK-001"
    from app.models.hermes_skill.hermes_task import TaskStatus
    task.status = TaskStatus.COMPLETED

    event = MagicMock()
    event.event_seq = 0
    event.event_type = EventType.TASK_CREATED
    event.payload = {}
    event.created_at = None

    db = AsyncMock()
    user = MagicMock()
    user.id = "u1"
    org = MagicMock()
    org.id = "org-1"

    with patch.object(tasks_router.TaskService, "get_task", AsyncMock(return_value=task)), \
         patch.object(tasks_router.TaskEventService, "get_events", AsyncMock(return_value=[event])), \
         patch.object(tasks_router.PermissionChecker, "require_permission", AsyncMock()):
        resp = await tasks_router.get_task_timeline("task-1", (user, org), db)

    assert resp["data"]["task_id"] == "task-1"
    assert resp["data"]["items"][0]["title"] == "任务创建"
