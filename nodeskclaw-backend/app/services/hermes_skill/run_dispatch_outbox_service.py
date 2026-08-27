import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import async_session_factory
from app.models.base import not_deleted
from app.models.hermes_skill.run_dispatch_outbox import RunDispatchOutbox, RunDispatchStatus

logger = logging.getLogger(__name__)


class RunDispatchOutboxService:
    def __init__(self, db: AsyncSession, dispatcher_id: str | None = None):
        self.db = db
        self.dispatcher_id = dispatcher_id or f"disp-{uuid.uuid4().hex[:8]}"

    async def claim_pending(self, batch_size: int | None = None) -> list[RunDispatchOutbox]:
        limit = batch_size or settings.SKILL_RUN_DISPATCHER_BATCH_SIZE
        now = datetime.now(timezone.utc)
        lease_duration = timedelta(seconds=settings.SKILL_RUN_DISPATCHER_LEASE_SECONDS)
        lease_until = now + lease_duration

        stmt = (
            select(RunDispatchOutbox)
            .where(
                not_deleted(RunDispatchOutbox),
                or_(
                    RunDispatchOutbox.status == RunDispatchStatus.PENDING.value,
                    (RunDispatchOutbox.status == RunDispatchStatus.DELIVERING.value)
                    & (RunDispatchOutbox.lease_until.is_not(None))
                    & (RunDispatchOutbox.lease_until < now),
                ),
                or_(
                    RunDispatchOutbox.next_retry_at.is_(None),
                    RunDispatchOutbox.next_retry_at <= now,
                ),
            )
            .order_by(RunDispatchOutbox.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        result = await self.db.execute(stmt)
        entries = list(result.scalars().all())

        for entry in entries:
            entry.status = RunDispatchStatus.DELIVERING.value
            entry.dispatcher_id = self.dispatcher_id
            entry.claimed_at = now
            entry.lease_until = lease_until

        if entries:
            await self.db.flush()
        return entries

    async def deliver_entry(self, entry: RunDispatchOutbox) -> bool:
        url = f"{settings.SKILL_AGENT_BASE_URL.rstrip('/')}/internal/v1/runs"
        headers = {
            "X-Skill-Agent-Token": settings.SKILL_AGENT_INTERNAL_TOKEN,
            "X-Exec-Org-Id": entry.org_id,
            "X-Exec-User-Id": entry.user_id,
            "Content-Type": "application/json",
        }
        payload = dict(entry.payload or {})
        payload.setdefault("run_id", entry.run_id)
        payload.setdefault("dispatch_id", entry.dispatch_id)
        payload.setdefault("tool_name", entry.tool_name)

        now = datetime.now(timezone.utc)
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=3.0)) as client:
                res = await client.post(url, headers=headers, json=payload)
                if res.status_code in (200, 201):
                    entry.status = RunDispatchStatus.DELIVERED.value
                    entry.delivered_at = now
                    entry.lease_until = None
                    entry.last_error = None
                    logger.info("Outbox dispatch delivered: run_id=%s dispatch_id=%s", entry.run_id, entry.dispatch_id)
                    return True
                else:
                    err_msg = f"HTTP {res.status_code}: {res.text[:256]}"
                    # Permanent 4xx client/schema/auth errors (except transient 408 Request Timeout / 429 Too Many Requests) -> Dead Letter directly
                    is_permanent_error = (400 <= res.status_code < 500) and res.status_code not in (408, 429)
                    self._record_failure(entry, err_msg, now, dead_letter_immediately=is_permanent_error)
                    return False
        except Exception as exc:
            err_msg = f"Connection/Transport error: {str(exc)[:256]}"
            self._record_failure(entry, err_msg, now, dead_letter_immediately=False)
            return False

    def _record_failure(
        self,
        entry: RunDispatchOutbox,
        error_message: str,
        now: datetime,
        *,
        dead_letter_immediately: bool = False,
    ) -> None:
        entry.retry_count += 1
        entry.last_error = error_message
        entry.lease_until = None
        if dead_letter_immediately or entry.retry_count >= entry.max_retries:
            entry.status = RunDispatchStatus.DEAD_LETTER.value
            entry.next_retry_at = None
            logger.warning(
                "Outbox dispatch dead-lettered: run_id=%s dispatch_id=%s retries=%d immediate=%s error=%s",
                entry.run_id,
                entry.dispatch_id,
                entry.retry_count,
                dead_letter_immediately,
                error_message,
            )
        else:
            backoff_secs = min(300, 2 ** entry.retry_count)
            entry.status = RunDispatchStatus.PENDING.value
            entry.next_retry_at = now + timedelta(seconds=backoff_secs)
            logger.info(
                "Outbox dispatch retry scheduled: run_id=%s retry=%d in %ds error=%s",
                entry.run_id,
                entry.retry_count,
                backoff_secs,
                error_message,
            )


class RunDispatchWorker:
    def __init__(self):
        self._running = False
        self._dispatcher_id = f"worker-{uuid.uuid4().hex[:8]}"

    async def start(self):
        self._running = True
        logger.info("RunDispatchWorker started, dispatcher_id=%s", self._dispatcher_id)
        while self._running:
            try:
                await self._poll_once()
            except Exception as exc:
                logger.error("RunDispatchWorker poll error: %s", exc)
            await asyncio.sleep(settings.SKILL_RUN_DISPATCHER_INTERVAL_SECONDS)

    def stop(self):
        self._running = False
        logger.info("RunDispatchWorker stopped")

    async def _poll_once(self):
        async with async_session_factory() as db:
            service = RunDispatchOutboxService(db, dispatcher_id=self._dispatcher_id)
            entries = await service.claim_pending()
            if not entries:
                return

            await db.commit()

            for entry in entries:
                async with async_session_factory() as item_db:
                    item_service = RunDispatchOutboxService(item_db, dispatcher_id=self._dispatcher_id)
                    item = await item_db.get(RunDispatchOutbox, entry.id)
                    if (
                        item
                        and item.status == RunDispatchStatus.DELIVERING.value
                        and item.dispatcher_id == self._dispatcher_id
                    ):
                        await item_service.deliver_entry(item)
                        await item_db.commit()
