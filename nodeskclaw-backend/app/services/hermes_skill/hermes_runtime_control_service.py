import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_runtime_control import HermesRuntimeControl
from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus, EventType

logger = logging.getLogger(__name__)

WORKER_PAUSED_KEY = "worker.paused"
QUEUE_PAUSED_KEY = "queue.paused"


class HermesRuntimeControlService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_controls(self, org_id: str) -> dict:
        worker = await self._get_control(org_id, WORKER_PAUSED_KEY)
        queue = await self._get_control(org_id, QUEUE_PAUSED_KEY)
        return {
            "worker": {"paused": self._is_true(worker), "reason": worker.reason if worker else None},
            "queue": {"paused": self._is_true(queue), "reason": queue.reason if queue else None},
        }

    async def is_worker_paused(self, org_id: str) -> bool:
        control = await self._get_control(org_id, WORKER_PAUSED_KEY)
        return self._is_true(control)

    async def is_queue_paused(self, org_id: str) -> bool:
        control = await self._get_control(org_id, QUEUE_PAUSED_KEY)
        return self._is_true(control)

    async def pause_worker(self, org_id: str, reason: str | None, actor_id: str | None) -> dict:
        await self._set_control(org_id, WORKER_PAUSED_KEY, "true", reason, actor_id)
        return await self.get_controls(org_id)

    async def resume_worker(self, org_id: str, actor_id: str | None) -> dict:
        await self._set_control(org_id, WORKER_PAUSED_KEY, "false", None, actor_id)
        return await self.get_controls(org_id)

    async def pause_queue(self, org_id: str, reason: str | None, actor_id: str | None) -> dict:
        await self._set_control(org_id, QUEUE_PAUSED_KEY, "true", reason, actor_id)
        return await self.get_controls(org_id)

    async def resume_queue(self, org_id: str, actor_id: str | None) -> dict:
        await self._set_control(org_id, QUEUE_PAUSED_KEY, "false", None, actor_id)
        return await self.get_controls(org_id)

    async def clear_stale_locks(self, org_id: str) -> dict:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.HERMES_TASK_LOCK_TIMEOUT_SECONDS)
        stmt = select(HermesTask).where(
            not_deleted(HermesTask),
            HermesTask.org_id == org_id,
            HermesTask.status.in_([TaskStatus.QUEUED, TaskStatus.ACCEPTED]),
            HermesTask.locked_at.isnot(None),
            HermesTask.locked_at < cutoff,
        )
        result = await self.db.execute(stmt)
        cleared = 0
        for task in result.scalars().all():
            task.worker_id = None
            task.locked_at = None
            if task.status == TaskStatus.ACCEPTED:
                task.status = TaskStatus.QUEUED
            cleared += 1
        await self.db.flush()
        return {"cleared": cleared}

    async def requeue_task(self, task: HermesTask, actor_id: str | None = None) -> HermesTask:
        requeueable = {TaskStatus.FAILED, TaskStatus.TIMEOUT, TaskStatus.RUNNING, TaskStatus.ACCEPTED}
        if task.status not in requeueable:
            raise BadRequestError("当前任务状态不可重新入队", "errors.task.cannot_requeue")

        task.status = TaskStatus.QUEUED
        task.worker_id = None
        task.locked_at = None
        task.dispatch_status = None
        task.error_code = None
        task.error_message = None
        task.queue_entered_at = datetime.now(timezone.utc)
        from app.services.hermes_skill.task_service import TaskService
        task_service = TaskService(self.db)
        await task_service._append_status_event(
            task,
            EventType.TASK_QUEUED,
            {"status": TaskStatus.QUEUED.value, "requeued": True, "actor_id": actor_id},
        )
        await self.db.flush()
        return task

    async def mark_task_failed(
        self,
        task: HermesTask,
        error_code: str,
        error_message: str,
        actor_id: str | None = None,
    ) -> HermesTask:
        from app.services.hermes_skill.task_service import TaskService
        task_service = TaskService(self.db)
        await task_service.mark_failed(task, error_code, error_message)
        task.worker_id = None
        task.locked_at = None
        task.dispatch_status = "failed"
        await self.db.flush()
        return task

    async def _get_control(self, org_id: str, key: str) -> HermesRuntimeControl | None:
        result = await self.db.execute(
            select(HermesRuntimeControl).where(
                not_deleted(HermesRuntimeControl),
                HermesRuntimeControl.org_id == org_id,
                HermesRuntimeControl.control_key == key,
            )
        )
        return result.scalar_one_or_none()

    async def _set_control(
        self,
        org_id: str,
        key: str,
        value: str,
        reason: str | None,
        actor_id: str | None,
    ) -> HermesRuntimeControl:
        control = await self._get_control(org_id, key)
        if control is None:
            control = HermesRuntimeControl(
                id=str(uuid.uuid4()),
                org_id=org_id,
                control_key=key,
                control_value=value,
                reason=reason,
                updated_by=actor_id,
            )
            self.db.add(control)
        else:
            control.control_value = value
            control.reason = reason
            control.updated_by = actor_id
        await self.db.flush()
        return control

    @staticmethod
    def _is_true(control: HermesRuntimeControl | None) -> bool:
        if control is None:
            return False
        return control.control_value.lower() in ("true", "1", "yes")
