"""MCP write tool server-side approval and grant management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.mcp_tool_approval_request import McpToolApprovalRequest
from app.models.mcp_tool_grant import McpToolGrant
from app.models.mcp_tool_policy_event import McpToolPolicyEvent
from app.models.org_membership import OrgMembership, OrgRole
from app.services.mcp_skill_gateway.audit_service import sanitize_input_summary
from app.services.mcp_skill_gateway.errors import (
    MCP_TOOL_APPROVAL_PENDING,
    MCP_TOOL_APPROVAL_REQUIRED,
    MCP_TOOL_GRANT_EXPIRED,
    MCP_TOOL_GRANT_NOT_FOUND,
    MCP_TOOL_GRANT_REVOKED,
)
from app.services.mcp_skill_gateway.mcp_tool_registry import ToolDefinition, resolve_approval_mode

DEFAULT_PROTECTED_SKILLS = frozenset({
    "hermes-agent",
    "mcp-skill-gateway",
    "genehub-runtime",
})


@dataclass
class GrantCheckResult:
    allowed: bool
    error_code: str | None = None
    message: str | None = None
    data: dict[str, Any] | None = None
    grant: McpToolGrant | None = None
    approval_request_id: str | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _record_policy_event(
    db: AsyncSession,
    *,
    org_id: str,
    event_type: str,
    tool_name: str,
    actor_user_id: str | None = None,
    target_user_id: str | None = None,
    instance_id: str | None = None,
    approval_request_id: str | None = None,
    grant_id: str | None = None,
    before_json: dict | None = None,
    after_json: dict | None = None,
    reason: str | None = None,
) -> None:
    event = McpToolPolicyEvent(
        org_id=org_id,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        tool_name=tool_name,
        instance_id=instance_id,
        event_type=event_type,
        approval_request_id=approval_request_id,
        grant_id=grant_id,
        before_json=before_json,
        after_json=after_json,
        reason=reason,
    )
    db.add(event)
    await db.flush()


async def _get_latest_grant(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    instance_id: str | None,
    tool_name: str,
) -> McpToolGrant | None:
    result = await db.execute(
        select(McpToolGrant)
        .where(
            McpToolGrant.org_id == org_id,
            McpToolGrant.user_id == user_id,
            McpToolGrant.tool_name == tool_name,
            McpToolGrant.instance_id == instance_id,
            not_deleted(McpToolGrant),
        )
        .order_by(McpToolGrant.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_pending_request(
    db: AsyncSession,
    *,
    org_id: str,
    requester_user_id: str,
    instance_id: str | None,
    tool_name: str,
) -> McpToolApprovalRequest | None:
    result = await db.execute(
        select(McpToolApprovalRequest)
        .where(
            McpToolApprovalRequest.org_id == org_id,
            McpToolApprovalRequest.requester_user_id == requester_user_id,
            McpToolApprovalRequest.instance_id == instance_id,
            McpToolApprovalRequest.tool_name == tool_name,
            McpToolApprovalRequest.status == "pending",
            not_deleted(McpToolApprovalRequest),
        )
        .order_by(McpToolApprovalRequest.requested_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _grant_is_expired(grant: McpToolGrant, now: datetime | None = None) -> bool:
    if grant.expires_at is None:
        return False
    current = now or _utcnow()
    return grant.expires_at <= current


async def get_grant_annotation(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    instance_id: str | None,
    tool_name: str,
    tool: ToolDefinition | None = None,
) -> dict[str, Any]:
    if tool is None:
        from app.services.mcp_skill_gateway.mcp_tool_registry import get_tool

        tool = get_tool(tool_name)
    if tool and resolve_approval_mode(tool) in ("none", "desktop"):
        if resolve_approval_mode(tool) == "desktop":
            return {
                "authorized": True,
                "grantStatus": "desktop_pending",
                "approvalMode": "desktop",
            }
        return {"authorized": True}
    grant = await _get_latest_grant(
        db,
        org_id=org_id,
        user_id=user_id,
        instance_id=instance_id,
        tool_name=tool_name,
    )
    if grant is None:
        return {
            "authorized": False,
            "grantStatus": "missing",
        }
    if grant.grant_status == "active" and not _grant_is_expired(grant):
        return {
            "authorized": True,
            "grantStatus": "active",
            "grantId": grant.id,
            "expiresAt": grant.expires_at.isoformat() if grant.expires_at else None,
        }
    if grant.grant_status == "revoked":
        return {
            "authorized": False,
            "grantStatus": "revoked",
            "revokedAt": grant.revoked_at.isoformat() if grant.revoked_at else None,
        }
    if grant.grant_status == "expired" or _grant_is_expired(grant):
        return {
            "authorized": False,
            "grantStatus": "expired",
            "expiresAt": grant.expires_at.isoformat() if grant.expires_at else None,
        }
    return {
        "authorized": False,
        "grantStatus": grant.grant_status,
    }


async def check_tool_grant(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    tool: ToolDefinition,
    instance_id: str | None,
    instance_ref: str | None,
    arguments: dict[str, Any] | None = None,
) -> GrantCheckResult:
    mode = resolve_approval_mode(tool)
    if mode in ("none", "desktop") or tool.permission == "read":
        return GrantCheckResult(allowed=True)

    if not tool.requires_approval and mode not in ("server", "hybrid"):
        return GrantCheckResult(allowed=True)

    grant = await _get_latest_grant(
        db,
        org_id=org_id,
        user_id=user_id,
        instance_id=instance_id,
        tool_name=tool.name,
    )
    if grant and grant.grant_status == "active":
        if _grant_is_expired(grant):
            grant.grant_status = "expired"
            await db.flush()
            await _record_policy_event(
                db,
                org_id=org_id,
                event_type="grant_expired",
                tool_name=tool.name,
                target_user_id=user_id,
                instance_id=instance_id,
                grant_id=grant.id,
            )
            return GrantCheckResult(
                allowed=False,
                error_code=MCP_TOOL_GRANT_EXPIRED,
                message="Tool grant expired",
                data={
                    "toolName": tool.name,
                    "expiresAt": grant.expires_at.isoformat() if grant.expires_at else None,
                },
            )
        await _record_policy_event(
            db,
            org_id=org_id,
            event_type="grant_used",
            tool_name=tool.name,
            actor_user_id=user_id,
            target_user_id=user_id,
            instance_id=instance_id,
            grant_id=grant.id,
        )
        return GrantCheckResult(allowed=True, grant=grant)

    if grant and grant.grant_status == "revoked":
        await _record_policy_event(
            db,
            org_id=org_id,
            event_type="grant_denied",
            tool_name=tool.name,
            actor_user_id=user_id,
            target_user_id=user_id,
            instance_id=instance_id,
            grant_id=grant.id,
            reason="grant_revoked",
        )
        return GrantCheckResult(
            allowed=False,
            error_code=MCP_TOOL_GRANT_REVOKED,
            message="Tool grant revoked",
            data={
                "toolName": tool.name,
                "revokedAt": grant.revoked_at.isoformat() if grant.revoked_at else None,
            },
        )

    pending = await _get_pending_request(
        db,
        org_id=org_id,
        requester_user_id=user_id,
        instance_id=instance_id,
        tool_name=tool.name,
    )
    if pending:
        return GrantCheckResult(
            allowed=False,
            error_code=MCP_TOOL_APPROVAL_PENDING,
            message="Tool approval pending",
            data={
                "toolName": tool.name,
                "approvalRequestId": pending.id,
                "approvalMode": "server",
            },
            approval_request_id=pending.id,
        )

    request = await create_approval_request(
        db,
        org_id=org_id,
        requester_user_id=user_id,
        tool=tool,
        instance_id=instance_id,
        instance_ref=instance_ref,
        arguments=arguments,
        request_source="mcp_tool_call",
    )
    return GrantCheckResult(
        allowed=False,
        error_code=MCP_TOOL_APPROVAL_REQUIRED,
        message="Tool approval required",
        data={
            "toolName": tool.name,
            "approvalRequestId": request.id,
            "approvalMode": "server",
            "message": "Approval request created in nodeskclaw.",
        },
        approval_request_id=request.id,
    )


async def create_approval_request(
    db: AsyncSession,
    *,
    org_id: str,
    requester_user_id: str,
    tool: ToolDefinition,
    instance_id: str | None = None,
    instance_ref: str | None = None,
    arguments: dict[str, Any] | None = None,
    request_source: str = "mcp_tool_call",
    request_reason: str | None = None,
    desktop_device_id: str | None = None,
    profile_id: str | None = None,
    profile_name: str | None = None,
) -> McpToolApprovalRequest:
    now = _utcnow()
    request = McpToolApprovalRequest(
        org_id=org_id,
        requester_user_id=requester_user_id,
        desktop_device_id=desktop_device_id,
        profile_id=profile_id,
        profile_name=profile_name,
        instance_id=instance_id,
        instance_ref=instance_ref,
        tool_name=tool.name,
        permission=tool.permission,
        risk_level=tool.risk_level,
        request_source=request_source,
        request_reason=request_reason,
        arguments_summary=sanitize_input_summary(arguments),
        status="pending",
        requested_at=now,
    )
    db.add(request)
    await db.flush()
    await _record_policy_event(
        db,
        org_id=org_id,
        event_type="request_created",
        tool_name=tool.name,
        actor_user_id=requester_user_id,
        target_user_id=requester_user_id,
        instance_id=instance_id,
        approval_request_id=request.id,
        after_json={"status": "pending"},
    )
    return request


async def _require_approver(
    db: AsyncSession,
    *,
    user_id: str,
    org_id: str,
    tool_permission: str,
) -> str:
    result = await db.execute(
        select(OrgMembership).where(
            OrgMembership.user_id == user_id,
            OrgMembership.org_id == org_id,
            not_deleted(OrgMembership),
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        raise ForbiddenError("无权审批", "errors.org.org_member_required")
    if membership.role == OrgRole.member:
        raise ForbiddenError("无权审批", "errors.org.org_admin_required")
    if membership.role == OrgRole.operator and tool_permission == "admin":
        raise ForbiddenError("operator 不可审批 admin 工具", "errors.org.org_admin_required")
    return membership.role


async def approve_request(
    db: AsyncSession,
    *,
    request_id: str,
    approver_user_id: str,
    org_id: str,
    expires_at: datetime | None = None,
    decision_comment: str | None = None,
    constraints: dict | None = None,
) -> McpToolGrant:
    result = await db.execute(
        select(McpToolApprovalRequest).where(
            McpToolApprovalRequest.id == request_id,
            McpToolApprovalRequest.org_id == org_id,
            not_deleted(McpToolApprovalRequest),
        )
    )
    request = result.scalar_one_or_none()
    if request is None:
        raise NotFoundError("审批请求不存在", "errors.mcp.approval_request_not_found")
    if request.status != "pending":
        raise BadRequestError("审批请求状态不可审批", "errors.mcp.approval_request_invalid_status")

    await _require_approver(db, user_id=approver_user_id, org_id=org_id, tool_permission=request.permission)

    existing = await _get_latest_grant(
        db,
        org_id=org_id,
        user_id=request.requester_user_id,
        instance_id=request.instance_id,
        tool_name=request.tool_name,
    )
    if existing and existing.grant_status == "active":
        raise BadRequestError("已存在有效授权", "errors.mcp.grant_already_active")

    now = _utcnow()
    grant = McpToolGrant(
        org_id=org_id,
        user_id=request.requester_user_id,
        desktop_device_id=request.desktop_device_id,
        profile_id=request.profile_id,
        profile_name=request.profile_name,
        instance_id=request.instance_id,
        tool_name=request.tool_name,
        permission=request.permission,
        risk_level=request.risk_level,
        grant_status="active",
        approved_by=approver_user_id,
        approved_at=now,
        expires_at=expires_at,
        constraints_json=constraints,
        source_request_id=request.id,
    )
    db.add(grant)
    await db.flush()

    request.status = "approved"
    request.decided_by = approver_user_id
    request.decided_at = now
    request.decision_comment = decision_comment
    request.grant_id = grant.id
    request.expires_at = expires_at
    await db.flush()

    await _record_policy_event(
        db,
        org_id=org_id,
        event_type="request_approved",
        tool_name=request.tool_name,
        actor_user_id=approver_user_id,
        target_user_id=request.requester_user_id,
        instance_id=request.instance_id,
        approval_request_id=request.id,
        grant_id=grant.id,
        after_json={"status": "approved"},
        reason=decision_comment,
    )
    await _record_policy_event(
        db,
        org_id=org_id,
        event_type="grant_created",
        tool_name=request.tool_name,
        actor_user_id=approver_user_id,
        target_user_id=request.requester_user_id,
        instance_id=request.instance_id,
        approval_request_id=request.id,
        grant_id=grant.id,
    )
    return grant


async def reject_request(
    db: AsyncSession,
    *,
    request_id: str,
    approver_user_id: str,
    org_id: str,
    decision_comment: str | None = None,
) -> McpToolApprovalRequest:
    result = await db.execute(
        select(McpToolApprovalRequest).where(
            McpToolApprovalRequest.id == request_id,
            McpToolApprovalRequest.org_id == org_id,
            not_deleted(McpToolApprovalRequest),
        )
    )
    request = result.scalar_one_or_none()
    if request is None:
        raise NotFoundError("审批请求不存在", "errors.mcp.approval_request_not_found")
    if request.status != "pending":
        raise BadRequestError("审批请求状态不可拒绝", "errors.mcp.approval_request_invalid_status")

    await _require_approver(db, user_id=approver_user_id, org_id=org_id, tool_permission=request.permission)

    now = _utcnow()
    request.status = "rejected"
    request.decided_by = approver_user_id
    request.decided_at = now
    request.decision_comment = decision_comment
    await db.flush()

    await _record_policy_event(
        db,
        org_id=org_id,
        event_type="request_rejected",
        tool_name=request.tool_name,
        actor_user_id=approver_user_id,
        target_user_id=request.requester_user_id,
        instance_id=request.instance_id,
        approval_request_id=request.id,
        after_json={"status": "rejected"},
        reason=decision_comment,
    )
    return request


async def revoke_grant(
    db: AsyncSession,
    *,
    grant_id: str,
    org_id: str,
    revoker_user_id: str,
    reason: str | None = None,
) -> McpToolGrant:
    result = await db.execute(
        select(McpToolGrant).where(
            McpToolGrant.id == grant_id,
            McpToolGrant.org_id == org_id,
            not_deleted(McpToolGrant),
        )
    )
    grant = result.scalar_one_or_none()
    if grant is None:
        raise NotFoundError("授权不存在", MCP_TOOL_GRANT_NOT_FOUND)
    if grant.grant_status != "active":
        raise BadRequestError("授权不可撤销", "errors.mcp.grant_not_active")

    await _require_approver(db, user_id=revoker_user_id, org_id=org_id, tool_permission=grant.permission)

    now = _utcnow()
    grant.grant_status = "revoked"
    grant.revoked_by = revoker_user_id
    grant.revoked_at = now
    grant.revoke_reason = reason
    await db.flush()

    await _record_policy_event(
        db,
        org_id=org_id,
        event_type="grant_revoked",
        tool_name=grant.tool_name,
        actor_user_id=revoker_user_id,
        target_user_id=grant.user_id,
        instance_id=grant.instance_id,
        grant_id=grant.id,
        reason=reason,
    )
    return grant


async def list_approval_requests(
    db: AsyncSession,
    *,
    org_id: str,
    status: str | None = None,
    tool_name: str | None = None,
    instance_id: str | None = None,
    requester_user_id: str | None = None,
    from_time: datetime | None = None,
    to_time: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[McpToolApprovalRequest], int]:
    query = select(McpToolApprovalRequest).where(
        McpToolApprovalRequest.org_id == org_id,
        not_deleted(McpToolApprovalRequest),
    )
    count_query = select(func.count()).select_from(McpToolApprovalRequest).where(
        McpToolApprovalRequest.org_id == org_id,
        not_deleted(McpToolApprovalRequest),
    )
    if status:
        query = query.where(McpToolApprovalRequest.status == status)
        count_query = count_query.where(McpToolApprovalRequest.status == status)
    if tool_name:
        query = query.where(McpToolApprovalRequest.tool_name == tool_name)
        count_query = count_query.where(McpToolApprovalRequest.tool_name == tool_name)
    if instance_id:
        query = query.where(McpToolApprovalRequest.instance_id == instance_id)
        count_query = count_query.where(McpToolApprovalRequest.instance_id == instance_id)
    if requester_user_id:
        query = query.where(McpToolApprovalRequest.requester_user_id == requester_user_id)
        count_query = count_query.where(McpToolApprovalRequest.requester_user_id == requester_user_id)
    if from_time:
        query = query.where(McpToolApprovalRequest.requested_at >= from_time)
        count_query = count_query.where(McpToolApprovalRequest.requested_at >= from_time)
    if to_time:
        query = query.where(McpToolApprovalRequest.requested_at <= to_time)
        count_query = count_query.where(McpToolApprovalRequest.requested_at <= to_time)

    total = int((await db.execute(count_query)).scalar_one())
    rows = await db.execute(
        query.order_by(McpToolApprovalRequest.requested_at.desc()).limit(limit).offset(offset)
    )
    return list(rows.scalars().all()), total


async def get_approval_request(
    db: AsyncSession,
    *,
    org_id: str,
    request_id: str,
) -> McpToolApprovalRequest:
    result = await db.execute(
        select(McpToolApprovalRequest).where(
            McpToolApprovalRequest.id == request_id,
            McpToolApprovalRequest.org_id == org_id,
            not_deleted(McpToolApprovalRequest),
        )
    )
    request = result.scalar_one_or_none()
    if request is None:
        raise NotFoundError("审批请求不存在", "errors.mcp.approval_request_not_found")
    return request


async def list_grants(
    db: AsyncSession,
    *,
    org_id: str,
    grant_status: str | None = None,
    tool_name: str | None = None,
    instance_id: str | None = None,
    user_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[McpToolGrant], int]:
    query = select(McpToolGrant).where(
        McpToolGrant.org_id == org_id,
        not_deleted(McpToolGrant),
    )
    count_query = select(func.count()).select_from(McpToolGrant).where(
        McpToolGrant.org_id == org_id,
        not_deleted(McpToolGrant),
    )
    if grant_status:
        query = query.where(McpToolGrant.grant_status == grant_status)
        count_query = count_query.where(McpToolGrant.grant_status == grant_status)
    if tool_name:
        query = query.where(McpToolGrant.tool_name == tool_name)
        count_query = count_query.where(McpToolGrant.tool_name == tool_name)
    if instance_id:
        query = query.where(McpToolGrant.instance_id == instance_id)
        count_query = count_query.where(McpToolGrant.instance_id == instance_id)
    if user_id:
        query = query.where(McpToolGrant.user_id == user_id)
        count_query = count_query.where(McpToolGrant.user_id == user_id)

    total = int((await db.execute(count_query)).scalar_one())
    rows = await db.execute(
        query.order_by(McpToolGrant.approved_at.desc()).limit(limit).offset(offset)
    )
    return list(rows.scalars().all()), total


def get_protected_skills(constraints: dict | None) -> frozenset[str]:
    if not constraints:
        return DEFAULT_PROTECTED_SKILLS
    protected = constraints.get("protected_skills")
    if isinstance(protected, list):
        return frozenset(str(item) for item in protected) | DEFAULT_PROTECTED_SKILLS
    return DEFAULT_PROTECTED_SKILLS
