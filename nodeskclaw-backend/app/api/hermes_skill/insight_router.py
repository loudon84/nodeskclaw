from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.hermes_skill._agent_profile_context import host_dir_from_agent, require_agent_record
from app.core.deps import get_db, require_org_member
from app.services.hermes_external.insight.service import HermesInsightService
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger

router = APIRouter()
_insight_service = HermesInsightService()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.get("/agents/{profile_name}/insight")
async def get_hermes_agent_insight(
    profile_name: str,
    profile: str = Query(default="all"),
    refresh: bool = Query(default=False),
    days: int | None = Query(default=None),
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:view")
    record = await require_agent_record(db, org.id, profile_name)
    host_data_dir, record, instance = await host_dir_from_agent(db, org.id, profile_name, record)

    result = await _insight_service.get_insight(
        agent_profile_name=profile_name,
        host_data_dir=host_data_dir,
        record=record,
        instance=instance,
        profile=profile,
        refresh=refresh,
        ignore_days_param=days is not None,
    )

    audit = SkillAuditLogger(db)
    await audit.log(
        action="hermes.insight.get",
        target_id=profile_name,
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"profile": profile, "refresh": refresh, "scope": result.scope},
    )
    await db.commit()
    return _ok(result.model_dump())
