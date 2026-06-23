import asyncio
import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.core.exceptions import NotFoundError, BadRequestError, ForbiddenError
from app.models.hermes_skill.hermes_task import HermesTask, TaskStatus, EventType
from app.schemas.hermes_skill.task import TaskRead
from app.schemas.hermes_skill.artifact import ArtifactRead
from app.schemas.hermes_skill.artifact_rescan import (
    ArtifactRescanRequest,
    ArtifactRescanResponse,
    ArtifactRescanItem,
)
from app.services.hermes_skill.task_service import TaskService
from app.services.hermes_skill.task_event_service import TaskEventService
from app.services.hermes_skill.artifact_service import ArtifactService
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.hermes_runtime_control_service import HermesRuntimeControlService
from app.services.hermes_skill.hermes_queue_policy_service import HermesQueuePolicyService

router = APIRouter()

_EVENT_TITLES: dict[str, str] = {
    EventType.TASK_CREATED.value: "任务创建",
    EventType.TASK_QUEUED.value: "任务入队",
    EventType.TASK_ACCEPTED.value: "任务已接受",
    EventType.TASK_STARTED.value: "任务开始",
    EventType.TASK_RETRYING.value: "任务重试",
    EventType.TASK_CANCEL_REQUESTED.value: "取消请求",
    EventType.TASK_COMPLETED.value: "任务完成",
    EventType.TASK_FAILED.value: "任务失败",
    EventType.TASK_CANCELLED.value: "任务已取消",
    EventType.TASK_TIMEOUT.value: "任务超时",
    EventType.HERMES_RUN_CREATED.value: "Hermes Run 创建",
    EventType.HERMES_RUN_STARTED.value: "Hermes Run 开始",
    EventType.HERMES_RUN_DELTA.value: "Hermes Run 增量",
    EventType.HERMES_RUN_COMPLETED.value: "Hermes Run 完成",
    EventType.HERMES_RUN_FAILED.value: "Hermes Run 失败",
    EventType.ARTIFACT_SCAN_STARTED.value: "产物扫描开始",
    EventType.ARTIFACT_CREATED.value: "产物创建",
    EventType.ARTIFACT_SCAN_COMPLETED.value: "产物扫描完成",
    EventType.ARTIFACT_SCAN_FAILED.value: "产物扫描失败",
}


def _unwrap_event_payload(payload: dict | None) -> dict:
    if not payload:
        return {}
    if payload.get("source") == "hermes" and isinstance(payload.get("payload"), dict):
        inner = dict(payload["payload"])
        if payload.get("hermes_event_seq") is not None:
            inner["hermes_event_seq"] = payload["hermes_event_seq"]
        return inner
    return payload


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.get("/tasks")
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    skill_id: str | None = Query(None),
    tool_name: str | None = Query(None),
    agent_id: str | None = Query(None),
    profile_id: str | None = Query(None),
    workspace_id: str | None = Query(None),
    user_id: str | None = Query(None),
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_task:view")

    filter_user_id = user_id
    if user and not filter_user_id:
        from sqlalchemy import select
        from app.models.org_membership import OrgMembership, OrgRole
        from app.models.base import not_deleted
        role_result = await db.execute(
            select(OrgMembership.role).where(
                OrgMembership.user_id == user.id,
                OrgMembership.org_id == org.id,
                not_deleted(OrgMembership),
            )
        )
        org_role = role_result.scalar_one_or_none()
        if org_role not in (OrgRole.admin, OrgRole.operator):
            filter_user_id = user.id

    service = TaskService(db)
    items, total = await service.list_tasks(
        org_id=org.id,
        skill_id=skill_id,
        status=status,
        tool_name=tool_name,
        agent_id=agent_id,
        profile_id=profile_id,
        workspace_id=workspace_id,
        user_id=filter_user_id,
        page=page,
        page_size=page_size,
    )
    payload = [TaskRead.model_validate(item).model_dump() for item in items]
    return _ok({"items": payload, "total": total, "page": page, "page_size": page_size})


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


