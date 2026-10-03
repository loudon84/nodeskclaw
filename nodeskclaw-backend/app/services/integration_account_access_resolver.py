from __future__ import annotations

import logging

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.integration.account import (
    OWNER_TYPE_ORGANIZATION,
    OWNER_TYPE_USER,
    IntegrationAccount,
)
from app.models.integration.account_grant import (
    ORG_ROLE_GRANT_SUBJECTS,
    PERMISSION_USE,
    SUBJECT_TYPE_ORG_ROLE,
    SUBJECT_TYPE_USER,
    IntegrationAccountGrant,
)
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.remote_agent_provider_service import RemoteAgentRouteError

logger = logging.getLogger("integration.access")


def account_not_found() -> RemoteAgentRouteError:
    return RemoteAgentRouteError(
        "INTEGRATION_ACCOUNT_NOT_FOUND",
        404,
        40404,
        "errors.remote_agent.integration_account_not_found",
        "外部账号不存在",
    )


class IntegrationAccountAccessResolver:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def can_manage(
        self,
        *,
        org_id: str,
        user_id: str,
        row: IntegrationAccount,
    ) -> bool:
        if row.org_id != org_id or row.deleted_at is not None:
            return False
        if row.owner_type == OWNER_TYPE_USER:
            return row.owner_id == user_id or row.user_id == user_id
        if row.owner_type == OWNER_TYPE_ORGANIZATION:
            return await PermissionChecker.has_permission(
                self.db, user_id, org_id, "integration:shared:manage"
            )
        return False

    async def can_use(
        self,
        *,
        org_id: str,
        user_id: str,
        row: IntegrationAccount,
        role: str | None = None,
    ) -> bool:
        if row.org_id != org_id or row.deleted_at is not None:
            return False
        if row.owner_type == OWNER_TYPE_USER:
            return row.owner_id == user_id or row.user_id == user_id
        if row.owner_type != OWNER_TYPE_ORGANIZATION:
            return False
        current_role = role
        if current_role is None:
            current_role = await PermissionChecker.get_user_role(self.db, user_id, org_id)
        return await self._has_use_grant(row.id, user_id=user_id, role=current_role)

    async def require_use_active(
        self,
        *,
        org_id: str,
        user_id: str,
        account_id: str,
        require_active: bool = True,
    ) -> IntegrationAccount:
        row = await self.db.get(IntegrationAccount, account_id)
        if row is None or row.deleted_at is not None or row.org_id != org_id:
            raise account_not_found()
        if not await self.can_use(org_id=org_id, user_id=user_id, row=row):
            logger.info(
                "integration.use_denied",
                extra={
                    "trace": "INTEGRATION_ACCOUNT_USE_DENIED",
                    "account_id": account_id,
                    "user_id": user_id,
                    "org_id": org_id,
                },
            )
            raise account_not_found()
        if require_active and row.status != "ACTIVE":
            raise RemoteAgentRouteError(
                "INTEGRATION_ACCOUNT_INACTIVE",
                409,
                40908,
                "errors.remote_agent.integration_account_inactive",
                "外部账号不可用",
            )
        if row.provider != "composio":
            raise RemoteAgentRouteError(
                "INTEGRATION_SCOPE_DENIED",
                403,
                40303,
                "errors.remote_agent.integration_scope_denied",
                "专家没有可用的外部工具策略",
            )
        return row

    async def list_visible(
        self,
        *,
        org_id: str,
        user_id: str,
        scope: str = "all",
    ) -> list[IntegrationAccount]:
        role = await PermissionChecker.get_user_role(self.db, user_id, org_id)
        can_manage_shared = await PermissionChecker.has_permission(
            self.db, user_id, org_id, "integration:shared:manage"
        )
        rows = await self._org_rows(org_id)
        visible: list[IntegrationAccount] = []
        for row in rows:
            ownership = "ORGANIZATION" if row.owner_type == OWNER_TYPE_ORGANIZATION else "PERSONAL"
            if scope == "personal" and ownership != "PERSONAL":
                continue
            if scope == "shared" and ownership != "ORGANIZATION":
                continue
            if ownership == "PERSONAL":
                if row.owner_id == user_id or row.user_id == user_id:
                    visible.append(row)
                continue
            use = await self.can_use(org_id=org_id, user_id=user_id, row=row, role=role)
            if use or can_manage_shared:
                visible.append(row)
        return visible

    async def _has_use_grant(self, account_id: str, *, user_id: str, role: str | None) -> bool:
        role_clause = None
        if role and role in ORG_ROLE_GRANT_SUBJECTS:
            role_clause = (
                (IntegrationAccountGrant.subject_type == SUBJECT_TYPE_ORG_ROLE)
                & (IntegrationAccountGrant.subject_id == role)
            )
        user_clause = (
            (IntegrationAccountGrant.subject_type == SUBJECT_TYPE_USER)
            & (IntegrationAccountGrant.subject_id == user_id)
        )
        subject_filter = or_(user_clause, role_clause) if role_clause is not None else user_clause
        result = await self.db.execute(
            select(IntegrationAccountGrant.id)
            .where(
                not_deleted(IntegrationAccountGrant),
                IntegrationAccountGrant.integration_account_id == account_id,
                IntegrationAccountGrant.permission == PERMISSION_USE,
                subject_filter,
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _org_rows(self, org_id: str) -> list[IntegrationAccount]:
        result = await self.db.execute(
            select(IntegrationAccount).where(
                not_deleted(IntegrationAccount),
                IntegrationAccount.org_id == org_id,
            )
        )
        return list(result.scalars().all())
