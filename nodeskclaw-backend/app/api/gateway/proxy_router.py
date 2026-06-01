from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_org
from app.models.instance import Instance
from app.models.base import not_deleted
from app.schemas.gateway.proxy import McpProxyRequest, McpProxyResponse
from app.services.gateway.proxy_service import ProxyService
from app.services.gateway.route_matcher import RouteMatcher
from app.services.gateway.policy_engine import PolicyEngine
from app.services.gateway.tool_cache import ToolCache

router = APIRouter()

_route_matcher = RouteMatcher()
_policy_engine = PolicyEngine()
_tool_cache = ToolCache()
_proxy_service = ProxyService(_route_matcher, _policy_engine, _tool_cache)


def _ok(data=None, message: str = "success"):
    return {"code": 0, "message": message, "data": data}


@router.post("/mcp", tags=["Gateway - MCP 代理"])
async def proxy_mcp_request(
    body: McpProxyRequest,
    user_org=Depends(get_current_org),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org

    instance_id = None
    tool_name = None
    if body.params:
        instance_id = body.params.get("instance_id")
        tool_name = body.params.get("name")

    if not instance_id:
        raise HTTPException(
            status_code=400,
            detail={"error_code": 40000, "message_key": "errors.common.bad_request", "message": "缺少 instance_id"},
        )

    result = await db.execute(
        select(Instance).where(
            Instance.id == instance_id,
            not_deleted(Instance),
            Instance.org_id == org.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=403,
            detail={"error_code": 40300, "message_key": "errors.mcp.access_denied", "message": "无权访问该实例"},
        )

    await _route_matcher.refresh(db)

    response = await _proxy_service.handle_mcp_request(
        db,
        method=body.method,
        params=body.params,
        instance_id=instance_id,
        org_id=org.id,
        user_id=user.id,
        tool_name=tool_name,
    )

    return _ok(response.model_dump(exclude_none=True))
