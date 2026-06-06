import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.core.exceptions import NotFoundError, BadRequestError
from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus
from app.schemas.hermes_skill.task import TaskRead
from app.schemas.hermes_skill.artifact import ArtifactRead
from app.services.hermes_skill.task_service import TaskService
from app.services.hermes_skill.task_event_service import TaskEventService
from app.services.hermes_skill.artifact_service import ArtifactService
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
from app.services.hermes_skill.permission_checker import PermissionChecker

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_task:view")
    service = TaskService(db)
    task = await service.get_task(task_id, org.id)
    return _ok(TaskRead.model_validate(task).model_dump())


@router.get("/tasks/{task_id}/events")
async def stream_task_events(
    task_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
    last_event_id: str | None = None,
):
    from fastapi import Request
    from app.core.config import settings as _settings

    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_task:view")
    service = TaskService(db)
    await service.get_task(task_id, org.id)

    event_service = TaskEventService(db)
    from app.services.hermes_skill.event_bus import EventBus
    event_bus = EventBus.get_instance()

    last_seq = None
    if last_event_id:
        try:
            last_seq = int(last_event_id.split("-")[-1])
        except (ValueError, IndexError):
            pass

    async def _event_generator():
        from app.models.hermes_skill.hermes_task import TaskStatus

        _terminal_states = frozenset({
            TaskStatus.COMPLETED, TaskStatus.FAILED,
            TaskStatus.CANCELLED, TaskStatus.TIMEOUT,
        })

        existing_events = await event_service.get_events(task_id, org.id)
        if last_seq is not None:
            existing_events = [e for e in existing_events if e.event_seq > last_seq]

        for event in existing_events:
            data = json.dumps({
                "task_id": task_id,
                "event_type": event.event_type.value,
                "event_seq": event.event_seq,
                "payload": event.payload,
                "created_at": event.created_at.isoformat() if event.created_at else None,
            })
            yield f"id: {task_id}-{event.event_seq}\nevent: {event.event_type.value}\ndata: {data}\n\n"

        task = await db.get(HermesTask, task_id)
        if task and task.status in _terminal_states:
            return

        seen_seqs = {e.event_seq for e in existing_events}
        if last_seq is not None:
            all_events = await event_service.get_events(task_id, org.id)
            seen_seqs = {e.event_seq for e in all_events}

        heartbeat_interval = _settings.HERMES_TASK_SSE_HEARTBEAT_SECONDS

        while True:
            waited = await event_bus.wait(task_id, timeout=heartbeat_interval)

            if not waited:
                yield ": heartbeat\n\n"
                continue

            new_events = await event_service.get_events(task_id, org.id)
            for event in new_events:
                if event.event_seq in seen_seqs:
                    continue
                seen_seqs.add(event.event_seq)

                data = json.dumps({
                    "task_id": task_id,
                    "event_type": event.event_type.value,
                    "event_seq": event.event_seq,
                    "payload": event.payload,
                    "created_at": event.created_at.isoformat() if event.created_at else None,
                })
                yield f"id: {task_id}-{event.event_seq}\nevent: {event.event_type.value}\ndata: {data}\n\n"

            task = await db.get(HermesTask, task_id)
            if task and task.status in _terminal_states:
                event_bus.clear(task_id)
                return

    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/tasks/{task_id}/artifacts")
async def list_task_artifacts(
    task_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_artifact:view")
    service = ArtifactService(db)
    artifacts, _ = await service.list_artifacts(org_id=org.id, task_id=task_id, user_id=user.id if user else None)
    items = [ArtifactRead.model_validate(a).model_dump() for a in artifacts]
    return _ok(items)


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_task:cancel")
    service = TaskService(db)
    task = await service.get_task(task_id, org.id)

    cancellable = {TaskStatus.QUEUED, TaskStatus.ACCEPTED, TaskStatus.RUNNING}
    if task.status not in cancellable:
        raise BadRequestError("当前任务状态不可取消", "errors.task.cannot_cancel")

    if task.hermes_run_id:
        try:
            from app.services.hermes_skill.hermes_agent_adapter import HermesAgentAdapter
            adapter = HermesAgentAdapter(db)
            await adapter.cancel_run(task)
        except Exception:
            pass

    task = await service.update_status(task_id, org.id, TaskStatus.CANCELLED)

    audit_logger = SkillAuditLogger(db)
    await audit_logger.log(
        action="hermes.task.cancelled",
        target_id=task_id,
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"task_no": task.task_no, "skill_id": task.skill_id},
    )
    await db.commit()
    return _ok(TaskRead.model_validate(task).model_dump())


@router.post("/tasks/{task_id}/retry")
async def retry_task(
    task_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_task:create")
    service = TaskService(db)
    task = await service.get_task(task_id, org.id)

    retryable = {TaskStatus.FAILED, TaskStatus.TIMEOUT}
    if task.status not in retryable:
        raise BadRequestError("当前任务状态不可重试", "errors.task.cannot_retry")

    new_task = await service.create_task(
        org_id=org.id,
        skill_id=task.skill_id,
        tool_name=task.tool_name,
        agent_id=task.agent_id,
        profile_id=task.profile_id,
        workspace_id=task.workspace_id,
        installation_id=task.installation_id,
        user_id=user.id if user else task.user_id,
        arguments=task.arguments,
    )
    new_task.request_summary = f"retry of {task.task_no}"
    await db.flush()

    audit_logger = SkillAuditLogger(db)
    await audit_logger.log(
        action="hermes.task.created",
        target_id=new_task.id,
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"parent_task_id": task_id, "task_no": new_task.task_no},
    )
    await db.commit()
    return _ok(TaskRead.model_validate(new_task).model_dump())
