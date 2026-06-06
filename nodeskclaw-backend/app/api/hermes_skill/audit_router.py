from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.models.operation_audit_log import OperationAuditLog

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.get("/skills/audit")
async def list_skill_audit(
    action: str | None = None,
    skill_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    query = select(OperationAuditLog).where(
        OperationAuditLog.target_type == "hermes_skill",
        OperationAuditLog.org_id == org.id,
    )
    count_query = select(func.count()).select_from(OperationAuditLog).where(
        OperationAuditLog.target_type == "hermes_skill",
        OperationAuditLog.org_id == org.id,
    )

    if action:
        query = query.where(OperationAuditLog.action == action)
        count_query = count_query.where(OperationAuditLog.action == action)

    total = (await db.execute(count_query)).scalar() or 0
    offset = (page - 1) * page_size
    query = query.order_by(OperationAuditLog.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    items = [
        {
            "id": log.id,
            "action": log.action,
            "target_id": log.target_id,
            "actor_type": log.actor_type,
            "actor_id": log.actor_id,
            "details": log.details,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in result.scalars().all()
    ]

    return _ok({"items": items, "total": total, "page": page, "page_size": page_size})
