from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.services.hermes_external.hermes_bound_agent_scope_service import HermesBoundAgentScopeService
from app.services.hermes_skill.hermes_agent_runtime_service import HermesAgentRuntimeService
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger

router = APIRouter()


def _ok(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


class MaintenanceBody(BaseModel):
    reason: str | None = None


async def _resolve_bound_only(
    db: AsyncSession,
    user,
    org,
    bound_only: bool,
) -> bool:
    if bound_only:
        return True
    if user and await PermissionChecker.has_permission(
        db, user.id, org.id, "hermes_agent:manage",
    ):
        return False
    return True


@router.get("/agents/runtime")
async def list_agent_runtime(
    bound_only: bool = Query(default=True),
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:view")
    bound_only_effective = await _resolve_bound_only(db, user, org, bound_only)
    service = HermesAgentRuntimeService(db)
    items = await service.list_runtime_states(org.id, bound_only=bound_only_effective)
    return _ok(items)


@router.get("/agents/{agent_id}/runtime")
async def get_agent_runtime(
    agent_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:view")
    await HermesBoundAgentScopeService(db).assert_bound_instance(org.id, agent_id)
    service = HermesAgentRuntimeService(db)
    return _ok(await service.get_runtime_state(org.id, agent_id, require_bound=False))


@router.post("/agents/{agent_id}/health-check")
async def agent_health_check(
    agent_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:health_check")
    await HermesBoundAgentScopeService(db).assert_bound_instance(org.id, agent_id)
    service = HermesAgentRuntimeService(db)
    result = await service.health_check(org.id, agent_id, actor_id=user.id if user else None)
    audit = SkillAuditLogger(db)
    await audit.log(
        action="hermes.agent.health_check",
        target_id=agent_id,
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"ok": result.get("ok")},
    )
    await db.commit()
    return _ok(result)


@router.post("/agents/{agent_id}/enable")
async def enable_agent(
    agent_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    await HermesBoundAgentScopeService(db).assert_bound_instance(org.id, agent_id)
    service = HermesAgentRuntimeService(db)
    await service.enable(org.id, agent_id, actor_id=user.id if user else None)
    audit = SkillAuditLogger(db)
    await audit.log(action="hermes.agent.enabled", target_id=agent_id, org_id=org.id, actor_id=user.id if user else "")
    await db.commit()
    return _ok(await service.get_runtime_state(org.id, agent_id, require_bound=False))


@router.post("/agents/{agent_id}/disable")
async def disable_agent(
    agent_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    await HermesBoundAgentScopeService(db).assert_bound_instance(org.id, agent_id)
    service = HermesAgentRuntimeService(db)
    await service.disable(org.id, agent_id, actor_id=user.id if user else None)
    audit = SkillAuditLogger(db)
    await audit.log(action="hermes.agent.disabled", target_id=agent_id, org_id=org.id, actor_id=user.id if user else "")
    await db.commit()
    return _ok(await service.get_runtime_state(org.id, agent_id, require_bound=False))


@router.post("/agents/{agent_id}/maintenance")
async def maintenance_agent(
    agent_id: str,
    body: MaintenanceBody,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    await HermesBoundAgentScopeService(db).assert_bound_instance(org.id, agent_id)
    service = HermesAgentRuntimeService(db)
    await service.maintenance(org.id, agent_id, body.reason, actor_id=user.id if user else None)
    audit = SkillAuditLogger(db)
    await audit.log(
        action="hermes.agent.maintenance",
        target_id=agent_id,
        org_id=org.id,
        actor_id=user.id if user else "",
        details={"reason": body.reason},
    )
    await db.commit()
    return _ok(await service.get_runtime_state(org.id, agent_id, require_bound=False))


@router.post("/agents/{agent_id}/drain")
async def drain_agent(
    agent_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:drain")
    await HermesBoundAgentScopeService(db).assert_bound_instance(org.id, agent_id)
    service = HermesAgentRuntimeService(db)
    await service.drain(org.id, agent_id, actor_id=user.id if user else None)
    audit = SkillAuditLogger(db)
    await audit.log(action="hermes.agent.drain", target_id=agent_id, org_id=org.id, actor_id=user.id if user else "")
    await db.commit()
    return _ok(await service.get_runtime_state(org.id, agent_id, require_bound=False))


@router.post("/agents/{agent_id}/resume")
async def resume_agent(
    agent_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    await HermesBoundAgentScopeService(db).assert_bound_instance(org.id, agent_id)
    service = HermesAgentRuntimeService(db)
    await service.resume(org.id, agent_id, actor_id=user.id if user else None)
    audit = SkillAuditLogger(db)
    await audit.log(action="hermes.agent.resumed", target_id=agent_id, org_id=org.id, actor_id=user.id if user else "")
    await db.commit()
    return _ok(await service.get_runtime_state(org.id, agent_id, require_bound=False))
