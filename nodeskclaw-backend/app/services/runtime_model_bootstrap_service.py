"""Runtime provider bootstrap. Reads the current user's default member token and never calls NEW-API."""

from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import hooks
from app.models.base import not_deleted
from app.models.member_token import MemberToken
from app.models.org_membership import OrgMembership
from app.models.user import User
from app.services.credential_crypto import MemberTokenError, decrypt_member_token
from app.services.model_provider.member_model_discovery import normalize_model_base


async def build_runtime_bootstrap(
    db: AsyncSession,
    *,
    user: User,
    org_id: str,
    consumer: str,
    runtime: str,
) -> dict:
    membership = await _membership(db, user.id, org_id)
    token = None if membership is None else await _default_token(db, membership.id)
    if isinstance(token, list):
        data = _not_ready("MODEL_CREDENTIAL_INVALID", None)
    else:
        data = _evaluate(token)
    await hooks.emit(
        "operation_audit",
        action="member_token.bootstrapped",
        target_type="member_token",
        target_id=token.id if isinstance(token, MemberToken) else None,
        actor_id=user.id,
        org_id=org_id,
        details={
            "provider": data.get("provider"),
            "member_id": membership.id if membership is not None else None,
            "state": data["state"],
            "revision": data.get("revision"),
            "consumer": consumer,
            "runtime": runtime,
        },
    )
    return data


async def _membership(db: AsyncSession, user_id: str, org_id: str) -> OrgMembership | None:
    result = await db.execute(
        select(OrgMembership).where(
            OrgMembership.user_id == user_id,
            OrgMembership.org_id == org_id,
            not_deleted(OrgMembership),
        )
    )
    return result.scalar_one_or_none()


async def _default_token(db: AsyncSession, member_id: str) -> MemberToken | list | None:
    result = await db.execute(
        select(MemberToken).where(
            MemberToken.member_id == member_id,
            MemberToken.is_default.is_(True),
            not_deleted(MemberToken),
        )
    )
    rows = list(result.scalars().all())
    if len(rows) > 1:
        return rows
    return rows[0] if rows else None


def _evaluate(row: MemberToken | None) -> dict:
    if row is None:
        return _not_ready("MODEL_NOT_CONFIGURED", None)
    if row.sync_status == "revoke_pending":
        return _not_ready("MODEL_CREDENTIAL_CLOSING", row.provider)
    if not row.is_active:
        return _not_ready("MODEL_CREDENTIAL_DISABLED", row.provider)
    if row.provider != "new-api":
        return _not_ready("MODEL_PROVIDER_UNSUPPORTED", row.provider)
    if row.source == "auto" and row.sync_status != "synced":
        return _not_ready("MODEL_SYNC_NOT_READY", row.provider)
    if not normalize_model_base(row.base_url):
        return _not_ready("MODEL_CREDENTIAL_INVALID", row.provider)
    document = row.models if isinstance(row.models, dict) else {}
    items = document.get("items") if isinstance(document.get("items"), list) else []
    enabled = [item for item in items if isinstance(item, dict) and item.get("enabled") is True]
    default_model = document.get("default_model")
    if not enabled:
        return _not_ready("MODEL_LIST_EMPTY", row.provider)
    if not isinstance(default_model, str) or not default_model:
        return _not_ready("MODEL_DEFAULT_NOT_SET", row.provider)
    if default_model not in {item.get("id") for item in enabled}:
        return _not_ready("MODEL_DEFAULT_INVALID", row.provider)
    try:
        plaintext = decrypt_member_token(
            row.token,
            token_id=row.id,
            member_id=row.member_id,
            provider=row.provider,
        )
    except MemberTokenError:
        return _not_ready("MODEL_CREDENTIAL_INVALID", row.provider)
    return {
        "ready": True,
        "state": "READY",
        "revision": _revision(row),
        "provider": row.provider,
        "base_url": row.base_url,
        "api_key": plaintext,
        "provider_group": row.provider_group,
        "default_model": default_model,
        "models": [_public_model(item) for item in enabled],
    }


def _not_ready(state: str, provider: str | None) -> dict:
    data = {"ready": False, "state": state, "revision": None}
    if provider:
        data["provider"] = provider
    return data


def _public_model(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "display_name": item.get("display_name") or item.get("id"),
        "context_window": item.get("context_window"),
        "max_output_tokens": item.get("max_output_tokens"),
        "capabilities": item.get("capabilities") if isinstance(item.get("capabilities"), list) else [],
        "settings": item.get("settings") if isinstance(item.get("settings"), dict) else {"extra": {}},
    }


def _revision(row: MemberToken) -> str:
    updated = row.updated_at.isoformat() if row.updated_at is not None else ""
    raw = f"{row.id}|{updated}|{row.token_fingerprint or ''}"
    return hashlib.sha256(raw.encode()).hexdigest()
