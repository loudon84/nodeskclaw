from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.runtime_diagnostics_service import RuntimeDiagnosticsService
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.get("/diagnostics/runtime")
async def get_runtime_diagnostics(
    include_unbound: bool = Query(default=False),
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_runtime:diagnostics")

    include_unbound_effective = include_unbound
    if include_unbound and user:
        can_view_unbound = await PermissionChecker.has_permission(
            db, user.id, org.id, "hermes_agent:manage",
        )
        if not can_view_unbound:
            include_unbound_effective = False

    service = RuntimeDiagnosticsService(db)
    payload = await service.get_runtime_diagnostics(org.id, include_unbound=include_unbound_effective)

    if user:
        audit = SkillAuditLogger(db)
        await audit.log(
            action="hermes.runtime.diagnostics.viewed",
            target_id=org.id,
            org_id=org.id,
            actor_id=user.id,
            details={"queue_running": payload["queue"].get("running")},
        )
        await db.commit()

    return _ok(payload)
