"""Worker dispatch: lease, events, finish."""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.automation_task import AutomationTask
from app.models.base import not_deleted
from app.models.enums import RunEventType, RunStatus, TaskStatus, WorkerStatus
from app.models.rpa_run import RpaRun
from app.models.rpa_worker import RpaWorker
from app.models.run_event import RunEvent
from app.models.step_run import StepRun
from app.models.worker_lease import WorkerLease
from app.models.workflow_binding import WorkflowBinding
from app.schemas.dispatch import (
    RunArtifactCreate,
    RunEventCreate,
    RunFinishRequest,
    WorkerLeaseRenewRequest,
    WorkerLeaseRequest,
    WorkerLeaseResponse,
)
from app.services.artifact_service import create_artifact_record
from app.services.automation_task_service import task_input_dict
from app.services.human_action_service import create_human_action_for_run
from app.services.json_utils import dumps_json
from app.services.rpa_worker_service import get_worker
from app.services.task_state_machine import transition


async def _expire_stale_leases(db: AsyncSession) -> None:
    now = datetime.now(UTC)
    stale_leases = (
        await db.execute(
            select(WorkerLease).where(
                WorkerLease.lease_expires_at < now,
                not_deleted(WorkerLease),
            )
        )
    ).scalars().all()
    for lease in stale_leases:
        task = (
            await db.execute(
                select(AutomationTask).where(AutomationTask.id == lease.task_id, not_deleted(AutomationTask))
            )
        ).scalar_one_or_none()
        if task and task.status == TaskStatus.LEASED:
            transition(task, TaskStatus.QUEUED)
        lease.soft_delete()
    if stale_leases:
        await db.flush()


async def lease_task(db: AsyncSession, body: WorkerLeaseRequest) -> WorkerLeaseResponse | None:
    await _expire_stale_leases(db)
    worker = await get_worker(db, body.worker_id)

    stmt = (
        select(AutomationTask)
        .where(
            AutomationTask.status == TaskStatus.QUEUED,
            not_deleted(AutomationTask),
        )
        .order_by(AutomationTask.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(body.limit)
    )
    tasks = (await db.execute(stmt)).scalars().all()
    if not tasks:
        return None

    task = tasks[0]
    binding = (
        await db.execute(
            select(WorkflowBinding).where(
                WorkflowBinding.id == task.workflow_binding_id,
                not_deleted(WorkflowBinding),
            )
        )
    ).scalar_one_or_none()
    if binding is None:
        raise NotFoundError(message="工作流绑定不存在", message_key="errors.autotask.binding_not_found")

    run = (
        await db.execute(
            select(RpaRun)
            .where(RpaRun.task_id == task.id, RpaRun.status == RunStatus.QUEUED, not_deleted(RpaRun))
            .order_by(RpaRun.created_at.desc())
        )
    ).scalar_one_or_none()
    if run is None:
        run = RpaRun(task_id=task.id, rpa_flow_id=binding.rpa_flow_id, status=RunStatus.QUEUED)
        db.add(run)
        await db.flush()

    lease_id = str(uuid.uuid4())
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.WORKER_LEASE_TTL_SECONDS)
    transition(task, TaskStatus.LEASED)
    run.status = RunStatus.QUEUED
    run.lease_id = lease_id
    run.rpa_worker_id = body.worker_id
    worker.status = WorkerStatus.BUSY
    worker.current_run_id = run.id
    db.add(
        WorkerLease(
            task_id=task.id,
            run_id=run.id,
            worker_id=body.worker_id,
            lease_id=lease_id,
            lease_expires_at=expires_at,
        )
    )
    db.add(
        RunEvent(
            run_id=run.id,
            task_id=task.id,
            worker_id=body.worker_id,
            type=RunEventType.RUN_STARTED,
            level="INFO",
            message="任务已被 Worker 领取",
            payload=dumps_json({"leaseId": lease_id}),
        )
    )
    transition(task, TaskStatus.RUNNING)
    run.status = RunStatus.RUNNING
    run.started_at = datetime.now(UTC)
    await db.commit()

    return WorkerLeaseResponse(
        task_id=task.id,
        run_id=run.id,
        lease_id=lease_id,
        workflow_binding_id=task.workflow_binding_id,
        portal_account_id=task.portal_account_id,
        rpa_flow_id=binding.rpa_flow_id,
        input=task_input_dict(task),
    )


async def renew_lease(db: AsyncSession, task_id: str, body: WorkerLeaseRenewRequest) -> None:
    lease = (
        await db.execute(
            select(WorkerLease).where(
                WorkerLease.task_id == task_id,
                WorkerLease.worker_id == body.worker_id,
                WorkerLease.lease_id == body.lease_id,
                not_deleted(WorkerLease),
            )
        )
    ).scalar_one_or_none()
    if lease is None:
        raise NotFoundError(message="Lease 不存在", message_key="errors.autotask.lease_not_found")
    lease.lease_expires_at = datetime.now(UTC) + timedelta(seconds=settings.WORKER_LEASE_TTL_SECONDS)
    await db.commit()


