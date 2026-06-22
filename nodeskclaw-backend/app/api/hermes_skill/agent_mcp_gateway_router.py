from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.services.hermes_external import hermes_agent_mcp_gateway_service as mcp_gateway_service
from app.services.hermes_skill.permission_checker import PermissionChecker

router = APIRouter()


def _ok(data=None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


@router.get("/agents/{agent_profile}/mcp-gateway")
async def get_agent_mcp_gateway_status(
    agent_profile: str,
    force_refresh: bool = Query(False),
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:view")
    data = await mcp_gateway_service.get_gateway_status(
        db,
        org.id,
        agent_profile,
        force_refresh=force_refresh,
    )
    return _ok(data.model_dump())


@router.get("/agents/{agent_profile}/mcp-tools")
async def list_agent_mcp_tools(
    agent_profile: str,
    force_refresh: bool = Query(False),
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:view")
    user_id = user.id if user else ""
    items = await mcp_gateway_service.list_mcp_tools_for_user(
        db,
        org.id,
        user_id,
        agent_profile,
        force_refresh=force_refresh,
    )
    return _ok({"items": [item.model_dump() for item in items], "total": len(items)})


@router.post("/mcp/{agent_profile}")
async def agent_mcp_jsonrpc(
    agent_profile: str,
    body: dict,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    if user:
        await PermissionChecker.require_permission(db, user.id, org.id, "hermes_agent:view")
    user_id = user.id if user else ""
    result = await mcp_gateway_service.dispatch_agent_mcp(
        db,
        org.id,
        user_id,
        agent_profile,
        body,
    )
    await db.commit()
    return result
