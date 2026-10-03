from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
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
from app.models.integration.connect_attempt import IntegrationConnectAttempt
from app.services.external_action.composio_client import ComposioCallError, ComposioClient
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.integration_account_access_resolver import IntegrationAccountAccessResolver
from app.services.remote_agent_provider_service import RemoteAgentRouteError

logger = logging.getLogger("integration.account")
CONNECT_LINK_TTL_SECONDS = 1800
OWNERSHIP_PERSONAL = "PERSONAL"
OWNERSHIP_ORGANIZATION = "ORGANIZATION"

_DESCRIPTOR_KEYS = (
    "integration_account_id",
    "provider",
    "toolkit_slug",
    "connected_account_ref",
)


def correlation_candidates(baseline: list[str] | None, current: list[str] | None) -> list[str]:
    known = {item for item in baseline or [] if item}
    return sorted({item for item in current or [] if item and item not in known})


def provider_user_id(org_id: str, user_id: str) -> str:
    return f"nodeskclaw:{org_id}:{user_id}"


def shared_provider_user_id(org_id: str) -> str:
    return f"nodeskclaw:{org_id}:shared"


def ownership_label(row: IntegrationAccount) -> str:
    if row.owner_type == OWNER_TYPE_ORGANIZATION:
        return OWNERSHIP_ORGANIZATION
    return OWNERSHIP_PERSONAL


async def public_account(
    db: AsyncSession,
    row: IntegrationAccount,
    *,
    org_id: str,
    user_id: str,
) -> dict[str, Any]:
    resolver = IntegrationAccountAccessResolver(db)
    return {
        "id": row.id,
        "provider": row.provider,
        "toolkit_slug": row.toolkit_slug,
        "alias": row.alias,
        "status": row.status,
        "connected_account_id": row.connected_account_id,
        "ownership": ownership_label(row),
        "can_use": await resolver.can_use(org_id=org_id, user_id=user_id, row=row),
        "can_manage": await resolver.can_manage(org_id=org_id, user_id=user_id, row=row),
    }


def account_not_found() -> RemoteAgentRouteError:
    return RemoteAgentRouteError(
        "INTEGRATION_ACCOUNT_NOT_FOUND",
        404,
        40404,
        "errors.remote_agent.integration_account_not_found",
        "外部账号不存在",
    )


def account_inactive() -> RemoteAgentRouteError:
    return RemoteAgentRouteError(
        "INTEGRATION_ACCOUNT_INACTIVE",
        409,
        40908,
        "errors.remote_agent.integration_account_inactive",
        "外部账号不可用",
    )


def account_scope_denied() -> RemoteAgentRouteError:
    return RemoteAgentRouteError(
        "INTEGRATION_SCOPE_DENIED",
        403,
        40303,
        "errors.remote_agent.integration_scope_denied",
        "专家没有可用的外部工具策略",
    )


