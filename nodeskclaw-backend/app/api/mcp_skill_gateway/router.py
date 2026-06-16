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
from app.schemas.mcp_tool_approval import (
    ApproveMcpToolRequestBody,
    McpToolApprovalRequestItem,
    McpToolApprovalRequestListResponse,
    McpToolGrantItem,
    McpToolGrantListResponse,
    RejectMcpToolRequestBody,
    RevokeMcpToolGrantBody,
)
from app.services.mcp_skill_gateway.approval_service import (
    approve_request,
    get_approval_request,
    list_approval_requests,
    list_grants,
    reject_request,
    revoke_grant,
)
from app.services.mcp_skill_gateway.audit_service import list_mcp_calls
from app.services.mcp_skill_gateway.constants import (
    HERMES_MCP_VERSION,
    MCP_HEALTH_ENDPOINT_LEGACY,
    MCP_PROTOCOL_VERSION,
    MCP_SERVER_NAME,
)
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


@router.get("/hermes/mcp/health", tags=["MCP Skill Gateway"])
async def hermes_mcp_health():
    return {
        "status": "ok",
        "service": "hermes-mcp-gateway",
        "version": HERMES_MCP_VERSION,
        "protocolVersion": MCP_PROTOCOL_VERSION,
    }


@router.get(MCP_HEALTH_ENDPOINT_LEGACY, tags=["MCP Skill Gateway"], include_in_schema=False)
async def mcp_health_legacy():
    return await mcp_health()


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


def _to_approval_item(row) -> McpToolApprovalRequestItem:
    return McpToolApprovalRequestItem(
        id=row.id,
        org_id=row.org_id,
        requester_user_id=row.requester_user_id,
        desktop_device_id=row.desktop_device_id,
        profile_id=row.profile_id,
        profile_name=row.profile_name,
        instance_id=row.instance_id,
        instance_ref=row.instance_ref,
        tool_name=row.tool_name,
        permission=row.permission,
        risk_level=row.risk_level,
        request_source=row.request_source,
        request_reason=row.request_reason,
        arguments_summary=row.arguments_summary,
        status=row.status,
        requested_at=row.requested_at,
        decided_by=row.decided_by,
        decided_at=row.decided_at,
        decision_comment=row.decision_comment,
        grant_id=row.grant_id,
        expires_at=row.expires_at,
    )


def _to_grant_item(row) -> McpToolGrantItem:
    return McpToolGrantItem(
        id=row.id,
        org_id=row.org_id,
        user_id=row.user_id,
        desktop_device_id=row.desktop_device_id,
        profile_id=row.profile_id,
        profile_name=row.profile_name,
        instance_id=row.instance_id,
        tool_name=row.tool_name,
        permission=row.permission,
        risk_level=row.risk_level,
        grant_status=row.grant_status,
        approved_by=row.approved_by,
        approved_at=row.approved_at,
        revoked_by=row.revoked_by,
        revoked_at=row.revoked_at,
        revoke_reason=row.revoke_reason,
        expires_at=row.expires_at,
        constraints_json=row.constraints_json,
        source_request_id=row.source_request_id,
    )


async def _require_org_operator_or_admin(
    db: AsyncSession,
    user: User,
    org_id: str,
) -> None:
    from app.core.exceptions import ForbiddenError

    if user.is_super_admin:
        return
    result = await db.execute(
        select(OrgMembership.role).where(
            OrgMembership.user_id == user.id,
            OrgMembership.org_id == org_id,
            not_deleted(OrgMembership),
        )
    )
    role = result.scalar_one_or_none()
    if role not in (OrgRole.admin, OrgRole.operator):
        raise ForbiddenError("无权操作 MCP 工具审批", "errors.org.org_admin_required")


