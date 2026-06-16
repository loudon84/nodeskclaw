from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.services.hermes_skill.hermes_runtime_metrics_service import HermesRuntimeMetricsService
from app.services.hermes_skill.permission_checker import PermissionChecker

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.get("/metrics/runtime")
async def get_runtime_metrics(
    range: str = Query("7d", alias="range"),
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_runtime:metrics")
    service = HermesRuntimeMetricsService(db)
    return _ok(await service.get_metrics(org.id, range_key=range))
