import hashlib
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_task import HermesTask, HermesTaskEvent, TaskStatus, EventType
from app.services.hermes_skill.hermes_queue_policy_service import HermesQueuePolicyService

logger = logging.getLogger(__name__)


class TaskService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_task(
        self,
        org_id: str,
        skill_id: str,
        tool_name: str,
        agent_id: str | None = None,
        profile_id: str | None = None,
        workspace_id: str | None = None,
        installation_id: str | None = None,
        user_id: str | None = None,
        arguments: dict | None = None,
        client_context: dict | None = None,
        routing_metadata: dict | None = None,
    ) -> HermesTask:
        queue_policy = HermesQueuePolicyService(self.db)
        can_enqueue, message_key = await queue_policy.can_enqueue(
            org_id, user_id, agent_id, skill_id,
        )
        if not can_enqueue:
            raise BadRequestError("任务无法入队", message_key or "errors.hermes.cannot_enqueue")

        arguments_hash = ""
        if arguments:
            arguments_hash = hashlib.sha256(
                str(sorted(arguments.items())).encode()
            ).hexdigest()

        task = HermesTask(
            id=str(uuid.uuid4()),
            org_id=org_id,
            task_no=f"TASK-{org_id[:4]}-{uuid.uuid4().hex[:8]}",
            skill_id=skill_id,
            tool_name=tool_name,
            agent_id=agent_id,
            profile_id=profile_id,
            workspace_id=workspace_id,
            installation_id=installation_id,
            user_id=user_id,
            status=TaskStatus.QUEUED,
            arguments=arguments,
            arguments_hash=arguments_hash,
            timeout_seconds=settings.HERMES_TASK_DEFAULT_TIMEOUT_SECONDS,
            priority=settings.HERMES_QUEUE_DEFAULT_PRIORITY,
            max_retry=settings.HERMES_TASK_DEFAULT_MAX_RETRY,
            queue_entered_at=datetime.now(timezone.utc),
            event_url=f"/api/v1/hermes/tasks/{{task_id}}/events",
            artifact_url=f"/api/v1/hermes/tasks/{{task_id}}/artifacts",
            client_context=client_context,
            routing_metadata=routing_metadata,
        )
        self.db.add(task)
        await self.db.flush()
        await self.db.refresh(task)

        task.event_url = f"/api/v1/hermes/tasks/{task.id}/events"
        task.artifact_url = f"/api/v1/hermes/tasks/{task.id}/artifacts"

        task_event = HermesTaskEvent(
            id=str(uuid.uuid4()),
            org_id=org_id,
            task_id=task.id,
            event_type=EventType.TASK_CREATED,
            event_seq=0,
            payload={"skill_id": skill_id, "tool_name": tool_name},
        )
        self.db.add(task_event)

        queued_event = HermesTaskEvent(
            id=str(uuid.uuid4()),
            org_id=org_id,
            task_id=task.id,
            event_type=EventType.TASK_QUEUED,
            event_seq=1,
            payload={"status": TaskStatus.QUEUED.value},
        )
        self.db.add(queued_event)
        await self.db.flush()

        return task

    async def _has_event(self, task_id: str, event_type: EventType) -> bool:
        result = await self.db.execute(
            select(HermesTaskEvent.id).where(
                HermesTaskEvent.task_id == task_id,
                HermesTaskEvent.event_type == event_type,
            ).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def mark_accepted(self, task: HermesTask, payload: dict | None = None) -> HermesTask:
        if task.status != TaskStatus.ACCEPTED:
            task.status = TaskStatus.ACCEPTED
        event_payload = payload or {"status": TaskStatus.ACCEPTED.value}
        if not await self._has_event(task.id, EventType.TASK_ACCEPTED):
            await self._append_status_event(task, EventType.TASK_ACCEPTED, event_payload)
        await self.db.flush()
        return task

    async def mark_running(self, task: HermesTask) -> HermesTask:
        if task.status != TaskStatus.RUNNING:
            task.status = TaskStatus.RUNNING
            task.started_at = task.started_at or datetime.now(timezone.utc)
        if not await self._has_event(task.id, EventType.TASK_STARTED):
            await self._append_status_event(task, EventType.TASK_STARTED, {"status": TaskStatus.RUNNING.value})
        await self.db.flush()
        return task

    async def mark_completed(self, task: HermesTask, result_summary: str | None = None) -> HermesTask:
        if task.status == TaskStatus.COMPLETED:
            return task
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now(timezone.utc)
        if result_summary:
            task.result_summary = result_summary
        await self._append_status_event(task, EventType.TASK_COMPLETED, {"status": TaskStatus.COMPLETED.value})
        await self.db.flush()
        return task

    async def mark_failed(
        self,
        task: HermesTask,
        error_code: str,
        error_message: str,
    ) -> HermesTask:
        if task.status == TaskStatus.FAILED:
            return task
        task.status = TaskStatus.FAILED
        task.error_code = error_code
        task.error_message = error_message[:1024]
        task.completed_at = datetime.now(timezone.utc)
        await self._append_status_event(
            task,
            EventType.TASK_FAILED,
            {"status": TaskStatus.FAILED.value, "error_code": error_code, "error_message": error_message[:1024]},
        )
        await self.db.flush()
        return task

    async def mark_timeout(self, task: HermesTask, elapsed_seconds: float) -> HermesTask:
        if task.status == TaskStatus.TIMEOUT:
            return task
        task.status = TaskStatus.TIMEOUT
        task.completed_at = datetime.now(timezone.utc)
        task.run_finished_at = task.completed_at
        task.last_dispatch_error = "task timeout"
        await self._append_status_event(
            task,
            EventType.TASK_TIMEOUT,
            {"status": TaskStatus.TIMEOUT.value, "elapsed_seconds": elapsed_seconds},
        )
        await self.db.flush()
        return task

    async def _append_status_event(self, task: HermesTask, event_type: EventType, payload: dict) -> None:
        max_seq_result = await self.db.execute(
            select(HermesTaskEvent.event_seq).where(
                HermesTaskEvent.task_id == task.id,
            ).order_by(HermesTaskEvent.event_seq.desc()).limit(1)
        )
        max_seq = max_seq_result.scalar_one_or_none() or 0
        self.db.add(
            HermesTaskEvent(
                id=str(uuid.uuid4()),
                org_id=task.org_id,
                task_id=task.id,
                event_type=event_type,
                event_seq=max_seq + 1,
                payload=payload,
            )
        )

    async def get_task(self, task_id: str, org_id: str) -> HermesTask:
        task = await self.db.get(HermesTask, task_id)
        if not task or task.deleted_at is not None or task.org_id != org_id:
            raise NotFoundError("Task 不存在", "errors.task.not_found")
        return task

    async def update_status(
        self,
        task_id: str,
        org_id: str,
        new_status: TaskStatus,
        error_code: str | None = None,
        error_message: str | None = None,
        result_summary: str | None = None,
    ) -> HermesTask:
        task = await self.get_task(task_id, org_id)
        task.status = new_status

        if error_code:
            task.error_code = error_code
        if error_message:
            task.error_message = error_message
        if result_summary:
            task.result_summary = result_summary

        now = datetime.now(timezone.utc)
        if new_status == TaskStatus.RUNNING:
            task.started_at = now
        elif new_status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.TIMEOUT):
            task.completed_at = now

        event_type_map = {
            TaskStatus.RUNNING: EventType.TASK_STARTED,
            TaskStatus.COMPLETED: EventType.TASK_COMPLETED,
            TaskStatus.FAILED: EventType.TASK_FAILED,
            TaskStatus.CANCELLED: EventType.TASK_CANCELLED,
        }
        event_type = event_type_map.get(new_status)
        if event_type:
            max_seq_result = await self.db.execute(
                select(HermesTaskEvent.event_seq).where(
                    HermesTaskEvent.task_id == task_id,
                ).order_by(HermesTaskEvent.event_seq.desc()).limit(1)
            )
            max_seq = max_seq_result.scalar_one_or_none() or 0
            task_event = HermesTaskEvent(
                id=str(uuid.uuid4()),
                org_id=org_id,
                task_id=task_id,
                event_type=event_type,
                event_seq=max_seq + 1,
                payload={"status": new_status.value},
            )
            self.db.add(task_event)

        await self.db.flush()
        return task

    async def list_tasks(
        self,
        org_id: str,
        skill_id: str | None = None,
        status: str | None = None,
        tool_name: str | None = None,
        agent_id: str | None = None,
        profile_id: str | None = None,
        workspace_id: str | None = None,
        user_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[HermesTask], int]:
        stmt = select(HermesTask).where(
            not_deleted(HermesTask),
            HermesTask.org_id == org_id,
        )
        from sqlalchemy import func
        count_stmt = select(func.count()).select_from(HermesTask).where(
            not_deleted(HermesTask),
            HermesTask.org_id == org_id,
        )
        if skill_id:
            stmt = stmt.where(HermesTask.skill_id == skill_id)
            count_stmt = count_stmt.where(HermesTask.skill_id == skill_id)
        if status:
            stmt = stmt.where(HermesTask.status == status)
            count_stmt = count_stmt.where(HermesTask.status == status)
        if tool_name:
            stmt = stmt.where(HermesTask.tool_name == tool_name)
            count_stmt = count_stmt.where(HermesTask.tool_name == tool_name)
        if agent_id:
            stmt = stmt.where(HermesTask.agent_id == agent_id)
            count_stmt = count_stmt.where(HermesTask.agent_id == agent_id)
        if profile_id:
            stmt = stmt.where(HermesTask.profile_id == profile_id)
            count_stmt = count_stmt.where(HermesTask.profile_id == profile_id)
        if workspace_id:
            stmt = stmt.where(HermesTask.workspace_id == workspace_id)
            count_stmt = count_stmt.where(HermesTask.workspace_id == workspace_id)
        if user_id:
            stmt = stmt.where(HermesTask.user_id == user_id)
            count_stmt = count_stmt.where(HermesTask.user_id == user_id)

        total = (await self.db.execute(count_stmt)).scalar() or 0
        offset = (page - 1) * page_size
        stmt = stmt.order_by(HermesTask.created_at.desc()).offset(offset).limit(page_size)
        result = await self.db.execute(stmt)
        return result.scalars().all(), total
