import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hermes_skill.hermes_task import HermesTaskEvent, EventType

logger = logging.getLogger(__name__)


class TaskEventService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def write_event(
        self,
        task_id: str,
        org_id: str,
        event_type: EventType,
        payload: dict | None = None,
    ) -> HermesTaskEvent:
        max_seq_result = await self.db.execute(
            select(HermesTaskEvent.event_seq).where(
                HermesTaskEvent.task_id == task_id,
            ).order_by(HermesTaskEvent.event_seq.desc()).limit(1)
        )
        max_seq = max_seq_result.scalar_one_or_none() or 0

        event = HermesTaskEvent(
            id=str(uuid.uuid4()),
            org_id=org_id,
            task_id=task_id,
            event_type=event_type,
            event_seq=max_seq + 1,
            payload=payload,
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def get_events(
        self,
        task_id: str,
        org_id: str,
    ) -> list[HermesTaskEvent]:
        result = await self.db.execute(
            select(HermesTaskEvent).where(
                HermesTaskEvent.task_id == task_id,
                HermesTaskEvent.org_id == org_id,
            ).order_by(HermesTaskEvent.event_seq)
        )
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