async def append_run_event(db: AsyncSession, run_id: str, body: RunEventCreate) -> RunEvent:
    run = (
        await db.execute(select(RpaRun).where(RpaRun.id == run_id, not_deleted(RpaRun)))
    ).scalar_one_or_none()
    if run is None:
        raise NotFoundError(message="Run 不存在", message_key="errors.autotask.run_not_found")

    task = (
        await db.execute(select(AutomationTask).where(AutomationTask.id == run.task_id, not_deleted(AutomationTask)))
    ).scalar_one_or_none()
    if task is None:
        raise NotFoundError(message="任务不存在", message_key="errors.autotask.task_not_found")

    event = RunEvent(
        run_id=run.id,
        task_id=task.id,
        worker_id=body.worker_id,
        type=body.type,
        level=body.level,
        message=body.message,
        payload=dumps_json(body.payload or {}),
    )
    db.add(event)

    if body.type == RunEventType.STEP_STARTED:
        db.add(StepRun(run_id=run.id, step_id=body.payload.get("stepId", "unknown") if body.payload else "unknown", status="RUNNING"))
        run.current_step_id = body.payload.get("stepId") if body.payload else None
        task.current_step = run.current_step_id
    elif body.type == RunEventType.STEP_SUCCEEDED:
        step_id = body.payload.get("stepId") if body.payload else None
        if step_id:
            step = (
                await db.execute(
                    select(StepRun).where(StepRun.run_id == run.id, StepRun.step_id == step_id, not_deleted(StepRun))
                )
            ).scalar_one_or_none()
            if step:
                step.status = "SUCCESS"
    elif body.type == RunEventType.WAITING_HUMAN:
        transition(task, TaskStatus.WAITING_HUMAN)
        run.status = RunStatus.WAITING_HUMAN
        await create_human_action_for_run(
            db,
            task=task,
            run=run,
            action_type=body.payload.get("type", "MANUAL_CONFIRM") if body.payload else "MANUAL_CONFIRM",
            title=body.payload.get("title", "需要人工处理") if body.payload else "需要人工处理",
            instruction=body.message,
            target_url=body.payload.get("targetUrl") if body.payload else None,
            payload=body.payload,
        )

    await db.commit()
    await db.refresh(event)
    return event


async def append_run_artifact(db: AsyncSession, run_id: str, body: RunArtifactCreate, created_by: str | None) -> None:
    run = (
        await db.execute(select(RpaRun).where(RpaRun.id == run_id, not_deleted(RpaRun)))
    ).scalar_one_or_none()
    if run is None:
        raise NotFoundError(message="Run 不存在", message_key="errors.autotask.run_not_found")
    task = (
        await db.execute(select(AutomationTask).where(AutomationTask.id == run.task_id, not_deleted(AutomationTask)))
    ).scalar_one_or_none()
    if task is None:
        raise NotFoundError(message="任务不存在", message_key="errors.autotask.task_not_found")

    await create_artifact_record(
        db,
        tenant_id=task.tenant_id,
        task_id=task.id,
        run_id=run.id,
        artifact_type=body.type,
        name=body.name,
        storage_key=body.storage_key,
        size=body.size,
        mime_type=body.mime_type,
        created_by=created_by,
    )
    db.add(
        RunEvent(
            run_id=run.id,
            task_id=task.id,
            type=RunEventType.ARTIFACT_SAVED,
            level="INFO",
            message=f"Artifact 已保存: {body.name}",
            payload=dumps_json({"storageKey": body.storage_key}),
        )
    )
    await db.commit()


async def finish_run(db: AsyncSession, run_id: str, body: RunFinishRequest) -> RpaRun:
    run = (
        await db.execute(select(RpaRun).where(RpaRun.id == run_id, not_deleted(RpaRun)))
    ).scalar_one_or_none()
    if run is None:
        raise NotFoundError(message="Run 不存在", message_key="errors.autotask.run_not_found")
    task = (
        await db.execute(select(AutomationTask).where(AutomationTask.id == run.task_id, not_deleted(AutomationTask)))
    ).scalar_one_or_none()
    if task is None:
        raise NotFoundError(message="任务不存在", message_key="errors.autotask.task_not_found")

    run.status = body.status
    run.ended_at = datetime.now(UTC)
    run.error_code = body.error_code
    run.error_message = body.error_message

    if body.status == RunStatus.SUCCESS:
        transition(task, TaskStatus.SUCCESS)
        task.progress = 100
        event_type = RunEventType.RUN_SUCCEEDED
    elif body.status == RunStatus.FAILED:
        transition(task, TaskStatus.FAILED)
        event_type = RunEventType.RUN_FAILED
    elif body.status == RunStatus.CANCELLED:
        transition(task, TaskStatus.CANCELLED)
        event_type = RunEventType.RUN_CANCELLED
    else:
        raise BadRequestError(message="不支持的 Run 完成状态", message_key="errors.autotask.invalid_run_status")

    worker = None
    if run.rpa_worker_id:
        worker = (
            await db.execute(
                select(RpaWorker).where(RpaWorker.worker_id == run.rpa_worker_id, not_deleted(RpaWorker))
            )
        ).scalar_one_or_none()
    if worker:
        worker.current_run_id = None
        worker.status = WorkerStatus.ONLINE

    leases = (
        await db.execute(
            select(WorkerLease).where(WorkerLease.run_id == run.id, not_deleted(WorkerLease))
        )
    ).scalars().all()
    for lease in leases:
        lease.soft_delete()

    db.add(
        RunEvent(
            run_id=run.id,
            task_id=task.id,
            worker_id=run.rpa_worker_id,
            type=event_type,
            level="INFO" if body.status == RunStatus.SUCCESS else "ERROR",
            message=body.error_message or f"Run 已完成: {body.status}",
            payload=dumps_json({"status": body.status}),
        )
    )
    await db.commit()
    await db.refresh(run)
    return run
