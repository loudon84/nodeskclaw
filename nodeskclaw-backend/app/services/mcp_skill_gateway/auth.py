from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.org_membership import OrgMembership
from app.models.organization import Organization
from app.models.user import User


@dataclass
class McpAuthContext:
    user: User
    org: Organization


@dataclass
class McpAuthFailure:
    error_code: str
    reason: str


async def resolve_mcp_user(
    authorization: str | None,
    db: AsyncSession,
) -> McpAuthContext | McpAuthFailure:
    from app.services.mcp_skill_gateway.errors import MCP_FORBIDDEN, MCP_UNAUTHORIZED

    if not authorization or not authorization.startswith("Bearer "):
        return McpAuthFailure(MCP_UNAUTHORIZED, "Missing or invalid Authorization header")

    token = authorization[7:].strip()
    if not token:
        return McpAuthFailure(MCP_UNAUTHORIZED, "Missing or invalid Authorization header")

    from app.core.security import _get_user_by_token

    try:
        user = await _get_user_by_token(token, db)
    except HTTPException:
        return McpAuthFailure(MCP_UNAUTHORIZED, "Missing or invalid Authorization header")

    target_org_id = user.current_org_id
    if target_org_id is None:
        return McpAuthFailure(MCP_FORBIDDEN, "User has no organization context")

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
        return McpAuthFailure(MCP_FORBIDDEN, "User is not a member of the organization")

    result = await db.execute(
        select(Organization).where(
            Organization.id == target_org_id,
            Organization.deleted_at.is_(None),
        )
    )
    org = result.scalar_one_or_none()
    if org is None:
        return McpAuthFailure(MCP_FORBIDDEN, "Organization not found")

    return McpAuthContext(user=user, org=org)
