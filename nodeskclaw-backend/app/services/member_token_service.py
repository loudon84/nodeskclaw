"""Member model credential service.

llm-proxy and Agent Runtime do not read this table. user_llm_configs is not written here.
"""

from __future__ import annotations

import hashlib
import logging
import uuid

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core import hooks
from app.core.config import settings
from app.models.base import not_deleted
from app.models.member_token import MemberToken
from app.models.org_membership import OrgMembership, OrgRole
from app.models.user import User
from app.services.credential_crypto import (
    MemberTokenError,
    decrypt_member_token,
    encrypt_member_token,
    fingerprint_token,
    load_model_token_key,
)
from app.services.member_token_models import EMPTY_MODELS, normalize_models_document
from app.services.model_provider.new_api import NewApiClient, normalize_groups

logger = logging.getLogger(__name__)

PROVIDERS = {"new-api", "deepseek", "custom"}


async def _compensate_external_token(client: NewApiClient, external_id: str) -> None:
    try:
        await client.delete_token(external_id)
    except MemberTokenError as exc:
        raise MemberTokenError(
            502,
            "errors.member_token.new_api_compensation_failed",
            "本地保存失败，且未能删除刚创建的 NEW-API Token，请检查后重试",
        ) from exc


def mask_token(plaintext: str) -> str:
    length = len(plaintext)
    if length <= 8:
        if length < 4:
            return "****"
        return plaintext[:2] + "****" + plaintext[-2:]
    return plaintext[:4] + "**********" + plaintext[-4:]


def token_name_from_email(email: str | None) -> str:
    if not email or "@" not in email:
        raise MemberTokenError(
            400,
            "errors.member_token.name_invalid",
            "成员邮箱无法生成 Token 名称，请先为成员填写有效邮箱",
        )
    local = email.split("@", 1)[0].strip().lower()
    if not local or len(local) > 50:
        raise MemberTokenError(
            400,
            "errors.member_token.name_invalid",
            "成员邮箱前缀无法作为 Token 名称（需要 1 到 50 个字符）",
        )
    return local


def assert_membership_org(membership: OrgMembership | None, org_id: str) -> OrgMembership:
    if membership is None or membership.org_id != org_id or membership.deleted_at is not None:
        raise MemberTokenError(404, "errors.member_token.member_not_found", "成员不存在于该组织")
    return membership


async def list_new_api_groups() -> list[dict]:
    client = NewApiClient()
    return normalize_groups(await client.list_groups())


async def list_member_tokens(
    db: AsyncSession,
    *,
    org_id: str,
    membership_id: str,
    caller: User,
) -> list[dict]:
    membership = await _load_membership(db, membership_id)
    assert_membership_org(membership, org_id)
    await _assert_can_read(db, caller, membership)
    rows = await _active_rows(db, membership.id)
    return [_public(row) for row in rows]


async def get_member_token(
    db: AsyncSession,
    *,
    org_id: str,
    membership_id: str,
    token_id: str,
    caller: User,
) -> dict:
    membership = await _load_membership(db, membership_id)
    assert_membership_org(membership, org_id)
    await _assert_can_read(db, caller, membership)
    row = await _get_row(db, membership.id, token_id)
    return _public(row)


async def create_member_token(
    db: AsyncSession,
    *,
    org_id: str,
    membership_id: str,
    actor: User,
    provider: str,
    provider_group: str | None,
    base_url: str | None,
    plaintext: str | None,
    models: dict | None,
    is_default: bool,
) -> dict:
    if provider not in PROVIDERS:
        raise MemberTokenError(400, "errors.member_token.provider_unsupported", "不支持的模型 Provider")
    membership = await _load_membership(db, membership_id)
    assert_membership_org(membership, org_id)
    document = normalize_models_document(models)
    await _lock(db, membership.id, provider)
    existing = await _find_provider_row(db, membership.id, provider)
    if provider == "new-api":
        return await _provision_new_api(
            db,
            membership=membership,
            actor=actor,
            existing=existing,
            provider_group=provider_group,
            document=document,
            is_default=is_default,
            supplied_plaintext=plaintext,
        )
    if plaintext is None or not base_url:
        raise MemberTokenError(
            400,
            "errors.member_token.manual_fields_required",
            "手工 Provider 需要填写 Base URL 和 API Key",
        )
    if existing is not None:
        raise MemberTokenError(
            409,
            "errors.member_token.provider_exists",
            "该成员已有此 Provider 的凭证，请直接修改",
        )
    row = await _insert_local(
        db,
        membership=membership,
        actor_id=actor.id,
        provider=provider,
        base_url=base_url.strip(),
        plaintext=plaintext,
        provider_group=None,
        token_name=None,
        external_token_id=None,
        source="manual",
        sync_status="manual",
        document=document,
        is_default=is_default,
    )
    await db.commit()
    await db.refresh(row)
    await _audit(actor.id, membership.org_id, "member_token.created", row.id, provider=provider, source="manual")
    return {**_public(row), "created": True, "plaintext_token": None}


