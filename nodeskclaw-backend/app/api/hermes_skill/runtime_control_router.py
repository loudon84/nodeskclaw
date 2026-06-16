from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.schemas.hermes_skill.task import TaskRead
from app.services.hermes_skill.hermes_runtime_control_service import HermesRuntimeControlService
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
from app.services.hermes_skill.task_service import TaskService

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


class ControlReasonBody(BaseModel):
    reason: str | None = None


@router.get("/runtime/controls")
async def get_runtime_controls(
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_runtime:diagnostics")
    service = HermesRuntimeControlService(db)
    return _ok(await service.get_controls(org.id))


@router.post("/runtime/worker/pause")
async def pause_worker(
    body: ControlReasonBody,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_runtime:control")
    service = HermesRuntimeControlService(db)
    result = await service.pause_worker(org.id, body.reason, user.id if user else None)
    audit = SkillAuditLogger(db)
    await audit.log(action="hermes.runtime.worker.paused", target_id=org.id, org_id=org.id, actor_id=user.id if user else "")
    await db.commit()
    return _ok(result)


@router.post("/runtime/worker/resume")
async def resume_worker(
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_runtime:control")
    service = HermesRuntimeControlService(db)
    result = await service.resume_worker(org.id, user.id if user else None)
    audit = SkillAuditLogger(db)
    await audit.log(action="hermes.runtime.worker.resumed", target_id=org.id, org_id=org.id, actor_id=user.id if user else "")
    await db.commit()
    return _ok(result)


@router.post("/runtime/queue/pause")
async def pause_runtime_queue(
    body: ControlReasonBody,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_runtime:control")
    service = HermesRuntimeControlService(db)
    result = await service.pause_queue(org.id, body.reason, user.id if user else None)
    audit = SkillAuditLogger(db)
    await audit.log(action="hermes.runtime.queue.paused", target_id=org.id, org_id=org.id, actor_id=user.id if user else "")
    await db.commit()
    return _ok(result)


@router.post("/runtime/queue/resume")
async def resume_runtime_queue(
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_runtime:control")
    service = HermesRuntimeControlService(db)
    result = await service.resume_queue(org.id, user.id if user else None)
    audit = SkillAuditLogger(db)
    await audit.log(action="hermes.runtime.queue.resumed", target_id=org.id, org_id=org.id, actor_id=user.id if user else "")
    await db.commit()
    return _ok(result)


@router.post("/runtime/locks/clear-stale")
async def clear_stale_locks(
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_runtime:control")
    service = HermesRuntimeControlService(db)
    result = await service.clear_stale_locks(org.id)
    audit = SkillAuditLogger(db)
    await audit.log(
        action="hermes.runtime.locks.cleared",
        target_id=org.id,
        org_id=org.id,
        actor_id=user.id if user else "",
        details=result,
    )
    await db.commit()
    return _ok(result)


@router.post("/runtime/tasks/{task_id}/requeue")
async def requeue_runtime_task(
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
    await audit.log(action="hermes.task.requeued", target_id=task_id, org_id=org.id, actor_id=user.id if user else "")
    await db.commit()
    return _ok(TaskRead.model_validate(task).model_dump())


@router.post("/runtime/tasks/{task_id}/mark-failed")
async def mark_failed_runtime_task(
    task_id: str,
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
        "MANUAL_FAILED",
        "Marked failed by operator",
        actor_id=user.id if user else None,
    )
    audit = SkillAuditLogger(db)
    await audit.log(action="hermes.task.marked_failed", target_id=task_id, org_id=org.id, actor_id=user.id if user else "")
    await db.commit()
    return _ok(TaskRead.model_validate(task).model_dump())
