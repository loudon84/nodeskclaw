from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.hermes_skill.hermes_task import EventType, TaskStatus
from app.services.hermes_skill.task_event_publisher import TaskEventPublisher
from app.services.hermes_skill.task_service import TaskService


@pytest.mark.asyncio
async def test_mark_completed_is_idempotent_for_terminal_status():
    db = AsyncMock()
    service = TaskService(db)
    task = SimpleNamespace(
        id="task-1",
        org_id="org-1",
        status=TaskStatus.CANCELLED,
        result_summary=None,
        result_content=None,
        completed_at=None,
    )
    result = await service.mark_completed(task, result_summary="ignored", result_content="ignored")
    assert result.status == TaskStatus.CANCELLED


@pytest.mark.asyncio
async def test_publish_completed_with_result_skips_duplicate_event():
    db = AsyncMock()
    publisher = TaskEventPublisher(db)
    publisher._events.has_event = AsyncMock(return_value=True)
    publisher.publish = AsyncMock()
    result = await publisher.publish_completed_with_result("task-1", "org-1")
    assert result is None
    publisher.publish.assert_not_called()