async def update_member_token(
    db: AsyncSession,
    *,
    org_id: str,
    membership_id: str,
    token_id: str,
    actor: User,
    fields: dict,
) -> dict:
    membership = await _load_membership(db, membership_id)
    assert_membership_org(membership, org_id)
    row = await _get_row(db, membership.id, token_id)
    if "models" in fields and fields["models"] is not None:
        document = normalize_models_document(fields["models"])
    else:
        document = None
    if row.provider == "new-api":
        await _update_new_api(db, membership, row, fields)
    else:
        await _update_manual(row, fields)
    if document is not None:
        row.models = document
    if fields.get("is_default") is True:
        await _clear_default(db, membership.id, except_id=row.id)
        row.is_default = True
    elif fields.get("is_default") is False:
        row.is_default = False
    await db.commit()
    await _audit(actor.id, membership.org_id, "member_token.updated", row.id, provider=row.provider)
    return _public(row)


async def delete_member_token(
    db: AsyncSession,
    *,
    org_id: str,
    membership_id: str,
    token_id: str,
    actor: User,
) -> None:
    membership = await _load_membership(db, membership_id)
    assert_membership_org(membership, org_id)
    row = await _get_row(db, membership.id, token_id)
    manual = row.provider != "new-api"
    if row.provider == "new-api" and row.external_token_id:
        try:
            await NewApiClient().delete_token(row.external_token_id)
        except MemberTokenError as exc:
            await _mark_control_error(db, row, exc)
            raise
    row_id = row.id
    provider = row.provider
    row.is_active = False
    row.soft_delete()
    await db.commit()
    await _audit(
        actor.id,
        membership.org_id,
        "member_token.deleted",
        row_id,
        provider=provider,
        external_revoke_supported=not manual,
    )


async def revoke_tokens_for_removed_member(
    db: AsyncSession,
    membership: OrgMembership,
    *,
    actor_id: str | None,
) -> int:
    rows = await _active_rows(db, membership.id)
    client = NewApiClient()
    for row in rows:
        row.is_active = False
        if row.provider != "new-api" or not row.external_token_id:
            row.soft_delete()
            continue
        try:
            client.require_configured()
            await client.delete_token(row.external_token_id)
        except MemberTokenError as exc:
            row.sync_status = "revoke_pending"
            row.last_sync_error = exc.message_key
            logger.warning(
                "member token revoke pending membership=%s token=%s",
                membership.id,
                row.id,
            )
            continue
        row.soft_delete()
        row.sync_status = "synced"
        row.last_sync_error = None
    if actor_id:
        logger.info("member token revoke scheduled membership=%s count=%s", membership.id, len(rows))
    return len(rows)


async def _provision_new_api(
    db: AsyncSession,
    *,
    membership: OrgMembership,
    actor: User,
    existing: MemberToken | None,
    provider_group: str | None,
    document: dict,
    is_default: bool,
    supplied_plaintext: str | None,
) -> dict:
    if supplied_plaintext:
        raise MemberTokenError(
            400,
            "errors.member_token.managed_field_forbidden",
            "NEW-API 凭证由系统签发，不能手工填写 Key",
        )
    if not provider_group or provider_group == "auto":
        raise MemberTokenError(400, "errors.member_token.group_required", "请选择 NEW-API 分组")
    model_url = (settings.NEW_API_MODEL_BASE_URL or "").strip()
    if not model_url:
        raise MemberTokenError(
            503,
            "errors.member_token.new_api_not_configured",
            "NEW_API_MODEL_BASE_URL 未配置，请检查 backend 配置",
        )
    load_model_token_key()
    name = token_name_from_email(membership.user.email if membership.user else None)
    if existing is not None:
        if existing.provider_group == provider_group:
            return {**_public(existing), "created": False, "plaintext_token": None}
        raise MemberTokenError(
            409,
            "errors.member_token.provider_exists",
            "该成员已有 NEW-API 凭证且分组不同，请使用修改而不是重新创建",
        )
    client = NewApiClient()
    groups = normalize_groups(await client.list_groups())
    if provider_group not in {item["value"] for item in groups}:
        raise MemberTokenError(400, "errors.member_token.group_invalid", "所选分组在 NEW-API 中不存在")
    matches = await client.search_exact(name)
    if matches:
        raise MemberTokenError(
            409,
            "errors.member_token.name_conflict",
            "NEW-API 上已有同名 Token，系统不会自动认领，请更换成员邮箱或清理该 Token",
        )
    await client.create_token(name, provider_group)
    created = await client.search_exact(name)
    if len(created) != 1 or created[0].get("id") is None:
        raise MemberTokenError(
            409,
            "errors.member_token.name_conflict",
            "创建后未能确认唯一的 NEW-API Token，请检查后重试，系统不会自动认领",
        )
    external_id = str(created[0]["id"])
    plaintext = await client.fetch_key(external_id)
    row = await _insert_local(
        db,
        membership=membership,
        actor_id=actor.id,
        provider="new-api",
        base_url=model_url,
        plaintext=plaintext,
        provider_group=provider_group,
        token_name=name,
        external_token_id=external_id,
        source="auto",
        sync_status="synced",
        document=document,
        is_default=is_default,
    )
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        await _compensate_external_token(client, external_id)
        raise
    await db.refresh(row)
    await _audit(actor.id, membership.org_id, "member_token.created", row.id, provider="new-api", source="auto")
    return {**_public(row), "created": True, "plaintext_token": plaintext}


