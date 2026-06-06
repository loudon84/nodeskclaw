import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_admin, require_org_member
from app.models.base import not_deleted
from app.models.gateway.gateway_route import McpGatewayRoute
from app.models.gateway.gateway_policy import McpGatewayPolicy
from app.models.gateway.gateway_audit_log import McpGatewayAuditLog
from app.schemas.gateway.route import RouteCreate, RouteUpdate, RouteRead, RouteList
from app.schemas.gateway.policy import PolicyCreate, PolicyUpdate, PolicyRead, PolicyList
from app.schemas.gateway.audit import AuditLogRead, AuditLogList, AuditLogFilter
from app.schemas.gateway.proxy import UpstreamStatusRead
from app.services.gateway.health_checker import gateway_health_checker

router = APIRouter()


def _ok(data=None, message: str = "success"):
    return {"code": 0, "message": message, "data": data}


# ── Route CRUD ───────────────────────────────────────────


@router.post("/routes", tags=["Gateway - 路由规则"])
async def create_route(
    body: RouteCreate,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    existing = await db.execute(
        select(McpGatewayRoute).where(
            not_deleted(McpGatewayRoute),
            McpGatewayRoute.name == body.name,
            McpGatewayRoute.org_id == org.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail={
                "error_code": 40901,
                "message_key": "errors.mcp.route_conflict",
                "message": "路由规则名称已存在",
            },
        )

    route = McpGatewayRoute(
        id=str(uuid.uuid4()),
        name=body.name,
        instance_id=body.instance_id,
        mcp_server_ids=body.mcp_server_ids,
        match_tools=body.match_tools,
        priority=body.priority,
        is_active=body.is_active,
        org_id=org.id,
    )
    db.add(route)
    await db.commit()
    await db.refresh(route)
    return _ok(RouteRead.model_validate(route).model_dump())


@router.get("/routes", tags=["Gateway - 路由规则"])
async def list_routes(
    instance_id: str | None = None,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    query = select(McpGatewayRoute).where(
        not_deleted(McpGatewayRoute),
        McpGatewayRoute.org_id == org.id,
    )
    if instance_id:
        query = query.where(McpGatewayRoute.instance_id == instance_id)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    result = await db.execute(query.order_by(McpGatewayRoute.priority.desc()))
    items = [RouteRead.model_validate(r).model_dump() for r in result.scalars().all()]
    return _ok(RouteList(items=items, total=total).model_dump())


@router.get("/routes/{route_id}", tags=["Gateway - 路由规则"])
async def get_route(
    route_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    result = await db.execute(
        select(McpGatewayRoute).where(
            McpGatewayRoute.id == route_id,
            not_deleted(McpGatewayRoute),
            McpGatewayRoute.org_id == org.id,
        )
    )
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=404, detail={"error_code": 40400, "message": "路由规则不存在"})
    return _ok(RouteRead.model_validate(route).model_dump())


@router.put("/routes/{route_id}", tags=["Gateway - 路由规则"])
async def update_route(
    route_id: str,
    body: RouteUpdate,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    result = await db.execute(
        select(McpGatewayRoute).where(
            McpGatewayRoute.id == route_id,
            not_deleted(McpGatewayRoute),
            McpGatewayRoute.org_id == org.id,
        )
    )
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=404, detail={"error_code": 40400, "message": "路由规则不存在"})

    update_data = body.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(route, k, v)
    await db.commit()
    await db.refresh(route)
    return _ok(RouteRead.model_validate(route).model_dump())


@router.delete("/routes/{route_id}", tags=["Gateway - 路由规则"])
async def delete_route(
    route_id: str,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    result = await db.execute(
        select(McpGatewayRoute).where(
            McpGatewayRoute.id == route_id,
            not_deleted(McpGatewayRoute),
            McpGatewayRoute.org_id == org.id,
        )
    )
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=404, detail={"error_code": 40400, "message": "路由规则不存在"})
    route.soft_delete()
    await db.commit()
    return _ok(message="已删除")


# ── Policy CRUD ──────────────────────────────────────────


@router.post("/policies", tags=["Gateway - 调用策略"])
async def create_policy(
    body: PolicyCreate,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    existing = await db.execute(
        select(McpGatewayPolicy).where(
            not_deleted(McpGatewayPolicy),
            McpGatewayPolicy.name == body.name,
            McpGatewayPolicy.org_id == org.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail={"error_code": 40900, "message": "策略名称已存在"},
        )

    policy = McpGatewayPolicy(
        id=str(uuid.uuid4()),
        name=body.name,
        scope=body.scope,
        scope_ref_id=body.scope_ref_id,
        rate_limit_rpm=body.rate_limit_rpm,
        max_connections=body.max_connections,
        timeout_seconds=body.timeout_seconds,
        retry_count=body.retry_count,
        sensitive_tools=body.sensitive_tools,
        is_active=body.is_active,
        org_id=org.id,
    )
    db.add(policy)
    await db.commit()
    await db.refresh(policy)
    return _ok(PolicyRead.model_validate(policy).model_dump())


@router.get("/policies", tags=["Gateway - 调用策略"])
async def list_policies(
    scope: str | None = None,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    query = select(McpGatewayPolicy).where(
        not_deleted(McpGatewayPolicy),
        McpGatewayPolicy.org_id == org.id,
    )
    if scope:
        query = query.where(McpGatewayPolicy.scope == scope)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    result = await db.execute(query.order_by(McpGatewayPolicy.created_at.desc()))
    items = [PolicyRead.model_validate(p).model_dump() for p in result.scalars().all()]
    return _ok(PolicyList(items=items, total=total).model_dump())


@router.get("/policies/{policy_id}", tags=["Gateway - 调用策略"])
async def get_policy(
    policy_id: str,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    result = await db.execute(
        select(McpGatewayPolicy).where(
            McpGatewayPolicy.id == policy_id,
            not_deleted(McpGatewayPolicy),
            McpGatewayPolicy.org_id == org.id,
        )
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail={"error_code": 40400, "message": "策略不存在"})
    return _ok(PolicyRead.model_validate(policy).model_dump())


@router.put("/policies/{policy_id}", tags=["Gateway - 调用策略"])
async def update_policy(
    policy_id: str,
    body: PolicyUpdate,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    result = await db.execute(
        select(McpGatewayPolicy).where(
            McpGatewayPolicy.id == policy_id,
            not_deleted(McpGatewayPolicy),
            McpGatewayPolicy.org_id == org.id,
        )
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail={"error_code": 40400, "message": "策略不存在"})

    update_data = body.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(policy, k, v)
    await db.commit()
    await db.refresh(policy)
    return _ok(PolicyRead.model_validate(policy).model_dump())


@router.delete("/policies/{policy_id}", tags=["Gateway - 调用策略"])
async def delete_policy(
    policy_id: str,
    user_org=Depends(require_org_admin),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    result = await db.execute(
        select(McpGatewayPolicy).where(
            McpGatewayPolicy.id == policy_id,
            not_deleted(McpGatewayPolicy),
            McpGatewayPolicy.org_id == org.id,
        )
    )
    policy = result.scalar_one_or_none()
    if not policy:
        raise HTTPException(status_code=404, detail={"error_code": 40400, "message": "策略不存在"})
    policy.soft_delete()
    await db.commit()
    return _ok(message="已删除")


# ── Audit Logs ───────────────────────────────────────────


@router.get("/audit-logs", tags=["Gateway - 审计日志"])
async def list_audit_logs(
    instance_id: str | None = None,
    caller_user_id: str | None = None,
    method: str | None = None,
    tool_name: str | None = None,
    response_status: str | None = None,
    page: int = 1,
    page_size: int = 20,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    _, org = user_org
    query = select(McpGatewayAuditLog).where(
        McpGatewayAuditLog.caller_org_id == org.id,
    )
    if instance_id:
        query = query.where(McpGatewayAuditLog.instance_id == instance_id)
    if caller_user_id:
        query = query.where(McpGatewayAuditLog.caller_user_id == caller_user_id)
    if method:
        query = query.where(McpGatewayAuditLog.method == method)
    if tool_name:
        query = query.where(McpGatewayAuditLog.tool_name == tool_name)
    if response_status:
        query = query.where(McpGatewayAuditLog.response_status == response_status)

    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0

    offset = (page - 1) * page_size
    result = await db.execute(
        query.order_by(McpGatewayAuditLog.created_at.desc()).offset(offset).limit(page_size)
    )
    items = [AuditLogRead.model_validate(a).model_dump() for a in result.scalars().all()]
    return _ok(AuditLogList(items=items, total=total).model_dump())


# ── Upstream Status ──────────────────────────────────────


@router.get("/upstreams/status", tags=["Gateway - 上游状态"])
async def list_upstream_status(
    user_org=Depends(require_org_member),
):
    checker = gateway_health_checker
    if checker is None:
        return _ok([])

    states = checker.get_all_states()
    items = [
        UpstreamStatusRead(
            mcp_server_id=s.mcp_server_id,
            mcp_server_name="",
            is_available=s.is_available,
            consecutive_failures=s.consecutive_failures,
            consecutive_successes=s.consecutive_successes,
            last_checked_at=s.last_checked_at.isoformat() if s.last_checked_at else None,
        ).model_dump()
        for s in states.values()
    ]
    return _ok(items)
