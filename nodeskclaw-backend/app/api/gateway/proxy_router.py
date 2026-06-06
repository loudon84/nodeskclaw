from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_api_key_or_jwt
from app.models.instance import Instance
from app.models.base import not_deleted
from app.schemas.gateway.proxy import McpProxyRequest, McpProxyResponse
from app.services.gateway.proxy_service import ProxyService
from app.services.gateway.route_matcher import RouteMatcher
from app.services.gateway.policy_engine import PolicyEngine
from app.services.gateway.tool_cache import ToolCache
from app.services.gateway.security.request_validator import RequestValidator
from app.services.gateway.security.scope_checker import ScopeChecker
from app.services.gateway.security.injection_guard import InjectionGuard
from app.services.gateway.security.rate_limiter import RateLimiter

router = APIRouter()

_route_matcher = RouteMatcher()
_policy_engine = PolicyEngine()
_tool_cache = ToolCache()
_proxy_service = ProxyService(_route_matcher, _policy_engine, _tool_cache)
_rate_limiter = RateLimiter()


def _ok(data=None, message: str = "success"):
    return {"code": 0, "message": message, "data": data}


@router.post("/mcp", tags=["Gateway - MCP 代理"])
async def proxy_mcp_request(
    request: Request,
    body: McpProxyRequest,
    auth_result=Depends(get_api_key_or_jwt),
    db: AsyncSession = Depends(get_db),
):
    user, org, auth_type, auth_key_id = auth_result

    RequestValidator.validate_jsonrpc_version(body.jsonrpc)

    content_length = int(request.headers.get("content-length", "0"))
    RequestValidator.validate(
        method=body.method,
        params=body.params,
        body_size=content_length,
    )

    if user and hasattr(user, "scopes"):
        scope_result = ScopeChecker.check_scope(user.scopes, body.method)
        if not scope_result.is_allowed:
            raise HTTPException(
                status_code=403,
                detail={
                    "error_code": 40301,
                    "message_key": "errors.mcp.insufficient_scope",
                    "message": f"Scope 不足，需要 {scope_result.required_scope}",
                },
            )

    tool_name = body.params.get("name") if body.params else None
    if tool_name:
        InjectionGuard.check_tool_name(tool_name)
    if body.params:
        InjectionGuard.check_params(body.params)

    from app.core.config import settings
    if not _rate_limiter.check_global(settings.GATEWAY_GLOBAL_RATE_LIMIT_RPM):
        raise HTTPException(
            status_code=429,
            detail={"error_code": 42903, "message_key": "errors.mcp.rate_limit_exceeded", "message": "全局限流触发"},
        )
    if auth_key_id:
        from app.models.gateway.gateway_api_key import McpGatewayApiKey
        api_key_result = await db.execute(
            select(McpGatewayApiKey.rate_limit_rpm).where(McpGatewayApiKey.id == auth_key_id)
        )
        key_rpm = api_key_result.scalar_one_or_none()
        if key_rpm and not _rate_limiter.check_per_key(auth_key_id, key_rpm):
            raise HTTPException(
                status_code=429,
                detail={"error_code": 42904, "message_key": "errors.mcp.rate_limit_exceeded", "message": "API Key 限流触发"},
            )

    instance_id = None
    if body.params:
        instance_id = body.params.get("instance_id")

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

    user_id = user.id if user else None
    response = await _proxy_service.handle_mcp_request(
        db,
        method=body.method,
        params=body.params,
        instance_id=instance_id,
        org_id=org.id,
        user_id=user_id,
        tool_name=tool_name,
        caller_ip=request.client.host if request.client else None,
        auth_type=auth_type,
        auth_key_id=auth_key_id,
    )

    return _ok(response.model_dump(exclude_none=True))