async def _update_new_api(db: AsyncSession, membership: OrgMembership, row: MemberToken, fields: dict) -> None:
    if fields.get("base_url") or fields.get("token"):
        raise MemberTokenError(
            400,
            "errors.member_token.managed_field_forbidden",
            "NEW-API 的 Base URL 和 Key 不能手工修改",
        )
    client = NewApiClient()
    if "provider_group" in fields and fields["provider_group"] is not None:
        group = fields["provider_group"]
        if group == "auto":
            raise MemberTokenError(400, "errors.member_token.group_invalid", "不能把分组改为 auto")
        groups = normalize_groups(await client.list_groups())
        if group not in {item["value"] for item in groups}:
            raise MemberTokenError(400, "errors.member_token.group_invalid", "所选分组在 NEW-API 中不存在")
        if not row.external_token_id:
            await _mark_control_error(
                db,
                row,
                MemberTokenError(409, "errors.member_token.external_missing", "缺少外部 Token，无法修改分组"),
            )
            raise MemberTokenError(409, "errors.member_token.external_missing", "缺少外部 Token，无法修改分组")
        try:
            await client.update_group(row.external_token_id, group)
        except MemberTokenError as exc:
            await _mark_control_error(db, row, exc)
            raise
        row.provider_group = group
        row.sync_status = "synced"
        row.last_sync_error = None
    if "is_active" in fields and fields["is_active"] is not None and fields["is_active"] != row.is_active:
        if not row.external_token_id:
            await _mark_control_error(
                db,
                row,
                MemberTokenError(409, "errors.member_token.external_missing", "缺少外部 Token，无法修改启用状态"),
            )
            raise MemberTokenError(409, "errors.member_token.external_missing", "缺少外部 Token，无法修改启用状态")
        try:
            await client.set_status(row.external_token_id, bool(fields["is_active"]))
        except MemberTokenError as exc:
            await _mark_control_error(db, row, exc)
            raise
        row.is_active = bool(fields["is_active"])
        row.sync_status = "synced"
        row.last_sync_error = None


async def _update_manual(row: MemberToken, fields: dict) -> None:
    if fields.get("provider_group"):
        raise MemberTokenError(400, "errors.member_token.group_invalid", "手工 Provider 没有 NEW-API 分组")
    if fields.get("base_url"):
        row.base_url = str(fields["base_url"]).strip()
    if fields.get("token"):
        row.token = encrypt_member_token(
            fields["token"],
            token_id=row.id,
            member_id=row.member_id,
            provider=row.provider,
        )
        row.token_fingerprint = fingerprint_token(fields["token"])
    if fields.get("is_active") is not None:
        row.is_active = bool(fields["is_active"])


