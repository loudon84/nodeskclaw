from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.org_membership import OrgMembership
from app.models.organization import Organization
from app.models.user import User
from app.services.expert_gateway.expert_permission_service import ExpertPermissionService
from app.services.remote_acp.errors import (
    AUTH_REQUIRED,
    EXPERT_FORBIDDEN,
    EXPERT_NOT_FOUND,
    ORG_FORBIDDEN,
    RemoteAcpError,
    TRANSPORT_UNSUPPORTED,
)
from app.services.remote_expert_catalog_service import RemoteExpertCatalogService


FORBIDDEN_QUERY_KEYS = frozenset({"token", "access_token", "authorization", "credential"})


def assert_no_query_credentials(query_params) -> None:
    for key in query_params.keys():
        if str(key).lower() in FORBIDDEN_QUERY_KEYS:
            raise AUTH_REQUIRED


async def load_org_for_user(db: AsyncSession, user: User, org_id: str) -> Organization:
    if user.is_super_admin:
        result = await db.execute(
            select(Organization).where(Organization.id == org_id, Organization.deleted_at.is_(None))
        )
        org = result.scalar_one_or_none()
        if org:
            return org
    result = await db.execute(
        select(OrgMembership).where(
            OrgMembership.user_id == user.id,
            OrgMembership.org_id == org_id,
            OrgMembership.deleted_at.is_(None),
        )
    )
    membership = result.scalar_one_or_none()
    if not membership:
        raise ORG_FORBIDDEN
    org_result = await db.execute(
        select(Organization).where(Organization.id == org_id, Organization.deleted_at.is_(None))
    )
    org = org_result.scalar_one_or_none()
    if not org:
        raise ORG_FORBIDDEN
    return org


async def authorize_expert_invoke(db: AsyncSession, user: User, org_id: str, agent_ref: str):
    try:
        await ExpertPermissionService.require(db, user.id, org_id, "expert:invoke")
    except ForbiddenError as exc:
        raise EXPERT_FORBIDDEN from exc
    try:
        item = await RemoteExpertCatalogService(db).get_item(org_id, agent_ref)
    except NotFoundError as exc:
        raise EXPERT_NOT_FOUND from exc
    return item


def require_subprotocol(offered: str, expected: str) -> None:
    protocols = [item.strip() for item in (offered or "").split(",") if item.strip()]
    if expected not in protocols:
        raise TRANSPORT_UNSUPPORTED
