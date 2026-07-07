"""Portal account CRUD."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.base import not_deleted
from app.models.portal_access_grant import PortalAccessGrant
from app.models.portal_account import PortalAccount
from app.models.user_cache import UserCache
from app.schemas.portal_account import (
    PortalAccessGrantCreate,
    PortalAccountCreate,
    PortalAccountUpdate,
)
from app.services.json_utils import dumps_json


async def list_portal_accounts(db: AsyncSession, tenant_id: str) -> list[PortalAccount]:
    result = await db.execute(
        select(PortalAccount).where(
            PortalAccount.tenant_id == tenant_id,
            not_deleted(PortalAccount),
        ).order_by(PortalAccount.created_at.desc())
    )
    return list(result.scalars().all())


async def get_portal_account(db: AsyncSession, tenant_id: str, account_id: str) -> PortalAccount:
    account = (
        await db.execute(
            select(PortalAccount).where(
                PortalAccount.id == account_id,
                PortalAccount.tenant_id == tenant_id,
                not_deleted(PortalAccount),
            )
        )
    ).scalar_one_or_none()
    if account is None:
        raise NotFoundError(message="Portal 账号不存在", message_key="errors.autotask.portal_not_found")
    return account


async def create_portal_account(
    db: AsyncSession,
    tenant_id: str,
    user: UserCache,
    body: PortalAccountCreate,
) -> PortalAccount:
    existing = (
        await db.execute(
            select(PortalAccount).where(
                PortalAccount.tenant_id == tenant_id,
                PortalAccount.entity_type == body.entity_type,
                PortalAccount.portal_url == body.portal_url,
                PortalAccount.login_account == body.login_account,
                not_deleted(PortalAccount),
            )
        )
    ).scalar_one_or_none()
    if existing:
        raise ConflictError(
            message="Portal 账号已存在",
            message_key="errors.autotask.portal_duplicate",
        )

    account = PortalAccount(
        tenant_id=tenant_id,
        entity_type=body.entity_type,
        erp_entity_code=body.erp_entity_code,
        erp_entity_name=body.erp_entity_name,
        portal_name=body.portal_name,
        portal_url=body.portal_url,
        login_account=body.login_account,
        credential_ref=body.credential_ref,
        client_open_mode=body.client_open_mode,
        client_session_partition=body.client_session_partition,
        rpa_profile_id=body.rpa_profile_id,
        status=body.status,
        owner_dept_id=body.owner_dept_id,
        created_by=user.user_id,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


async def update_portal_account(
    db: AsyncSession,
    tenant_id: str,
    account_id: str,
    body: PortalAccountUpdate,
) -> PortalAccount:
    account = await get_portal_account(db, tenant_id, account_id)
    for field, value in body.model_dump(exclude_unset=True, by_alias=False).items():
        setattr(account, field, value)
    await db.commit()
    await db.refresh(account)
    return account


async def delete_portal_account(db: AsyncSession, tenant_id: str, account_id: str) -> None:
    account = await get_portal_account(db, tenant_id, account_id)
    account.soft_delete()
    await db.commit()


async def list_access_grants(db: AsyncSession, tenant_id: str, account_id: str) -> list[PortalAccessGrant]:
    await get_portal_account(db, tenant_id, account_id)
    result = await db.execute(
        select(PortalAccessGrant).where(
            PortalAccessGrant.portal_account_id == account_id,
            not_deleted(PortalAccessGrant),
        )
    )
    return list(result.scalars().all())


async def create_access_grant(
    db: AsyncSession,
    tenant_id: str,
    account_id: str,
    user: UserCache,
    body: PortalAccessGrantCreate,
) -> PortalAccessGrant:
    await get_portal_account(db, tenant_id, account_id)
    grant = PortalAccessGrant(
        portal_account_id=account_id,
        subject_type=body.subject_type,
        subject_id=body.subject_id,
        permissions=dumps_json(body.permissions),
        granted_by=user.user_id,
        granted_at=datetime.now(UTC).isoformat(),
    )
    db.add(grant)
    await db.commit()
    await db.refresh(grant)
    return grant
