import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.hermes_skill.hermes_task import EventType
from app.services.hermes_skill.task_event_service import TaskEventService


@pytest.mark.asyncio
async def test_get_events_start_after_seq():
    db = AsyncMock()
    service = TaskEventService(db)

    event_a = MagicMock(event_seq=1)
    event_b = MagicMock(event_seq=2)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [event_b]
    db.execute.return_value = mock_result

    events = await service.get_events("task-1", "org-1", start_after_seq=1)
    assert events == [event_b]


@pytest.mark.asyncio
async def test_has_event_returns_true_when_exists():
    db = AsyncMock()
    service = TaskEventService(db)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = "event-id"
    db.execute.return_value = mock_result

    assert await service.has_event("task-1", EventType.TASK_ACCEPTED) is True
