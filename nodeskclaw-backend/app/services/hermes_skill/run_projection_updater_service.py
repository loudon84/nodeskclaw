import asyncio
import logging
import uuid
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
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

                # 2. Fetch Events with incremental after_seq
                curr_cursor = task.projection_cursor or 0
                resp_events = await client.get(f"/internal/v1/runs/{task_id}/events", params={"after_seq": curr_cursor})
                resp_events.raise_for_status()
                events_data = resp_events.json().get("items", [])

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
                    "TIMED_OUT": TaskStatus.FAILED,
                }
                new_task_status = status_map.get(agent_status, task.status)
                task.status = new_task_status
                if agent_status == "TIMED_OUT":
                    task.error_code = task.error_code or "errors.skill_run.timed_out"
                    task.error_message = task.error_message or "Run execution timed out"

                # 3. Apply events with local monotonic seq (Agent seq stored in payload)
                for ev in sorted(events_data, key=lambda x: x.get("event_seq", 0)):
                    agent_seq = ev.get("event_seq", 0)
                    if agent_seq <= curr_cursor:
                        continue

                    ev_type_str = ev.get("event_type", "")
                    raw_payload = ev.get("payload") or {}

                    mapped_type = self._map_event_type(ev_type_str)

                    merged_payload = {
                        "source": "agent",
                        "hermes_event_seq": agent_seq,
                        "payload": raw_payload,
                    }

                    local_seq = await self._next_local_seq(task_id)
                    task_event = HermesTaskEvent(
                        id=str(uuid.uuid4()),
                        org_id=org_id,
                        task_id=task_id,
                        event_type=mapped_type,
                        event_seq=local_seq,
                        payload=merged_payload,
                    )
                    try:
                        self.db.add(task_event)
                        await self.db.flush()
                    except IntegrityError:
                        await self.db.rollback()
                        logger.warning(
                            "projection event_seq conflict task=%s agent_seq=%s local_seq=%s, retrying",
                            task_id, agent_seq, local_seq,
                        )
                        local_seq = await self._next_local_seq(task_id)
                        task_event = HermesTaskEvent(
                            id=str(uuid.uuid4()),
                            org_id=org_id,
                            task_id=task_id,
                            event_type=mapped_type,
                            event_seq=local_seq,
                            payload=merged_payload,
                        )
                        self.db.add(task_event)
                        await self.db.flush()
                    curr_cursor = agent_seq

                task.projection_cursor = curr_cursor

                # 4. If completed or failed, sync result & artifacts
                if new_task_status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                    resp_result = await client.get(f"/internal/v1/runs/{task_id}/result")
                    if resp_result.status_code == 200:
                        res_json = resp_result.json()
                        result_obj = res_json.get("result")
                        if isinstance(result_obj, dict):
                            task.result_content = result_obj.get("content") or ""
                            task.result_summary = result_obj.get("summary") or ""
                        elif isinstance(result_obj, str):
                            task.result_content = result_obj
                            task.result_summary = result_obj[:500] if result_obj else ""

                    resp_artifacts = await client.get(f"/internal/v1/runs/{task_id}/artifacts")
                    if resp_artifacts.status_code == 200:
                        task.server_artifacts = resp_artifacts.json().get("items", [])

                await self.db.commit()
                return True
        except Exception:
            logger.exception("Failed to sync projection for task_id=%s", task_id)
            await self.db.rollback()
            return False

    async def _next_local_seq(self, task_id: str) -> int:
        max_seq_result = await self.db.execute(
            select(HermesTaskEvent.event_seq)
            .where(HermesTaskEvent.task_id == task_id)
            .order_by(HermesTaskEvent.event_seq.desc())
            .limit(1)
        )
        return (max_seq_result.scalar_one_or_none() or 0) + 1

    @staticmethod
    def _map_event_type(ev_type_str: str) -> EventType:
        mapping = {
            "run.started": EventType.TASK_STARTED,
            "run.completed": EventType.TASK_COMPLETED,
            "run.failed": EventType.TASK_FAILED,
            "run.cancelled": EventType.TASK_CANCELLED,
            "run.cancelling": EventType.TASK_CANCEL_REQUESTED,
        }
        return mapping.get(ev_type_str, EventType.HERMES_RUN_DELTA)


# @lat: [[architecture/backend#C2 Projection Sync]]
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
            stmt = (
                select(HermesTask)
                .where(
                    HermesTask.status.in_([TaskStatus.QUEUED, TaskStatus.ACCEPTED, TaskStatus.RUNNING, TaskStatus.WAITING_APPROVAL])
                )
                .limit(settings.SKILL_RUN_PROJECTION_BATCH_SIZE)
            )
            res = await db.execute(stmt)
            task_refs = [(t.id, t.org_id, t.user_id) for t in res.scalars().all()]

        if not task_refs:
            return

        for task_id, org_id, user_id in task_refs:
            async with async_session_factory() as db:
                service = RunProjectionUpdaterService(db)
                await service.sync_task_projection(task_id, org_id, user_id)