@router.get(
    "/mcp/tool-approval-requests",
    response_model=ApiResponse[McpToolApprovalRequestListResponse],
    tags=["MCP Skill Gateway"],
)
async def list_tool_approval_requests(
    status: str | None = Query(default=None),
    tool_name: str | None = Query(default=None),
    instance_id: str | None = Query(default=None),
    requester_user_id: str | None = Query(default=None),
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

    await _require_org_operator_or_admin(db, current_user, org_id)
    rows, total = await list_approval_requests(
        db,
        org_id=org_id,
        status=status,
        tool_name=tool_name,
        instance_id=instance_id,
        requester_user_id=requester_user_id,
        from_time=from_time,
        to_time=to_time,
        limit=limit,
        offset=offset,
    )
    return ApiResponse(
        data=McpToolApprovalRequestListResponse(
            items=[_to_approval_item(row) for row in rows],
            total=total,
        )
    )


@router.get(
    "/mcp/tool-approval-requests/{request_id}",
    response_model=ApiResponse[McpToolApprovalRequestItem],
    tags=["MCP Skill Gateway"],
)
async def get_tool_approval_request(
    request_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = current_user.current_org_id
    if not org_id:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError("用户未选择组织", "errors.org.not_selected")

    await _require_org_operator_or_admin(db, current_user, org_id)
    row = await get_approval_request(db, org_id=org_id, request_id=request_id)
    return ApiResponse(data=_to_approval_item(row))


@router.post(
    "/mcp/tool-approval-requests/{request_id}/approve",
    response_model=ApiResponse[McpToolGrantItem],
    tags=["MCP Skill Gateway"],
)
async def approve_tool_request(
    request_id: str,
    body: ApproveMcpToolRequestBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = current_user.current_org_id
    if not org_id:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError("用户未选择组织", "errors.org.not_selected")

    grant = await approve_request(
        db,
        request_id=request_id,
        approver_user_id=current_user.id,
        org_id=org_id,
        expires_at=body.expires_at,
        decision_comment=body.decision_comment,
        constraints=body.constraints,
    )
    await db.commit()
    return ApiResponse(data=_to_grant_item(grant))


@router.post(
    "/mcp/tool-approval-requests/{request_id}/reject",
    response_model=ApiResponse[McpToolApprovalRequestItem],
    tags=["MCP Skill Gateway"],
)
async def reject_tool_request(
    request_id: str,
    body: RejectMcpToolRequestBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = current_user.current_org_id
    if not org_id:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError("用户未选择组织", "errors.org.not_selected")

    request = await reject_request(
        db,
        request_id=request_id,
        approver_user_id=current_user.id,
        org_id=org_id,
        decision_comment=body.decision_comment,
    )
    await db.commit()
    return ApiResponse(data=_to_approval_item(request))


@router.get(
    "/mcp/tool-grants",
    response_model=ApiResponse[McpToolGrantListResponse],
    tags=["MCP Skill Gateway"],
)
async def list_tool_grants(
    grant_status: str | None = Query(default=None, alias="status"),
    tool_name: str | None = Query(default=None),
    instance_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = current_user.current_org_id
    if not org_id:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError("用户未选择组织", "errors.org.not_selected")

    await _require_org_operator_or_admin(db, current_user, org_id)
    rows, total = await list_grants(
        db,
        org_id=org_id,
        grant_status=grant_status,
        tool_name=tool_name,
        instance_id=instance_id,
        user_id=user_id,
        limit=limit,
        offset=offset,
    )
    return ApiResponse(
        data=McpToolGrantListResponse(
            items=[_to_grant_item(row) for row in rows],
            total=total,
        )
    )


@router.post(
    "/mcp/tool-grants/{grant_id}/revoke",
    response_model=ApiResponse[McpToolGrantItem],
    tags=["MCP Skill Gateway"],
)
async def revoke_tool_grant(
    grant_id: str,
    body: RevokeMcpToolGrantBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    org_id = current_user.current_org_id
    if not org_id:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError("用户未选择组织", "errors.org.not_selected")

    grant = await revoke_grant(
        db,
        grant_id=grant_id,
        org_id=org_id,
        revoker_user_id=current_user.id,
        reason=body.reason,
    )
    await db.commit()
    return ApiResponse(data=_to_grant_item(grant))


@router.post("/mcp", tags=["MCP Skill Gateway"])
async def mcp_jsonrpc(
    request: Request,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    authorization = request.headers.get("authorization")
    return await dispatch(body, authorization, db, request_headers=dict(request.headers))


@router.post("/hermes/mcp", tags=["MCP Skill Gateway"])
async def hermes_mcp_jsonrpc(
    request: Request,
    body: dict,
    db: AsyncSession = Depends(get_db),
):
    authorization = request.headers.get("authorization")
    return await dispatch(body, authorization, db, request_headers=dict(request.headers))
