from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user
from app.models.base import not_deleted
from app.models.org_membership import OrgMembership, OrgRole
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.hermes_mcp import McpCallLogItem, McpCallLogListResponse
from app.services.mcp_skill_gateway.audit_service import list_mcp_calls
from app.services.mcp_skill_gateway.constants import MCP_PROTOCOL_VERSION, MCP_SERVER_NAME
from app.services.mcp_skill_gateway.handler import dispatch
from app.services.mcp_skill_gateway.mcp_tool_registry import count_tools_by_permission
router = APIRouter()


@router.get("/mcp/health", tags=["MCP Skill Gateway"])
async def mcp_health():
    tool_counts = count_tools_by_permission()
    return {
        "ok": True,
        "service": MCP_SERVER_NAME,
        "status": "running",
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "tools": tool_counts,
    }


@router.get("/hermes/mcp/audit", response_model=ApiResponse[McpCallLogListResponse], tags=["MCP Skill Gateway"])
async def list_mcp_audit_logs(
    tool_name: str | None = Query(default=None),
    instance_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    from_time: datetime | None = Query(default=None, alias="from"),
    to_time: datetime | None = Query(default=None, alias="to"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = current_user.current_org_id
    if not org_id:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError("用户未选择组织", "errors.org.not_selected")

    filter_user_id: str | None = current_user.id
    if current_user.is_super_admin:
        filter_user_id = None
    else:
        role_result = await db.execute(
            select(OrgMembership.role).where(
                OrgMembership.user_id == current_user.id,
                OrgMembership.org_id == org_id,
                not_deleted(OrgMembership),
            )
        )
        org_role = role_result.scalar_one_or_none()
        if org_role == OrgRole.admin:
            filter_user_id = None

    rows, total = await list_mcp_calls(
        db,
        org_id=org_id,
        user_id=filter_user_id,
        tool_name=tool_name,
        instance_id=instance_id,
        status=status,
        from_time=from_time,
        to_time=to_time,
        limit=limit,
        offset=offset,
    )
    items = [
        McpCallLogItem(
            id=row.id,
            tool_name=row.tool_name,
            permission=row.permission,
            risk_level=row.risk_level,
            instance_id=row.instance_id,
            status=row.status,
            duration_ms=row.duration_ms,
            created_at=row.created_at,
        )
        for row in rows
    ]
    return ApiResponse(data=McpCallLogListResponse(items=items, total=total))


@router.post("/mcp", tags=["MCP Skill Gateway"])
async def mcp_jsonrpc(
    request: Request,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    authorization = request.headers.get("authorization")
    return await dispatch(body, authorization, db)


@router.post("/hermes/mcp", tags=["MCP Skill Gateway"])
async def hermes_mcp_jsonrpc(
    request: Request,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    authorization = request.headers.get("authorization")
    return await dispatch(body, authorization, db)
