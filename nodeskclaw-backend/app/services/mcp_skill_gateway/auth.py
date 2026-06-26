from dataclasses import dataclass, field

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.mcp_client_token import McpClientToken
from app.models.org_membership import OrgMembership
from app.models.organization import Organization
from app.models.user import User


@dataclass
class McpAuthContext:
    user: User
    org: Organization
    auth_type: str = "user_jwt"
    mcp_client_token_id: str | None = None
    mcp_client_token_prefix: str | None = None
    profile: str | None = None
    workspace_id: str | None = None
    scopes: list[str] = field(default_factory=list)
    allowed_tools: list[str] | None = None
    allowed_skills: list[str] | None = None
    hermes_agent_id: str | None = None


@dataclass
class McpAuthFailure:
    error_code: str
    reason: str


async def resolve_mcp_client_token(token: str, db: AsyncSession) -> McpAuthContext | McpAuthFailure:
    from app.services.mcp_skill_gateway.errors import MCP_AUTH_EXPIRED, MCP_AUTH_REQUIRED, MCP_ORG_FORBIDDEN
    from app.services.mcp_skill_gateway.mcp_client_token_service import McpClientTokenService

    token_service = McpClientTokenService(db)
    record = await token_service.verify_token(token)
    if record is None:
        result = await db.execute(
            select(McpClientToken).where(
                not_deleted(McpClientToken),
                McpClientToken.token_prefix == token.split(".", 1)[0] if "." in token else token[:64],
            )
        )
        stale = result.scalar_one_or_none()
        if stale and stale.revoked_at is not None:
            return McpAuthFailure(MCP_AUTH_REQUIRED, "Token has been revoked")
        if stale and token_service.is_expired(stale):
            return McpAuthFailure(MCP_AUTH_EXPIRED, "Authentication expired")
        return McpAuthFailure(MCP_AUTH_REQUIRED, "Missing or invalid Authorization header")

    if not record.service_account_user_id:
        return McpAuthFailure(MCP_AUTH_REQUIRED, "Missing or invalid Authorization header")

    result = await db.execute(
        select(User).where(
            not_deleted(User),
            User.id == record.service_account_user_id,
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        return McpAuthFailure(MCP_ORG_FORBIDDEN, "Service account user not found")

    result = await db.execute(
        select(Organization).where(
            Organization.id == record.org_id,
            Organization.deleted_at.is_(None),
        )
    )
    org = result.scalar_one_or_none()
    if org is None:
        return McpAuthFailure(MCP_ORG_FORBIDDEN, "Organization not found")

    return McpAuthContext(
        user=user,
        org=org,
        auth_type="mcp_client_token",
        mcp_client_token_id=record.id,
        mcp_client_token_prefix=record.token_prefix,
        profile=record.profile,
        workspace_id=record.workspace_id,
        scopes=list(record.scopes or []),
        allowed_tools=record.allowed_tools,
        allowed_skills=record.allowed_skills,
        hermes_agent_id=record.hermes_agent_id,
    )


async def resolve_mcp_user(
    authorization: str | None,
    db: AsyncSession,
) -> McpAuthContext | McpAuthFailure:
    from app.services.mcp_skill_gateway.errors import MCP_AUTH_EXPIRED, MCP_AUTH_REQUIRED, MCP_ORG_FORBIDDEN

    if not authorization or not authorization.startswith("Bearer "):
        return McpAuthFailure(MCP_AUTH_REQUIRED, "Missing or invalid Authorization header")

    token = authorization[7:].strip()
    if not token:
        return McpAuthFailure(MCP_AUTH_REQUIRED, "Missing or invalid Authorization header")

    if token.startswith("ndsk_mcp_"):
        return await resolve_mcp_client_token(token, db)

    from app.core.security import _get_user_by_token

    try:
        user = await _get_user_by_token(token, db)
    except HTTPException as exc:
        if exc.status_code == 401:
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            message_key = detail.get("message_key") if isinstance(detail, dict) else None
            if message_key and "expired" in str(message_key).lower():
                return McpAuthFailure(MCP_AUTH_EXPIRED, "Authentication expired")
        return McpAuthFailure(MCP_AUTH_REQUIRED, "Missing or invalid Authorization header")

    target_org_id = user.current_org_id
    if target_org_id is None:
        return McpAuthFailure(MCP_ORG_FORBIDDEN, "User has no organization context")

    if user.is_super_admin:
        result = await db.execute(
            select(Organization).where(
                Organization.id == target_org_id,
                Organization.deleted_at.is_(None),
            )
        )
        org = result.scalar_one_or_none()
        if org:
            return McpAuthContext(user=user, org=org)

    result = await db.execute(
        select(OrgMembership).where(
            OrgMembership.user_id == user.id,
            OrgMembership.org_id == target_org_id,
            OrgMembership.deleted_at.is_(None),
        )
    )
    membership = result.scalar_one_or_none()
    if membership is None:
        return McpAuthFailure(MCP_ORG_FORBIDDEN, "User is not a member of the organization")

    result = await db.execute(
        select(Organization).where(
            Organization.id == target_org_id,
            Organization.deleted_at.is_(None),
        )
    )
    org = result.scalar_one_or_none()
    if org is None:
        return McpAuthFailure(MCP_ORG_FORBIDDEN, "Organization not found")

    return McpAuthContext(user=user, org=org)
