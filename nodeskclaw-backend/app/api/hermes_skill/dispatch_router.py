from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.run_dispatch_outbox_service import RunDispatchOutboxService

router = APIRouter(prefix="/dispatch/outbox", tags=["Hermes Dispatch Outbox"])


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.get("/stats")
async def get_outbox_stats(
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_queue:view")
    service = RunDispatchOutboxService(db)
    stats = await service.get_outbox_stats(org.id)
    return _ok(stats)


@router.get("/dead-letters")
async def list_dead_letters(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_queue:view")
    service = RunDispatchOutboxService(db)
    items, total = await service.list_dead_letters(org.id, page=page, page_size=page_size)
    return _ok(
        {
            "items": [
                {
                    "dispatch_id": item.dispatch_id,
                    "run_id": item.run_id,
                    "node_id": item.node_id,
                    "status": item.status,
                    "retry_count": item.retry_count,
                    "max_retries": item.max_retries,
                    "lease_generation": item.lease_generation,
                    "last_error": item.last_error,
                    "created_at": item.created_at.isoformat() if item.created_at else None,
                    "updated_at": item.updated_at.isoformat() if item.updated_at else None,
                }
                for item in items
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.post("/dead-letters/{dispatch_id}/replay")
async def replay_dead_letter(
    dispatch_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_queue:manage")
    service = RunDispatchOutboxService(db)
    entry = await service.replay_dead_letter(org.id, dispatch_id)
    return _ok(
        {
            "dispatch_id": entry.dispatch_id,
            "run_id": entry.run_id,
            "status": entry.status,
            "lease_generation": entry.lease_generation,
        },
        message="Dead letter replayed successfully",
    )
