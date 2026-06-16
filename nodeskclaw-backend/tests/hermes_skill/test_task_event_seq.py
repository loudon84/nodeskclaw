import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError

from app.services.hermes_skill.task_event_service import TaskEventService
from app.models.hermes_skill.hermes_task import EventType


@pytest.mark.asyncio
async def test_write_event_assigns_backend_seq_only():
    db = AsyncMock()
    seq_results = [MagicMock(scalar_one_or_none=MagicMock(return_value=2))]
    lock_result = MagicMock()
    db.execute = AsyncMock(side_effect=[lock_result, seq_results[0]])
    db.add = MagicMock()
    db.flush = AsyncMock()

    svc = TaskEventService(db)
    with patch("app.services.hermes_skill.event_bus.EventBus") as mock_bus:
        mock_bus.get_instance.return_value.notify = MagicMock()
        event = await svc.write_event(
            task_id="t1",
            org_id="org-1",
            event_type=EventType.HERMES_RUN_DELTA,
            payload={"delta": "x"},
            source="hermes",
            source_event_seq=99,
        )
    assert event.event_seq == 3
    assert event.payload["hermes_event_seq"] == 99
    assert event.payload["source"] == "hermes"


@pytest.mark.asyncio
async def test_write_event_retries_on_integrity_error():
    db = AsyncMock()
    lock_result = MagicMock()
    seq_result = MagicMock()
    seq_result.scalar_one_or_none.return_value = 1
    db.execute = AsyncMock(side_effect=[lock_result, seq_result, lock_result, seq_result])
    db.add = MagicMock()
    db.flush = AsyncMock(side_effect=[IntegrityError("stmt", {}, Exception()), None])
    db.rollback = AsyncMock()

    svc = TaskEventService(db)
    with patch("app.services.hermes_skill.event_bus.EventBus") as mock_bus, \
         patch("app.services.hermes_skill.task_event_service.asyncio.sleep", AsyncMock()):
        mock_bus.get_instance.return_value.notify = MagicMock()
        event = await svc.write_event(
            task_id="t1",
            org_id="org-1",
            event_type=EventType.TASK_CREATED,
            payload={},
        )
    assert event.event_seq == 2
    assert db.rollback.await_count == 1
