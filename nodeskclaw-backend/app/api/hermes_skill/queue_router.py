from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.schemas.hermes_skill.task import TaskRead
from app.services.hermes_skill.hermes_queue_policy_service import HermesQueuePolicyService
from app.services.hermes_skill.hermes_runtime_control_service import HermesRuntimeControlService
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
from app.services.hermes_skill.task_service import TaskService

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


class PriorityBody(BaseModel):
    priority: int


class MarkFailedBody(BaseModel):
    error_code: str = "MANUAL_FAILED"
    error_message: str = "Marked failed by operator"


@router.get("/queue/stats")
async def queue_stats(
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_queue:view")
    service = HermesQueuePolicyService(db)
    return _ok(await service.get_queue_stats(org.id))


@router.get("/queue/tasks")
async def list_queue_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    agent_id: str | None = Query(None),
    skill_id: str | None = Query(None),
    user_id: str | None = Query(None),
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_queue:view")
    service = HermesQueuePolicyService(db)
    items, total = await service.list_queue_tasks(
        org.id,
        status=status,
        agent_id=agent_id,
        skill_id=skill_id,
        user_id=user_id,
        page=page,
        page_size=page_size,
    )
    payload = [TaskRead.model_validate(item).model_dump() for item in items]
    return _ok({"items": payload, "total": total, "page": page, "page_size": page_size})


@router.post("/queue/tasks/{task_id}/priority")
async def set_task_priority(
    task_id: str,
    body: PriorityBody,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_queue:manage")
    task_service = TaskService(db)
    task = await task_service.get_task(task_id, org.id)
    policy = HermesQueuePolicyService(db)
    await policy.set_priority(task, body.priority)
    audit = SkillAuditLogger(db)
    await audit.log(
        action="hermes.task.priority_changed",
        target_id=task_id,
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"priority": body.priority},
    )
    await db.commit()
    return _ok(TaskRead.model_validate(task).model_dump())


@router.post("/queue/tasks/{task_id}/requeue")
async def requeue_queue_task(
    task_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_queue:requeue")
    task_service = TaskService(db)
    task = await task_service.get_task(task_id, org.id)
    control = HermesRuntimeControlService(db)
    await control.requeue_task(task, actor_id=user.id if user else None)
    audit = SkillAuditLogger(db)
    await audit.log(
        action="hermes.task.requeued",
        target_id=task_id,
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"task_no": task.task_no},
    )
    await db.commit()
    return _ok(TaskRead.model_validate(task).model_dump())


@router.post("/queue/tasks/{task_id}/mark-failed")
async def mark_failed_queue_task(
    task_id: str,
    body: MarkFailedBody,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_queue:manage")
    task_service = TaskService(db)
    task = await task_service.get_task(task_id, org.id)
    control = HermesRuntimeControlService(db)
    await control.mark_task_failed(
        task,
        body.error_code,
        body.error_message,
        actor_id=user.id if user else None,
    )
    audit = SkillAuditLogger(db)
    await audit.log(
        action="hermes.task.marked_failed",
        target_id=task_id,
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"error_code": body.error_code},
    )
    await db.commit()
    return _ok(TaskRead.model_validate(task).model_dump())
