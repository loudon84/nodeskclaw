import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import async_session_factory
from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus, EventType
from app.models.base import not_deleted
from app.services.hermes_skill.hermes_agent_adapter import HermesAgentAdapter
from app.services.hermes_skill.hermes_run_state_resolver import HermesRunStateResolver, RunStateTracker
from app.services.hermes_skill.hermes_queue_policy_service import HermesQueuePolicyService
from app.services.hermes_skill.hermes_runtime_control_service import HermesRuntimeControlService
from app.services.hermes_skill.task_event_service import TaskEventService
from app.services.hermes_skill.task_service import TaskService
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger

logger = logging.getLogger(__name__)


class HermesTaskWorker:
    def __init__(self):
        self._running = False
        self._worker_id = uuid.uuid4().hex[:12]

    async def start(self):
        self._running = True
        logger.info("HermesTaskWorker started, worker_id=%s", self._worker_id)
        while self._running:
            try:
                await self._poll_once()
            except Exception as exc:
                logger.error("Worker poll error: %s", exc)
            await asyncio.sleep(settings.HERMES_TASK_WORKER_INTERVAL_SECONDS)

    def stop(self):
        self._running = False
        logger.info("HermesTaskWorker stopped")

    async def _poll_once(self):
        async with async_session_factory() as db:
            tasks = await self._fetch_and_lock(db)
            if not tasks:
                await self._check_timeouts(db)
                await db.commit()
                return

            for task in tasks:
                try:
                    await self._execute_task(db, task)
                except Exception as exc:
                    logger.error("Execute task %s error: %s", task.id, exc)
                    task_service = TaskService(db)
                    await task_service.mark_failed(
                        task,
                        error_code="TASK_EXECUTION_ERROR",
                        error_message=str(exc)[:1024],
                    )
                    await self._maybe_auto_retry(db, task, task_service)

                    audit_logger = SkillAuditLogger(db)
                    await audit_logger.log(
                        action="hermes.task.failed",
                        target_id=task.id,
                        org_id=task.org_id,
                        actor_type="system",
                        actor_id=self._worker_id,
                        details={"task_no": task.task_no, "error": str(exc)[:512]},
                    )

                    task.worker_id = None
                    task.locked_at = None
                    task.dispatch_status = "failed"
                    await db.commit()

            await self._check_timeouts(db)
            await db.commit()

    async def _fetch_and_lock(self, db: AsyncSession) -> list[HermesTask]:
        from datetime import timedelta
        from sqlalchemy import nullsfirst

        lock_cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.HERMES_TASK_LOCK_TIMEOUT_SECONDS)
        control = HermesRuntimeControlService(db)
        policy = HermesQueuePolicyService(db)

        stmt = (
            select(HermesTask)
            .where(
                not_deleted(HermesTask),
                HermesTask.status == TaskStatus.QUEUED,
                (HermesTask.locked_at.is_(None)) | (HermesTask.locked_at < lock_cutoff),
            )
            .order_by(
                HermesTask.priority.desc(),
                nullsfirst(HermesTask.scheduled_at.asc()),
                HermesTask.created_at.asc(),
            )
            .limit(settings.HERMES_TASK_WORKER_BATCH_SIZE * 3)
            .with_for_update(skip_locked=True)
        )
        result = await db.execute(stmt)
        candidates = list(result.scalars().all())

        now = datetime.now(timezone.utc)
        task_service = TaskService(db)
        accepted: list[HermesTask] = []
        for task in candidates:
            if len(accepted) >= settings.HERMES_TASK_WORKER_BATCH_SIZE:
                break
            if await control.is_worker_paused(task.org_id):
                continue
            if task.not_before and task.not_before > now:
                continue
            can_dispatch, _ = await policy.can_dispatch(task)
            if not can_dispatch:
                continue

            task.worker_id = self._worker_id
            task.locked_at = now
            task.dispatch_status = "accepted"
            task.dispatch_attempts = (task.dispatch_attempts or 0) + 1
            task.run_dispatched_at = now
            await task_service.mark_accepted(
                task,
                payload={
                    "worker_id": self._worker_id,
                    "dispatch_attempts": task.dispatch_attempts,
                    "status": TaskStatus.ACCEPTED.value,
                },
            )
            accepted.append(task)

        await db.flush()
        return accepted

    async def _execute_task(self, db: AsyncSession, task: HermesTask):
        now = datetime.now(timezone.utc)
        event_service = TaskEventService(db)
        task_service = TaskService(db)
        audit_logger = SkillAuditLogger(db)

        try:
            task.status = TaskStatus.RUNNING
            task.run_started_at = now
            task.dispatch_status = "running"

            await task_service.mark_running(task)

            await audit_logger.log(
                action="hermes.task.started",
                target_id=task.id,
                org_id=task.org_id,
                actor_type="system",
                actor_id=self._worker_id,
                details={"task_no": task.task_no, "skill_id": task.skill_id, "tool_name": task.tool_name},
            )
            await db.flush()

            if await event_service.has_event(task.id, EventType.TASK_CANCEL_REQUESTED):
                await task_service.mark_failed(
                    task,
                    error_code="TASK_CANCELLED",
                    error_message="任务已请求取消",
                )
                task.status = TaskStatus.CANCELLED
                await db.flush()
                return

            adapter = HermesAgentAdapter(db)
            try:
                await adapter.submit_run(task, task.arguments or {})
            except Exception as exc:
                await task_service.mark_failed(
                    task,
                    error_code="AGENT_UNREACHABLE",
                    error_message=str(exc)[:1024],
                )
                task.worker_id = None
                task.locked_at = None
                task.dispatch_status = "failed"
                await db.flush()
                return

            if not await event_service.has_event(task.id, EventType.HERMES_RUN_CREATED):
                await event_service.write_event(
                    task_id=task.id,
                    org_id=task.org_id,
                    event_type=EventType.HERMES_RUN_CREATED,
                    payload={"hermes_run_id": task.hermes_run_id},
                )
            await db.flush()

            stream_interrupted = False
            state_tracker = RunStateTracker()
            try:
                async for event_data in adapter.read_run_events(task):
                    try:
                        converted = HermesRunStateResolver.convert_hermes_event(event_data)
                    except Exception as exc:
                        logger.warning("convert_events failed for task %s: %s", task.id, exc)
                        continue
                    if not converted:
                        continue
                    state_tracker.observe_event_type(
                        converted["event_type"],
                        converted.get("payload"),
                    )
                    try:
                        await event_service.write_event(
                            task_id=task.id,
                            org_id=task.org_id,
                            event_type=converted["event_type"],
                            payload=converted.get("payload"),
                            source="hermes",
                            source_event_seq=converted.get("source_event_seq"),
                        )
                    except Exception as exc:
                        logger.warning("write_event failed for task %s: %s", task.id, exc)
                    await db.flush()
            except Exception as exc:
                logger.warning("read_run_events stream error for task %s: %s", task.id, exc)
                stream_interrupted = True

            await db.refresh(task)

            if task.status == TaskStatus.RUNNING:
                run_status_value: str | None = None
                resolved = state_tracker.resolve_after_stream(
                    stream_interrupted=stream_interrupted,
                    run_status=None,
                )

                if resolved is None:
                    try:
                        run_status = await adapter.get_run_status(task)
                        run_status_value = run_status.get("status", "unknown")
                    except Exception as exc:
                        logger.error("get_run_status failed for task %s: %s", task.id, exc)
                        run_status_value = "unknown"

                    resolved = state_tracker.resolve_after_stream(
                        stream_interrupted=stream_interrupted,
                        run_status=run_status_value,
                    )
                    if resolved is None and run_status_value:
                        resolved = state_tracker.map_hermes_run_status(run_status_value)

                if resolved is None and (
        run_status_value in (None, "unknown", "running", "in_progress", "created", "queued")
        or state_tracker.map_hermes_run_status(str(run_status_value or "unknown")) == TaskStatus.RUNNING
    ):
                    task.worker_id = None
                    task.locked_at = None
                    task.dispatch_status = "running"
                    await db.flush()
                    return

                if resolved == TaskStatus.FAILED:
                    await task_service.mark_failed(
                        task,
                        error_code="RUN_FAILED",
                        error_message=state_tracker.last_error or "Run failed",
                    )
                elif resolved == TaskStatus.CANCELLED:
                    task.status = TaskStatus.CANCELLED
                    task.run_finished_at = datetime.now(timezone.utc)
                    await task_service.update_status(task.id, task.org_id, TaskStatus.CANCELLED)
                elif resolved == TaskStatus.COMPLETED:
                    task.status = TaskStatus.COMPLETED
                    task.run_finished_at = datetime.now(timezone.utc)
                    task.completed_at = datetime.now(timezone.utc)
                elif resolved == TaskStatus.TIMEOUT:
                    await task_service.mark_timeout(
                        task,
                        (datetime.now(timezone.utc) - task.run_started_at).total_seconds()
                        if task.run_started_at else 0,
                    )
                elif resolved is None:
                    await task_service.mark_failed(
                        task,
                        error_code="RUN_STATUS_UNKNOWN",
                        error_message=f"Unknown run status: {run_status_value}",
                    )

                if task.status == TaskStatus.COMPLETED:
                    await task_service.mark_completed(task)
                    await audit_logger.log(
                        action="hermes.task.completed",
                        target_id=task.id,
                        org_id=task.org_id,
                        actor_type="system",
                        actor_id=self._worker_id,
                        details={
                            "task_no": task.task_no,
                            "skill_id": task.skill_id,
                            "hermes_run_id": task.hermes_run_id,
                        },
                    )
                    await db.flush()
                    await self._scan_artifacts(db, task)

                elif task.status == TaskStatus.FAILED:
                    await audit_logger.log(
                        action="hermes.task.failed",
                        target_id=task.id,
                        org_id=task.org_id,
                        actor_type="system",
                        actor_id=self._worker_id,
                        details={
                            "task_no": task.task_no,
                            "error_code": task.error_code,
                            "error_message": task.error_message,
                        },
                    )
        finally:
            task.worker_id = None
            task.locked_at = None
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.TIMEOUT, TaskStatus.CANCELLED):
                task.dispatch_status = "finished"
            await db.flush()

    async def _maybe_auto_retry(
        self,
        db: AsyncSession,
        task: HermesTask,
        task_service: TaskService,
    ) -> None:
        if task.status != TaskStatus.FAILED:
            return
        if task.retry_count >= task.max_retry:
            return
        policy = HermesQueuePolicyService(db)
        task.status = TaskStatus.QUEUED
        task.retry_count += 1
        task.not_before = policy.compute_retry_not_before(task.retry_count)
        task.worker_id = None
        task.locked_at = None
        task.queue_entered_at = datetime.now(timezone.utc)
        task.error_code = None
        task.error_message = None
        await task_service._append_status_event(
            task,
            EventType.TASK_RETRYING,
            {
                "status": TaskStatus.QUEUED.value,
                "retry_count": task.retry_count,
                "not_before": task.not_before.isoformat() if task.not_before else None,
            },
        )
        await db.flush()

    async def _scan_artifacts(self, db: AsyncSession, task: HermesTask) -> None:
        try:
            from app.services.hermes_skill.artifact_service import ArtifactService
            artifact_service = ArtifactService(db)
            await artifact_service.scan_and_register(task.id, task.org_id)
        except Exception as exc:
            logger.error("Artifact scan failed for task %s: %s", task.id, exc)

    async def _check_timeouts(self, db: AsyncSession):
        now = datetime.now(timezone.utc)
        stmt = select(HermesTask).where(
            not_deleted(HermesTask),
            HermesTask.status == TaskStatus.RUNNING,
            HermesTask.run_started_at.isnot(None),
        )
        result = await db.execute(stmt)
        event_service = TaskEventService(db)
        task_service = TaskService(db)
        for task in result.scalars().all():
            elapsed = (now - task.run_started_at).total_seconds() if task.run_started_at else 0
            if elapsed > task.timeout_seconds:
                await task_service.mark_timeout(task, elapsed)
                task.worker_id = None
                task.locked_at = None

                audit_logger = SkillAuditLogger(db)
                await audit_logger.log(
                    action="hermes.task.timeout",
                    target_id=task.id,
                    org_id=task.org_id,
                    actor_type="system",
                    actor_id=self._worker_id,
                    details={"task_no": task.task_no, "elapsed_seconds": elapsed},
                )
                await db.flush()
