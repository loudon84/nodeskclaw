from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.schemas.hermes_skill.mcp_skill_router import (
    McpSkillRouterDeleteRequest,
    McpSkillRouterDeleteResponse,
    McpSkillRouterStatusResponse,
    McpSkillRouterSyncRequest,
    McpSkillRouterSyncResponse,
)
from app.services.hermes_agents.mcp_skill_router_service import McpSkillRouterService
from app.services.hermes_skill.permission_checker import PermissionChecker

router = APIRouter()


def _ok(data=None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.post("/agents/{agent_id}/mcp-skill-router/sync")
async def sync_mcp_skill_router(
    agent_id: str,
    body: McpSkillRouterSyncRequest,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    service = McpSkillRouterService(db)
    result = await service.sync(
        org.id,
        agent_id,
        user,
        profile=body.profile,
        force=body.force,
        tool_filter=body.tool_filter,
        include_registry_tools=body.include_registry_tools,
    )
    await db.commit()
    return _ok(McpSkillRouterSyncResponse(**result).model_dump())


@router.get("/agents/{agent_id}/mcp-skill-router/status")
async def get_mcp_skill_router_status(
    agent_id: str,
    profile: str = Query(default="default"),
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:view")
    service = McpSkillRouterService(db)
    result = await service.get_status(org.id, agent_id, profile=profile)
    return _ok(McpSkillRouterStatusResponse(**result).model_dump())


@router.post("/agents/{agent_id}/mcp-skill-router/delete")
async def delete_mcp_skill_router(
    agent_id: str,
    body: McpSkillRouterDeleteRequest,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    service = McpSkillRouterService(db)
    result = await service.delete(org.id, agent_id, user, profile=body.profile)
    await db.commit()
    return _ok(McpSkillRouterDeleteResponse(**result).model_dump())
