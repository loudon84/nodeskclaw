import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hermes_skill.hermes_task import HermesTask, HermesTaskEvent, EventType

logger = logging.getLogger(__name__)

_MAX_EVENT_WRITE_RETRIES = 3


class TaskEventService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def has_event(self, task_id: str, event_type: EventType) -> bool:
        result = await self.db.execute(
            select(HermesTaskEvent.id).where(
                HermesTaskEvent.task_id == task_id,
                HermesTaskEvent.event_type == event_type,
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def write_event(
        self,
        task_id: str,
        org_id: str,
        event_type: EventType,
        payload: dict | None = None,
        source: str = "backend",
        source_event_seq: int | None = None,
    ) -> HermesTaskEvent:
        merged_payload = dict(payload or {})
        if source != "backend":
            merged_payload = {
                "source": source,
                "hermes_event_seq": source_event_seq,
                "payload": merged_payload,
            }
        elif source_event_seq is not None:
            merged_payload["hermes_event_seq"] = source_event_seq

        last_exc: Exception | None = None
        for attempt in range(_MAX_EVENT_WRITE_RETRIES):
            try:
                return await self._write_event_once(
                    task_id=task_id,
                    org_id=org_id,
                    event_type=event_type,
                    payload=merged_payload,
                )
            except IntegrityError as exc:
                last_exc = exc
                await self.db.rollback()
                logger.warning(
                    "event_seq conflict task=%s attempt=%s: %s",
                    task_id,
                    attempt + 1,
                    exc,
                )
                await asyncio.sleep(0.05 * (attempt + 1))
        if last_exc:
            logger.error("write_event failed after retries task=%s", task_id)
        raise last_exc or RuntimeError("write_event failed")

    async def _write_event_once(
        self,
        task_id: str,
        org_id: str,
        event_type: EventType,
        payload: dict | None = None,
    ) -> HermesTaskEvent:
        await self.db.execute(
            select(HermesTask.id).where(
                HermesTask.id == task_id,
                HermesTask.org_id == org_id,
            ).with_for_update()
        )
        max_seq_result = await self.db.execute(
            select(HermesTaskEvent.event_seq).where(
                HermesTaskEvent.task_id == task_id,
            ).order_by(HermesTaskEvent.event_seq.desc()).limit(1)
        )
        max_seq = max_seq_result.scalar_one_or_none() or 0
        event_seq = max_seq + 1

        event = HermesTaskEvent(
            id=str(uuid.uuid4()),
            org_id=org_id,
            task_id=task_id,
            event_type=event_type,
            event_seq=event_seq,
            payload=payload,
        )
        self.db.add(event)
        await self.db.flush()

        from app.services.hermes_skill.event_bus import EventBus
        EventBus.get_instance().notify(task_id, {"event_type": event_type.value, "event_seq": event_seq})

        return event

    async def get_events(
        self,
        task_id: str,
        org_id: str,
        start_after_seq: int | None = None,
    ) -> list[HermesTaskEvent]:
        stmt = select(HermesTaskEvent).where(
            HermesTaskEvent.task_id == task_id,
            HermesTaskEvent.org_id == org_id,
        )
        if start_after_seq is not None:
            stmt = stmt.where(HermesTaskEvent.event_seq > start_after_seq)
        stmt = stmt.order_by(HermesTaskEvent.event_seq)
        result = await self.db.execute(stmt)
        return result.scalars().all()

    async def stream_events(
        self,
        task_id: str,
        org_id: str,
    ):
        from app.models.hermes_skill.hermes_task import TaskStatus, HermesTask

        queue: asyncio.Queue[HermesTaskEvent | None] = asyncio.Queue()
        _terminal_states = frozenset({
            TaskStatus.COMPLETED, TaskStatus.FAILED,
            TaskStatus.CANCELLED, TaskStatus.TIMEOUT,
        })

        existing_events = await self.get_events(task_id, org_id)
        for event in existing_events:
            yield event

        task = await self.db.get(HermesTask, task_id)
        if task and task.status in _terminal_states:
            return

        async def _watch():
            try:
                while True:
                    task = await self.db.get(HermesTask, task_id)
                    if task and task.status in _terminal_states:
                        await queue.put(None)
                        return

                    new_events = await self.get_events(task_id, org_id)
                    seen_seqs = {e.event_seq for e in existing_events}
                    for event in new_events:
                        if event.event_seq not in seen_seqs:
                            await queue.put(event)
                            seen_seqs.add(event.event_seq)

                    await asyncio.sleep(1)
            except Exception:
                await queue.put(None)

        watcher = asyncio.create_task(_watch())

        try:
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=30)
                except asyncio.TimeoutError:
                    yield None
                    continue

                if item is None:
                    break
                yield item
        finally:
            watcher.cancel()
            try:
                await watcher
            except asyncio.CancelledError:
                pass
