from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.schemas.hermes_skill.artifact_audit_schema import ArtifactAuditLogItem
from app.services.hermes_skill.artifact_audit_service import ArtifactAuditService
from app.services.hermes_skill.permission_checker import PermissionChecker

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.get("/artifacts/audit")
async def query_artifact_audit(
    action: str | None = Query(None),
    actor_id: str | None = Query(None),
    target_id: str | None = Query(None),
    start_time: str | None = Query(None),
    end_time: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_artifact:view")
    service = ArtifactAuditService(db)

    from datetime import datetime
    st = datetime.fromisoformat(start_time) if start_time else None
    et = datetime.fromisoformat(end_time) if end_time else None

    logs, total = await service.query_audit_logs(
        org_id=org.id,
        action=action,
        actor_id=actor_id,
        target_id=target_id,
        start_time=st,
        end_time=et,
        page=page,
        page_size=page_size,
    )
    items = [ArtifactAuditLogItem.model_validate(log).model_dump() for log in logs]
    return _ok({"items": items, "total": total, "page": page, "page_size": page_size})
