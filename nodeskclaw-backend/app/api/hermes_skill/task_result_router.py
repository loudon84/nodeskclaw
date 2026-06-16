from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
from app.services.hermes_skill.task_event_token_service import TaskEventTokenService
from app.services.hermes_skill.task_result_service import TaskResultService

router = APIRouter(tags=["Hermes Task Result"])


def _ok(data=None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.post("/tasks/{task_id}/events-token")
async def create_task_events_token(
    task_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "hermes_task:view")
    service = TaskEventTokenService(db)
    data = await service.create_token(task_id, user.id, org.id)
    audit = SkillAuditLogger(db)
    await audit.log(
        action="hermes.task.events_token.created",
        target_id=task_id,
        org_id=org.id,
        actor_id=user.id,
        details={"task_id": task_id},
    )
    await db.commit()
    return _ok(data)


@router.get("/tasks/{task_id}/result")
async def get_task_result(
    task_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "hermes_task:view")
    await PermissionChecker.require_permission(db, user.id, org.id, "hermes_artifact:view")
    service = TaskResultService(db)
    data = await service.get_result(task_id, org.id)
    audit = SkillAuditLogger(db)
    await audit.log(
        action="hermes.task.result.viewed",
        target_id=task_id,
        org_id=org.id,
        actor_id=user.id,
        details={"task_id": task_id},
    )
    return _ok(data)
