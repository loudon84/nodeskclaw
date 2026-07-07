"""Portal access grant checks."""

import json

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.portal_access_grant import PortalAccessGrant
from app.models.portal_account import PortalAccount
from app.models.user_cache import UserCache


async def check_portal_permission(
    db: AsyncSession,
    user: UserCache,
    tenant_id: str,
    portal_account_id: str,
    permission: str,
) -> bool:
    if user.is_super_admin:
        return True

    portal = (
        await db.execute(
            select(PortalAccount).where(
                PortalAccount.id == portal_account_id,
                PortalAccount.tenant_id == tenant_id,
                not_deleted(PortalAccount),
            )
        )
    ).scalar_one_or_none()
    if portal is None:
        return False

    grants = (
        await db.execute(
            select(PortalAccessGrant).where(
                PortalAccessGrant.portal_account_id == portal_account_id,
                not_deleted(PortalAccessGrant),
                or_(
                    (PortalAccessGrant.subject_type == "USER") & (PortalAccessGrant.subject_id == user.user_id),
                    (PortalAccessGrant.subject_type == "ROLE") & (PortalAccessGrant.subject_id == (user.org_role or "")),
                    (PortalAccessGrant.subject_type == "DEPARTMENT") & (PortalAccessGrant.subject_id == (user.portal_org_role or "")),
                ),
            )
        )
    ).scalars().all()

    for grant in grants:
        try:
            permissions = json.loads(grant.permissions or "[]")
        except json.JSONDecodeError:
            permissions = []
        if permission in permissions:
            return True
    return False
