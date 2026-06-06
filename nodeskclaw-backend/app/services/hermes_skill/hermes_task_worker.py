import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import async_session_factory
from app.models.hermes_skill.hermes_task import HermesTask, HermesTaskEvent, TaskStatus, EventType
from app.models.base import not_deleted
from app.services.hermes_skill.hermes_agent_adapter import HermesAgentAdapter
from app.services.hermes_skill.task_event_service import TaskEventService
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
                    task.status = TaskStatus.FAILED
                    task.error_code = "TASK_EXECUTION_ERROR"
                    task.error_message = str(exc)[:1024]
                    task.completed_at = datetime.now(timezone.utc)

                    event_service = TaskEventService(db)
                    await event_service.write_event(
                        task_id=task.id,
                        org_id=task.org_id,
                        event_type=EventType.TASK_FAILED,
                        payload={"error_code": "TASK_EXECUTION_ERROR", "error_message": str(exc)[:1024]},
                    )

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
        lock_cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.HERMES_TASK_LOCK_TIMEOUT_SECONDS)

        stmt = (
            select(HermesTask)
            .where(
                not_deleted(HermesTask),
                HermesTask.status == TaskStatus.QUEUED,
                (HermesTask.locked_at.is_(None)) | (HermesTask.locked_at < lock_cutoff),
            )
            .order_by(HermesTask.created_at.asc())
            .limit(settings.HERMES_TASK_WORKER_BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )
        result = await db.execute(stmt)
        tasks = list(result.scalars().all())

        now = datetime.now(timezone.utc)
        event_service = TaskEventService(db)
        for task in tasks:
            task.worker_id = self._worker_id
            task.locked_at = now
            task.status = TaskStatus.ACCEPTED
            task.dispatch_status = "accepted"
            task.dispatch_attempts = (task.dispatch_attempts or 0) + 1

            await event_service.write_event(
                task_id=task.id,
                org_id=task.org_id,
                event_type=EventType.TASK_ACCEPTED,
                payload={"worker_id": self._worker_id, "dispatch_attempts": task.dispatch_attempts},
            )

        await db.flush()
        return tasks

    async def _execute_task(self, db: AsyncSession, task: HermesTask):
        now = datetime.now(timezone.utc)

        task.status = TaskStatus.RUNNING
        task.run_started_at = now
        task.dispatch_status = "running"

        event_service = TaskEventService(db)
        await event_service.write_event(
            task_id=task.id,
            org_id=task.org_id,
            event_type=EventType.TASK_STARTED,
            payload={"status": "running"},
        )

        audit_logger = SkillAuditLogger(db)
        await audit_logger.log(
            action="hermes.task.started",
            target_id=task.id,
            org_id=task.org_id,
            actor_type="system",
            actor_id=self._worker_id,
            details={"task_no": task.task_no, "skill_id": task.skill_id, "tool_name": task.tool_name},
        )
        await db.flush()

        adapter = HermesAgentAdapter(db)
        try:
            run_data = await adapter.submit_run(task, task.arguments or {})
        except Exception as exc:
            task.status = TaskStatus.FAILED
            task.error_code = "AGENT_UNREACHABLE"
            task.error_message = str(exc)[:1024]
            task.completed_at = datetime.now(timezone.utc)

            await event_service.write_event(
                task_id=task.id,
                org_id=task.org_id,
                event_type=EventType.TASK_FAILED,
                payload={"error_code": "AGENT_UNREACHABLE", "error_message": str(exc)[:1024]},
            )

            task.worker_id = None
            task.locked_at = None
            task.dispatch_status = "failed"
            await db.flush()
            return

        await event_service.write_event(
            task_id=task.id,
            org_id=task.org_id,
            event_type=EventType.HERMES_RUN_CREATED,
            payload={"hermes_run_id": task.hermes_run_id},
        )
        await db.flush()

        stream_interrupted = False
        try:
            async for event_data in adapter.read_run_events(task):
                converted = HermesAgentAdapter.convert_events([event_data])
                for ce in converted:
                    await event_service.write_event(
                        task_id=task.id,
                        org_id=task.org_id,
                        event_type=ce["event_type"],
                        payload=ce["payload"],
                        event_seq=ce.get("event_seq"),
                    )
                await db.flush()
        except Exception as exc:
            logger.warning("read_run_events stream error for task %s: %s", task.id, exc)
            stream_interrupted = True

        await db.refresh(task)

        if task.status == TaskStatus.RUNNING:
            if stream_interrupted:
                try:
                    run_status = await adapter.get_run_status(task)
                    run_state = run_status.get("status", "")
                except Exception as exc:
                    logger.error("get_run_status failed for task %s: %s", task.id, exc)
                    run_state = "unknown"

                if run_state == "completed":
                    task.status = TaskStatus.COMPLETED
                    task.run_finished_at = datetime.now(timezone.utc)
                    task.completed_at = datetime.now(timezone.utc)
                elif run_state == "failed":
                    task.status = TaskStatus.FAILED
                    task.error_code = "RUN_FAILED"
                    task.error_message = "Run failed after stream interrupt"
                    task.completed_at = datetime.now(timezone.utc)
                elif run_state == "running":
                    task.worker_id = None
                    task.locked_at = None
                    task.dispatch_status = "running"
                    await db.flush()
                    return
                else:
                    task.status = TaskStatus.FAILED
                    task.error_code = "RUN_STATUS_UNKNOWN"
                    task.error_message = f"Unknown run status: {run_state}"
                    task.completed_at = datetime.now(timezone.utc)
            else:
                task.status = TaskStatus.COMPLETED
                task.run_finished_at = datetime.now(timezone.utc)
                task.completed_at = datetime.now(timezone.utc)

            if task.status == TaskStatus.COMPLETED:
                await event_service.write_event(
                    task_id=task.id,
                    org_id=task.org_id,
                    event_type=EventType.TASK_COMPLETED,
                    payload={"status": "completed"},
                )

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

                try:
                    from app.services.hermes_skill.artifact_service import ArtifactService
                    artifact_service = ArtifactService(db)
                    await artifact_service.scan_and_register(task.id, task.org_id)
                except Exception as exc:
                    logger.error("Artifact scan failed for task %s: %s", task.id, exc)

            elif task.status == TaskStatus.FAILED:
                await event_service.write_event(
                    task_id=task.id,
                    org_id=task.org_id,
                    event_type=EventType.TASK_FAILED,
                    payload={"error_code": task.error_code, "error_message": task.error_message},
                )

        task.worker_id = None
        task.locked_at = None
        task.dispatch_status = "finished"
        await db.flush()

    async def _check_timeouts(self, db: AsyncSession):
        now = datetime.now(timezone.utc)
        stmt = select(HermesTask).where(
            not_deleted(HermesTask),
            HermesTask.status == TaskStatus.RUNNING,
            HermesTask.run_started_at.isnot(None),
        )
        result = await db.execute(stmt)
        for task in result.scalars().all():
            elapsed = (now - task.run_started_at).total_seconds() if task.run_started_at else 0
            if elapsed > task.timeout_seconds:
                task.status = TaskStatus.TIMEOUT
                task.completed_at = now
                task.run_finished_at = now
                task.last_dispatch_error = "task timeout"
                task.worker_id = None
                task.locked_at = None

                event_service = TaskEventService(db)
                await event_service.write_event(
                    task_id=task.id,
                    org_id=task.org_id,
                    event_type=EventType.TASK_TIMEOUT,
                    payload={"status": "timeout", "elapsed_seconds": elapsed},
                )

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
