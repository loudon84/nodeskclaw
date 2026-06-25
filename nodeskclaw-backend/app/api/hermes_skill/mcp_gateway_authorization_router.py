from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.schemas.hermes_skill.mcp_gateway_authorization import (
    McpGatewayAuthorizeRequest,
    McpGatewayAuthorizeResponse,
    McpGatewayRevokeRequest,
    McpGatewayRevokeResponse,
    McpGatewayStatusResponse,
)
from app.services.hermes_agents.mcp_gateway_authorization_service import McpGatewayAuthorizationService
from app.services.hermes_skill.permission_checker import PermissionChecker

router = APIRouter()


def _ok(data=None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.post("/agents/{agent_id}/mcp-gateway/authorize")
async def authorize_mcp_gateway(
    agent_id: str,
    body: McpGatewayAuthorizeRequest,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    service = McpGatewayAuthorizationService(db)
    allowed = body.allowed_skills or None
    result = await service.authorize(
        org.id,
        agent_id,
        user,
        profile=body.profile,
        workspace_id=body.workspace_id,
        expires_days=body.expires_days,
        allowed_skills=allowed,
        write_env=body.write_env,
        force_rotate=body.force_rotate,
    )
    await db.commit()
    return _ok(McpGatewayAuthorizeResponse(**result).model_dump())


@router.get("/agents/{agent_id}/mcp-gateway/status")
async def get_mcp_gateway_status(
    agent_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:view")
    service = McpGatewayAuthorizationService(db)
    result = await service.get_status(org.id, agent_id)
    return _ok(McpGatewayStatusResponse(**result).model_dump())


@router.post("/agents/{agent_id}/mcp-gateway/revoke")
async def revoke_mcp_gateway(
    agent_id: str,
    body: McpGatewayRevokeRequest,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:manage")
    service = McpGatewayAuthorizationService(db)
    result = await service.revoke(
        org.id,
        agent_id,
        user,
        remove_env_keys_flag=body.remove_env_keys,
    )
    await db.commit()
    return _ok(McpGatewayRevokeResponse(**result).model_dump())