async def _insert_local(
    db: AsyncSession,
    *,
    membership: OrgMembership,
    actor_id: str,
    provider: str,
    base_url: str,
    plaintext: str,
    provider_group: str | None,
    token_name: str | None,
    external_token_id: str | None,
    source: str,
    sync_status: str,
    document: dict,
    is_default: bool,
) -> MemberToken:
    if is_default:
        await _clear_default(db, membership.id, except_id=None)
    token_id = str(uuid.uuid4())
    row = MemberToken(
        id=token_id,
        member_id=membership.id,
        provider=provider,
        base_url=base_url,
        token=encrypt_member_token(
            plaintext,
            token_id=token_id,
            member_id=membership.id,
            provider=provider,
        ),
        token_fingerprint=fingerprint_token(plaintext),
        models=document or dict(EMPTY_MODELS),
        provider_group=provider_group,
        external_token_id=external_token_id,
        token_name=token_name,
        source=source,
        is_active=True,
        is_default=is_default,
        sync_status=sync_status,
        created_by=actor_id,
    )
    db.add(row)
    await db.flush()
    return row


async def _mark_control_error(db: AsyncSession, row: MemberToken, exc: MemberTokenError) -> None:
    row.sync_status = "error"
    row.last_sync_error = exc.message_key
    await db.commit()


async def _clear_default(db: AsyncSession, member_id: str, except_id: str | None) -> None:
    stmt = (
        update(MemberToken)
        .where(
            MemberToken.member_id == member_id,
            MemberToken.is_default.is_(True),
            MemberToken.deleted_at.is_(None),
        )
        .values(is_default=False)
    )
    if except_id:
        stmt = stmt.where(MemberToken.id != except_id)
    await db.execute(stmt)


async def _lock(db: AsyncSession, member_id: str, provider: str) -> None:
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return
    digest = hashlib.sha256(f"{member_id}\0{provider}".encode()).hexdigest()[:15]
    await db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": int(digest, 16)})


async def _load_membership(db: AsyncSession, membership_id: str) -> OrgMembership | None:
    result = await db.execute(
        select(OrgMembership)
        .options(selectinload(OrgMembership.user))
        .where(OrgMembership.id == membership_id)
    )
    return result.scalar_one_or_none()


async def _assert_can_read(db: AsyncSession, caller: User, membership: OrgMembership) -> None:
    if caller.is_super_admin or caller.id == membership.user_id:
        return
    result = await db.execute(
        select(OrgMembership).where(
            OrgMembership.user_id == caller.id,
            OrgMembership.org_id == membership.org_id,
            OrgMembership.role == OrgRole.admin,
            not_deleted(OrgMembership),
        )
    )
    if result.scalar_one_or_none() is None:
        raise MemberTokenError(403, "errors.member_token.forbidden", "只能查看本人的模型凭证")


async def _active_rows(db: AsyncSession, member_id: str) -> list[MemberToken]:
    result = await db.execute(
        select(MemberToken)
        .where(MemberToken.member_id == member_id, not_deleted(MemberToken))
        .order_by(MemberToken.created_at.asc())
    )
    return list(result.scalars().all())


async def _find_provider_row(db: AsyncSession, member_id: str, provider: str) -> MemberToken | None:
    result = await db.execute(
        select(MemberToken).where(
            MemberToken.member_id == member_id,
            MemberToken.provider == provider,
            not_deleted(MemberToken),
        )
    )
    return result.scalar_one_or_none()


async def _get_row(db: AsyncSession, member_id: str, token_id: str) -> MemberToken:
    result = await db.execute(
        select(MemberToken).where(
            MemberToken.id == token_id,
            MemberToken.member_id == member_id,
            not_deleted(MemberToken),
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise MemberTokenError(404, "errors.member_token.not_found", "模型凭证不存在")
    return row


def _public(row: MemberToken) -> dict:
    try:
        plaintext = decrypt_member_token(
            row.token,
            token_id=row.id,
            member_id=row.member_id,
            provider=row.provider,
        )
        masked = mask_token(plaintext)
    except MemberTokenError:
        raise
    items = row.models.get("items") if isinstance(row.models, dict) else []
    return {
        "id": row.id,
        "member_id": row.member_id,
        "provider": row.provider,
        "base_url": row.base_url,
        "token_masked": masked,
        "token_name": row.token_name,
        "provider_group": row.provider_group,
        "models": row.models,
        "model_count": len(items or []),
        "source": row.source,
        "is_active": row.is_active,
        "is_default": row.is_default,
        "sync_status": row.sync_status,
        "last_sync_error": row.last_sync_error,
        "created": None,
        "plaintext_token": None,
    }


async def _audit(actor_id: str, org_id: str, action: str, target_id: str, **details) -> None:
    safe = {key: value for key, value in details.items() if key not in {"token", "plaintext", "plaintext_token"}}
    await hooks.emit(
        "operation_audit",
        action=action,
        target_type="member_token",
        target_id=target_id,
        actor_id=actor_id,
        org_id=org_id,
        details=safe,
    )