class IntegrationAccountService:
    def __init__(self, db: AsyncSession, client: ComposioClient | None = None):
        self.db = db
        self.client = client or ComposioClient()
        self.resolver = IntegrationAccountAccessResolver(db)

    async def list_accounts(
        self, *, org_id: str, user_id: str, scope: str = "all"
    ) -> list[dict[str, Any]]:
        if scope not in {"all", "personal", "shared"}:
            raise BadRequestError("scope 无效", "errors.integration.scope_invalid")
        rows = await self.resolver.list_visible(org_id=org_id, user_id=user_id, scope=scope)
        return [await public_account(self.db, row, org_id=org_id, user_id=user_id) for row in rows]

    async def get_account(self, *, org_id: str, user_id: str, account_id: str) -> dict[str, Any]:
        row = await self._visible_or_missing(org_id, user_id, account_id)
        return await public_account(self.db, row, org_id=org_id, user_id=user_id)

    async def connect(
        self,
        *,
        org_id: str,
        user_id: str,
        toolkit_slug: str,
        alias: str | None,
        ownership: str | None = None,
    ) -> dict[str, str]:
        slug = toolkit_slug.strip()
        if not slug:
            raise BadRequestError("toolkit_slug 不能为空", "errors.integration.toolkit_required")
        ownership_value = (ownership or OWNERSHIP_PERSONAL).strip().upper()
        if ownership_value not in {OWNERSHIP_PERSONAL, OWNERSHIP_ORGANIZATION}:
            raise BadRequestError("ownership 无效", "errors.integration.ownership_invalid")
        if ownership_value == OWNERSHIP_ORGANIZATION:
            await PermissionChecker.require_permission(
                self.db, user_id, org_id, "integration:shared:manage"
            )
            user_ref = shared_provider_user_id(org_id)
            owner_type = OWNER_TYPE_ORGANIZATION
            owner_id = org_id
            account_user_id = None
        else:
            user_ref = provider_user_id(org_id, user_id)
            owner_type = OWNER_TYPE_USER
            owner_id = user_id
            account_user_id = user_id
        baseline = await self._baseline_accounts(user_ref, slug)
        try:
            url = await self.client.create_connect_link(provider_user_id=user_ref, toolkit_slug=slug)
        except ComposioCallError as exc:
            raise BadRequestError("暂时无法创建连接链接", "errors.integration.connect_unavailable") from exc
        row = IntegrationAccount(
            id=str(uuid.uuid4()),
            org_id=org_id,
            user_id=account_user_id,
            owner_type=owner_type,
            owner_id=owner_id,
            created_by_user_id=user_id,
            provider="composio",
            toolkit_slug=slug,
            provider_user_id=user_ref,
            alias=(alias or "").strip() or None,
            status="AUTHORIZING",
            auth_version=1,
        )
        self.db.add(row)
        self._add_attempt(row, mode="CONNECT", baseline=baseline, initiated_by_user_id=user_id)
        await self.db.commit()
        return {"account_id": row.id, "url": url}

    async def complete(self, *, org_id: str, user_id: str, account_id: str) -> dict[str, Any]:
        row = await self._manageable_or_missing(org_id, user_id, account_id)
        try:
            current = await self.client.list_active_account_ids(
                provider_user_id=row.provider_user_id,
                toolkit_slug=row.toolkit_slug,
            )
        except ComposioCallError as exc:
            raise ConflictError("外部账号尚未完成连接", "errors.integration.account_not_confirmed") from exc
        if row.status == "ACTIVE" and row.connected_account_id and row.connected_account_id in current:
            return await public_account(self.db, row, org_id=org_id, user_id=user_id)
        attempt = await self._latest_attempt(row.id)
        now = datetime.now(timezone.utc)
        expires_at = None if attempt is None else attempt.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if attempt is None or expires_at is None or expires_at <= now:
            raise ConflictError("外部账号尚未完成连接", "errors.integration.account_not_confirmed")
        if attempt.mode == "REAUTHORIZE":
            if row.connected_account_id and row.connected_account_id in current:
                row.status = "ACTIVE"
                attempt.status = "CONFIRMED"
                attempt.confirmed_connected_account_id = row.connected_account_id
                await self.db.commit()
                return await public_account(self.db, row, org_id=org_id, user_id=user_id)
            raise ConflictError("外部账号尚未完成连接", "errors.integration.account_not_confirmed")
        candidates = correlation_candidates(list(attempt.baseline_account_ids or []), current)
        if len(candidates) != 1:
            if len(candidates) > 1:
                logger.warning(
                    "integration.connect.ambiguous",
                    extra={"trace": "INTEGRATION_ACCOUNT_CORRELATION_AMBIGUOUS", "candidate_count": len(candidates)},
                )
            raise ConflictError("外部账号尚未完成连接", "errors.integration.account_not_confirmed")
        row.connected_account_id = candidates[0]
        row.status = "ACTIVE"
        attempt.status = "CONFIRMED"
        attempt.confirmed_connected_account_id = candidates[0]
        await self.db.commit()
        return await public_account(self.db, row, org_id=org_id, user_id=user_id)

    async def reauthorize(self, *, org_id: str, user_id: str, account_id: str) -> dict[str, str]:
        row = await self._manageable_or_missing(org_id, user_id, account_id)
        baseline = await self._baseline_accounts(row.provider_user_id, row.toolkit_slug)
        try:
            url = await self.client.create_connect_link(
                provider_user_id=row.provider_user_id,
                toolkit_slug=row.toolkit_slug,
            )
        except ComposioCallError as exc:
            raise BadRequestError("暂时无法创建连接链接", "errors.integration.connect_unavailable") from exc
        row.status = "AUTHORIZING"
        self._add_attempt(row, mode="REAUTHORIZE", baseline=baseline, initiated_by_user_id=user_id)
        await self.db.commit()
        return {"account_id": row.id, "url": url}

    async def disconnect(self, *, org_id: str, user_id: str, account_id: str) -> dict[str, Any]:
        row = await self._manageable_or_missing(org_id, user_id, account_id)
        if row.connected_account_id:
            try:
                await self.client.revoke_connected_account(row.connected_account_id)
            except ComposioCallError:
                pass
        row.status = "DISCONNECTED"
        await self.db.commit()
        return await public_account(self.db, row, org_id=org_id, user_id=user_id)

    async def delete_account(self, *, org_id: str, user_id: str, account_id: str) -> None:
        row = await self._manageable_or_missing(org_id, user_id, account_id)
        row.soft_delete()
        await self.db.commit()

    async def list_grants(self, *, org_id: str, user_id: str, account_id: str) -> list[dict[str, str]]:
        row = await self._shared_manageable(org_id, user_id, account_id)
        result = await self.db.execute(
            select(IntegrationAccountGrant).where(
                not_deleted(IntegrationAccountGrant),
                IntegrationAccountGrant.integration_account_id == row.id,
                IntegrationAccountGrant.permission == PERMISSION_USE,
            )
        )
        return [
            {
                "subject_type": grant.subject_type,
                "subject_id": grant.subject_id,
                "permission": grant.permission,
            }
            for grant in result.scalars().all()
        ]

    async def replace_grants(
        self,
        *,
        org_id: str,
        user_id: str,
        account_id: str,
        grants: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        row = await self._shared_manageable(org_id, user_id, account_id)
        normalized: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for item in grants:
            subject_type = str(item.get("subject_type") or "").strip().upper()
            subject_id = str(item.get("subject_id") or "").strip()
            if subject_type == SUBJECT_TYPE_USER:
                if not subject_id:
                    raise BadRequestError("grant subject_id 无效", "errors.integration.grant_invalid")
            elif subject_type == SUBJECT_TYPE_ORG_ROLE:
                if subject_id not in ORG_ROLE_GRANT_SUBJECTS:
                    raise BadRequestError("grant subject_id 无效", "errors.integration.grant_invalid")
            else:
                raise BadRequestError("grant subject_type 无效", "errors.integration.grant_invalid")
            key = (subject_type, subject_id)
            if key in seen:
                continue
            seen.add(key)
            normalized.append(key)
        existing = await self.db.execute(
            select(IntegrationAccountGrant).where(
                not_deleted(IntegrationAccountGrant),
                IntegrationAccountGrant.integration_account_id == row.id,
            )
        )
        active = list(existing.scalars().all())
        desired = set(normalized)
        for grant in active:
            key = (grant.subject_type, grant.subject_id)
            if key not in desired:
                grant.soft_delete()
        active_keys = {(grant.subject_type, grant.subject_id) for grant in active if grant.deleted_at is None}
        for subject_type, subject_id in normalized:
            if (subject_type, subject_id) in active_keys:
                continue
            self.db.add(
                IntegrationAccountGrant(
                    id=str(uuid.uuid4()),
                    org_id=org_id,
                    integration_account_id=row.id,
                    subject_type=subject_type,
                    subject_id=subject_id,
                    permission=PERMISSION_USE,
                    created_by=user_id,
                )
            )
        await self.db.commit()
        return await self.list_grants(org_id=org_id, user_id=user_id, account_id=account_id)

    async def _baseline_accounts(self, provider_user: str, toolkit_slug: str) -> list[str]:
        try:
            return await self.client.list_active_account_ids(
                provider_user_id=provider_user,
                toolkit_slug=toolkit_slug,
            )
        except ComposioCallError as exc:
            raise BadRequestError("暂时无法创建连接链接", "errors.integration.connect_unavailable") from exc

    def _add_attempt(
        self,
        row: IntegrationAccount,
        *,
        mode: str,
        baseline: list[str],
        initiated_by_user_id: str,
    ) -> None:
        started = datetime.now(timezone.utc)
        self.db.add(
            IntegrationConnectAttempt(
                id=str(uuid.uuid4()),
                org_id=row.org_id,
                user_id=row.user_id,
                initiated_by_user_id=initiated_by_user_id,
                owner_type=row.owner_type,
                owner_id=row.owner_id,
                provider_user_id=row.provider_user_id,
                integration_account_id=row.id,
                provider=row.provider,
                toolkit_slug=row.toolkit_slug,
                mode=mode,
                baseline_account_ids=list(baseline),
                status="PENDING",
                started_at=started,
                expires_at=started + timedelta(seconds=CONNECT_LINK_TTL_SECONDS),
            )
        )

    async def _latest_attempt(self, account_id: str) -> IntegrationConnectAttempt | None:
        result = await self.db.execute(
            select(IntegrationConnectAttempt)
            .where(
                not_deleted(IntegrationConnectAttempt),
                IntegrationConnectAttempt.integration_account_id == account_id,
            )
            .order_by(IntegrationConnectAttempt.started_at.desc())
        )
        return result.scalars().first()

    async def _visible_or_missing(self, org_id: str, user_id: str, account_id: str) -> IntegrationAccount:
        rows = await self.resolver.list_visible(org_id=org_id, user_id=user_id, scope="all")
        for row in rows:
            if row.id == account_id:
                return row
        raise NotFoundError("外部账号不存在", "errors.integration.account_not_found")

    async def _manageable_or_missing(self, org_id: str, user_id: str, account_id: str) -> IntegrationAccount:
        row = await self.db.get(IntegrationAccount, account_id)
        if row is None or row.deleted_at is not None or row.org_id != org_id:
            raise NotFoundError("外部账号不存在", "errors.integration.account_not_found")
        if not await self.resolver.can_manage(org_id=org_id, user_id=user_id, row=row):
            raise NotFoundError("外部账号不存在", "errors.integration.account_not_found")
        return row

    async def _shared_manageable(self, org_id: str, user_id: str, account_id: str) -> IntegrationAccount:
        row = await self._manageable_or_missing(org_id, user_id, account_id)
        if row.owner_type != OWNER_TYPE_ORGANIZATION:
            raise BadRequestError("个人账号不支持 Grant", "errors.integration.grant_personal_forbidden")
        if not await PermissionChecker.has_permission(
            self.db, user_id, org_id, "integration:shared:manage"
        ):
            raise ForbiddenError("缺少权限: integration:shared:manage", "errors.skill.permission_denied")
        return row


async def load_accounts_for_run(
    db: AsyncSession,
    *,
    org_id: str,
    user_id: str,
    account_ids: list[str],
) -> list[IntegrationAccount]:
    resolver = IntegrationAccountAccessResolver(db)
    rows: list[IntegrationAccount] = []
    for account_id in account_ids:
        rows.append(
            await resolver.require_use_active(
                org_id=org_id,
                user_id=user_id,
                account_id=account_id,
                require_active=True,
            )
        )
    return rows


def external_descriptors(rows: list[IntegrationAccount]) -> list[dict[str, str]]:
    descriptors = [
        {
            "integration_account_id": row.id,
            "provider": row.provider,
            "toolkit_slug": row.toolkit_slug,
            "connected_account_ref": row.connected_account_id or "",
        }
        for row in rows
    ]
    for item in descriptors:
        unknown = set(item) - set(_DESCRIPTOR_KEYS)
        if unknown:
            raise RuntimeError("descriptor leaked")
    return descriptors