@router.get("/tasks/{task_id}/timeline")
async def get_task_timeline(
    task_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_task:view")
    task_service = TaskService(db)
    task = await task_service.get_task(task_id, org.id)
    event_service = TaskEventService(db)
    events = await event_service.get_events(task_id, org.id)
    items = []
    for event in events:
        payload = _unwrap_event_payload(event.payload)
        items.append({
            "event_seq": event.event_seq,
            "event_type": event.event_type.value,
            "title": _EVENT_TITLES.get(event.event_type.value, event.event_type.value),
            "timestamp": event.created_at.isoformat() if event.created_at else None,
            "payload": payload,
        })
    return _ok({
        "task_id": task.id,
        "task_no": task.task_no,
        "status": task.status.value if hasattr(task.status, "value") else task.status,
        "items": items,
    })


@router.get("/tasks/{task_id}/events")
async def stream_task_events(
    task_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: str | None = Query(None),
    last_event_id: str | None = None,
):
    from app.core.config import settings as _settings
    from app.core.security import get_current_user
    from app.services.hermes_skill.task_event_token_service import TaskEventTokenService

    service = TaskService(db)
    authorization = request.headers.get("authorization")
    org_id: str

    if authorization:
        user = await get_current_user(request=request, db=db)
        from app.services.org.factory import get_org_provider
        org = await get_org_provider().resolve_org_for_user(user, db)
        if org is None:
            raise ForbiddenError("用户未加入任何组织", "errors.org.user_has_no_org")
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_task:view")
        await service.get_task(task_id, org.id)
        org_id = org.id
    elif token:
        token_service = TaskEventTokenService(db)
        valid, token_user_id, token_org_id = await token_service.verify_token(token, task_id)
        if not valid or not token_org_id:
            raise ForbiddenError("SSE token 无效或已过期", "errors.task.events_token_invalid")
        task = await service.get_task(task_id, token_org_id)
        org_id = token_org_id
        if token_user_id and task.user_id and token_user_id != task.user_id:
            raise ForbiddenError("SSE token 无权访问该任务", "errors.task.events_token_forbidden")
    else:
        raise ForbiddenError("需要认证或 SSE token", "errors.auth.unauthorized")

    event_service = TaskEventService(db)
    from app.services.hermes_skill.event_bus import EventBus
    event_bus = EventBus.get_instance()

    last_seq = None
    header_last = request.headers.get("Last-Event-ID") or request.headers.get("last-event-id")
    resume_id = header_last or last_event_id
    if resume_id:
        try:
            last_seq = int(resume_id.split("-")[-1])
        except (ValueError, IndexError):
            pass

    async def _event_generator():
        from app.models.hermes_skill.hermes_task import TaskStatus

        _terminal_states = frozenset({
            TaskStatus.COMPLETED, TaskStatus.FAILED,
            TaskStatus.CANCELLED, TaskStatus.TIMEOUT,
        })

        existing_events = await event_service.get_events(task_id, org_id, start_after_seq=last_seq)

        for event in existing_events:
            payload = _unwrap_event_payload(event.payload)
            data = json.dumps({
                "task_id": task_id,
                "event_type": event.event_type.value,
                "event_seq": event.event_seq,
                "payload": payload,
                "hermes_event_seq": payload.get("hermes_event_seq"),
                "created_at": event.created_at.isoformat() if event.created_at else None,
            })
            yield f"id: {task_id}-{event.event_seq}\nevent: {event.event_type.value}\ndata: {data}\n\n"

        task = await db.get(HermesTask, task_id)
        if task and task.status in _terminal_states:
            return

        seen_seqs = {e.event_seq for e in existing_events}
        if last_seq is not None:
            all_events = await event_service.get_events(task_id, org_id)
            seen_seqs = {e.event_seq for e in all_events}

        heartbeat_interval = _settings.HERMES_TASK_SSE_HEARTBEAT_SECONDS

        while True:
            waited = await event_bus.wait(task_id, timeout=heartbeat_interval)

            if not waited:
                yield ": heartbeat\n\n"
                continue

            new_events = await event_service.get_events(task_id, org_id)
            for event in new_events:
                if event.event_seq in seen_seqs:
                    continue
                seen_seqs.add(event.event_seq)

                payload = _unwrap_event_payload(event.payload)
                data = json.dumps({
                    "task_id": task_id,
                    "event_type": event.event_type.value,
                    "event_seq": event.event_seq,
                    "payload": payload,
                    "hermes_event_seq": payload.get("hermes_event_seq"),
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


async def _assert_can_rescan_task_artifacts(
    db: AsyncSession,
    task: HermesTask,
    user_id: str,
    org_id: str,
) -> None:
    if task.user_id and task.user_id == user_id:
        return
    from sqlalchemy import select
    from app.models.org_membership import OrgMembership, OrgRole
    from app.models.base import not_deleted
    role_result = await db.execute(
        select(OrgMembership.role).where(
            OrgMembership.user_id == user_id,
            OrgMembership.org_id == org_id,
            not_deleted(OrgMembership),
        )
    )
    org_role = role_result.scalar_one_or_none()
    if org_role in (OrgRole.admin, OrgRole.operator):
        return
    raise ForbiddenError("无权重新扫描该任务产物", "errors.hermes.artifact_rescan_forbidden")


@router.post("/tasks/{task_id}/artifacts/rescan")
async def rescan_task_artifacts(
    task_id: str,
    body: ArtifactRescanRequest | None = None,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if not user:
        raise ForbiddenError("需要登录", "errors.auth.unauthorized")
    await PermissionChecker.require_permission(db, user.id, org.id, "hermes_task:view")

    task_service = TaskService(db)
    task = await task_service.get_task(task_id, org.id)
    await _assert_can_rescan_task_artifacts(db, task, user.id, org.id)

    if task.status != TaskStatus.COMPLETED:
        raise BadRequestError("仅已完成任务可重新扫描产物", "errors.hermes.artifact_rescan_not_completed")

    from app.services.hermes_skill.artifact_discovery_service import ArtifactDiscoveryService

    force = body.force if body else False
    artifacts = await ArtifactDiscoveryService(db).discover_and_register_for_task(
        task=task,
        result_text=None,
        force_rescan=force,
    )
    await db.commit()

    items = [
        ArtifactRescanItem(
            id=a.id,
            filename=a.file_name,
            artifact_type=a.artifact_type,
            mime_type=a.content_type,
            relative_path=a.relative_path,
            size_bytes=a.size_bytes,
        )
        for a in artifacts
    ]
    response = ArtifactRescanResponse(
        task_id=task_id,
        artifact_count=len(items),
        artifacts=items,
    )
    if not items:
        response.warning = "No artifact path found in task result_summary."
    return _ok(response.model_dump())


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

    event_service = TaskEventService(db)
    if task.status in {TaskStatus.QUEUED, TaskStatus.ACCEPTED}:
        await event_service.write_event(
            task_id=task_id,
            org_id=org.id,
            event_type=EventType.TASK_CANCEL_REQUESTED,
            payload={"requested_by": user.id if user else None},
        )

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
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_task:retry")
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
        action="hermes.task.retried",
        target_id=new_task.id,
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"parent_task_id": task_id, "task_no": new_task.task_no},
    )
    await db.commit()
    return _ok(TaskRead.model_validate(new_task).model_dump())


class TaskPriorityBody(BaseModel):
    priority: int


class TaskMarkFailedBody(BaseModel):
    error_code: str = "MANUAL_FAILED"
    error_message: str = "Marked failed by operator"


@router.post("/tasks/{task_id}/requeue")
async def requeue_task(
    task_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_queue:requeue")
    service = TaskService(db)
    task = await service.get_task(task_id, org.id)
    control = HermesRuntimeControlService(db)
    await control.requeue_task(task, actor_id=user.id if user else None)
    audit_logger = SkillAuditLogger(db)
    await audit_logger.log(
        action="hermes.task.requeued",
        target_id=task_id,
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"task_no": task.task_no},
    )
    await db.commit()
    return _ok(TaskRead.model_validate(task).model_dump())


@router.post("/tasks/{task_id}/priority")
async def set_task_priority(
    task_id: str,
    body: TaskPriorityBody,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_queue:manage")
    service = TaskService(db)
    task = await service.get_task(task_id, org.id)
    policy = HermesQueuePolicyService(db)
    await policy.set_priority(task, body.priority)
    audit_logger = SkillAuditLogger(db)
    await audit_logger.log(
        action="hermes.task.priority_changed",
        target_id=task_id,
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"priority": body.priority},
    )
    await db.commit()
    return _ok(TaskRead.model_validate(task).model_dump())


@router.post("/tasks/{task_id}/mark-failed")
async def mark_task_failed(
    task_id: str,
    body: TaskMarkFailedBody,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_queue:manage")
    service = TaskService(db)
    task = await service.get_task(task_id, org.id)
    control = HermesRuntimeControlService(db)
    await control.mark_task_failed(
        task,
        body.error_code,
        body.error_message,
        actor_id=user.id if user else None,
    )
    audit_logger = SkillAuditLogger(db)
    await audit_logger.log(
        action="hermes.task.marked_failed",
        target_id=task_id,
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"error_code": body.error_code},
    )
    await db.commit()
    return _ok(TaskRead.model_validate(task).model_dump())
