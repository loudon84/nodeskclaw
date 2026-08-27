import asyncio
import logging
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import async_session_factory
from app.models.hermes_skill.hermes_task import HermesTask, HermesTaskEvent, TaskStatus, EventType

logger = logging.getLogger(__name__)


class RunProjectionUpdaterService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def sync_task_projection(self, task_id: str, org_id: str, user_id: str | None = None) -> bool:
        stmt = select(HermesTask).where(HermesTask.id == task_id, HermesTask.org_id == org_id)
        res = await self.db.execute(stmt)
        task = res.scalar_one_or_none()
        if not task:
            return False

        agent_base = settings.SKILL_AGENT_BASE_URL.rstrip("/")
        headers = {
            "X-Skill-Agent-Token": settings.SKILL_AGENT_INTERNAL_TOKEN,
            "X-Exec-Org-Id": org_id,
            "X-Exec-User-Id": user_id or task.user_id or "",
        }

        try:
            async with httpx.AsyncClient(base_url=agent_base, headers=headers, timeout=10.0) as client:
                # 1. Fetch Run details
                resp_run = await client.get(f"/internal/v1/runs/{task_id}")
                if resp_run.status_code == 404:
                    return False
                resp_run.raise_for_status()
                run_data = resp_run.json()

                # 2. Fetch Events
                resp_events = await client.get(f"/internal/v1/runs/{task_id}/events")
                resp_events.raise_for_status()
                events_data = resp_events.json().get("events", [])

                # Map Run status to TaskStatus
                agent_status = run_data.get("status")
                status_map = {
                    "QUEUED": TaskStatus.QUEUED,
                    "PREPARING": TaskStatus.RUNNING,
                    "RUNNING": TaskStatus.RUNNING,
                    "WAITING_APPROVAL": TaskStatus.WAITING_APPROVAL,
                    "RESUMING": TaskStatus.RUNNING,
                    "CANCELLING": TaskStatus.RUNNING,
                    "COMPLETED": TaskStatus.COMPLETED,
                    "FAILED": TaskStatus.FAILED,
                    "CANCELLED": TaskStatus.CANCELLED,
                }
                new_task_status = status_map.get(agent_status, task.status)
                task.status = new_task_status

                # 3. Apply events monotonically
                curr_cursor = task.projection_cursor or 0
                for ev in sorted(events_data, key=lambda x: x.get("event_seq", 0)):
                    seq = ev.get("event_seq", 0)
                    if seq <= curr_cursor:
                        continue
                    
                    ev_type_str = ev.get("event_type", "")
                    payload = ev.get("payload") or {}

                    # Map event_type to EventType
                    mapped_type = None
                    if ev_type_str == "run.started":
                        mapped_type = EventType.TASK_STARTED
                    elif ev_type_str == "run.completed":
                        mapped_type = EventType.TASK_COMPLETED
                    elif ev_type_str == "run.failed":
                        mapped_type = EventType.TASK_FAILED
                    elif ev_type_str == "run.cancelled":
                        mapped_type = EventType.TASK_CANCELLED
                    elif ev_type_str == "run.cancelling":
                        mapped_type = EventType.TASK_CANCEL_REQUESTED
                    else:
                        mapped_type = EventType.HERMES_RUN_DELTA

                    task_event = HermesTaskEvent(
                        org_id=org_id,
                        task_id=task_id,
                        event_type=mapped_type,
                        event_seq=seq,
                        payload=payload,
                    )
                    self.db.add(task_event)
                    curr_cursor = seq

                task.projection_cursor = curr_cursor

                # 4. If completed, sync result & artifacts
                if new_task_status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    resp_result = await client.get(f"/internal/v1/runs/{task_id}/result")
                    if resp_result.status_code == 200:
                        res_json = resp_result.json()
                        task.result_content = res_json.get("content") or ""
                        task.result_summary = res_json.get("summary") or ""

                    resp_artifacts = await client.get(f"/internal/v1/runs/{task_id}/artifacts")
                    if resp_artifacts.status_code == 200:
                        task.server_artifacts = resp_artifacts.json().get("artifacts", [])

                await self.db.commit()
                return True
        except Exception:
            logger.exception("Failed to sync projection for task_id=%s", task_id)
            await self.db.rollback()
            return False


class RunProjectionWorker:
    def __init__(self):
        self._running = False

    async def start(self):
        self._running = True
        interval = float(settings.SKILL_RUN_PROJECTION_INTERVAL_SECONDS)
        while self._running:
            try:
                await self._run_once()
            except Exception:
                logger.exception("RunProjectionWorker loop iteration failed")
            await asyncio.sleep(interval)

    def stop(self):
        self._running = False

    async def _run_once(self):
        async with async_session_factory() as db:
            # Poll non-terminal tasks to sync projection
            stmt = (
                select(HermesTask)
                .where(
                    HermesTask.status.in_([TaskStatus.QUEUED, TaskStatus.ACCEPTED, TaskStatus.RUNNING, TaskStatus.WAITING_APPROVAL])
                )
                .limit(settings.SKILL_RUN_PROJECTION_BATCH_SIZE)
            )
            res = await db.execute(stmt)
            tasks = res.scalars().all()
            if not tasks:
                return

            service = RunProjectionUpdaterService(db)
            for t in tasks:
                await service.sync_task_projection(t.id, t.org_id, t.user_id)
