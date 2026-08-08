"""Retrieval Profile DRAFT/ACTIVE/ARCHIVED lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.enums import AuditAction, DEFAULT_RETRIEVAL_CONFIG, ProfileStatus, SetPermission
from app.models.knowledge_set import KnowledgeSet
from app.models.retrieval_profile import RetrievalProfile
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_set_service
from app.services.audit_service import write_audit
from app.services.permission_service import has_set_permission


def merge_profile_config(config: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(DEFAULT_RETRIEVAL_CONFIG)
    if config:
        merged.update(config)
    return merged


async def get_active_profile(db: AsyncSession, knowledge_set_id: str) -> RetrievalProfile | None:
    result = await db.execute(
        select(RetrievalProfile).where(
            RetrievalProfile.knowledge_set_id == knowledge_set_id,
            RetrievalProfile.status == ProfileStatus.active.value,
            not_deleted(RetrievalProfile),
        )
    )
    return result.scalar_one_or_none()


async def _get_profile_or_404(db: AsyncSession, profile_id: str) -> RetrievalProfile:
    row = await db.get(RetrievalProfile, profile_id)
    if row is None or row.deleted_at is not None:
        raise NotFoundError(message="检索配置不存在", message_key="errors.knowledge.profile_not_found")
    return row


async def _require_set_read(
    db: AsyncSession,
    member: KnowledgePrincipal,
    knowledge_set_id: str,
) -> KnowledgeSet:
    return await knowledge_set_service.get_knowledge_set(db, member, knowledge_set_id)


async def _require_set_manage(
    db: AsyncSession,
    member: KnowledgePrincipal,
    knowledge_set_id: str,
) -> KnowledgeSet:
    ks = await knowledge_set_service.get_knowledge_set(db, member, knowledge_set_id)
    if not await has_set_permission(db, member, ks, SetPermission.manage.value):
        raise ForbiddenError()
    return ks


async def list_profiles(
    db: AsyncSession,
    member: KnowledgePrincipal,
    knowledge_set_id: str,
) -> list[RetrievalProfile]:
    await _require_set_read(db, member, knowledge_set_id)
    result = await db.execute(
        select(RetrievalProfile)
        .where(
            RetrievalProfile.knowledge_set_id == knowledge_set_id,
            not_deleted(RetrievalProfile),
        )
        .order_by(RetrievalProfile.version.desc())
    )
    return list(result.scalars().all())


async def get_profile(
    db: AsyncSession,
    member: KnowledgePrincipal,
    profile_id: str,
) -> RetrievalProfile:
    row = await _get_profile_or_404(db, profile_id)
    await _require_set_read(db, member, row.knowledge_set_id)
    return row


async def create_draft(
    db: AsyncSession,
    member: KnowledgePrincipal,
    knowledge_set_id: str,
    *,
    config: dict[str, Any] | None = None,
) -> RetrievalProfile:
    await _require_set_manage(db, member, knowledge_set_id)
    max_version = await db.scalar(
        select(func.coalesce(func.max(RetrievalProfile.version), 0)).where(
            RetrievalProfile.knowledge_set_id == knowledge_set_id,
            not_deleted(RetrievalProfile),
        )
    )
    row = RetrievalProfile(
        knowledge_set_id=knowledge_set_id,
        version=int(max_version or 0) + 1,
        config=merge_profile_config(config),
        status=ProfileStatus.draft.value,
        created_by_member_id=member.member_id,
    )
    db.add(row)
    await db.flush()
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.profile_create.value,
        resource_type="retrieval_profile",
        resource_id=row.id,
        details={"knowledge_set_id": knowledge_set_id, "version": row.version},
    )
    await db.commit()
    await db.refresh(row)
    return row


async def update_draft(
    db: AsyncSession,
    member: KnowledgePrincipal,
    profile_id: str,
    *,
    config: dict[str, Any],
) -> RetrievalProfile:
    row = await _get_profile_or_404(db, profile_id)
    await _require_set_manage(db, member, row.knowledge_set_id)
    if row.status != ProfileStatus.draft.value:
        raise BadRequestError(
            message="仅草稿配置可修改",
            message_key="errors.knowledge.profile_not_draft",
        )
    row.config = merge_profile_config(config)
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.profile_update.value,
        resource_type="retrieval_profile",
        resource_id=row.id,
        details={"version": row.version},
    )
    await db.commit()
    await db.refresh(row)
    return row


async def publish(
    db: AsyncSession,
    member: KnowledgePrincipal,
    profile_id: str,
) -> RetrievalProfile:
    row = await _get_profile_or_404(db, profile_id)
    await _require_set_manage(db, member, row.knowledge_set_id)
    if row.status != ProfileStatus.draft.value:
        raise BadRequestError(
            message="仅草稿配置可发布",
            message_key="errors.knowledge.profile_not_draft",
        )
    now = datetime.now(UTC)
    current_active = await get_active_profile(db, row.knowledge_set_id)
    if current_active is not None and current_active.id != row.id:
        current_active.status = ProfileStatus.archived.value
    row.status = ProfileStatus.active.value
    row.activated_at = now
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.profile_publish.value,
        resource_type="retrieval_profile",
        resource_id=row.id,
        details={
            "knowledge_set_id": row.knowledge_set_id,
            "version": row.version,
            "archived_profile_id": current_active.id if current_active else None,
        },
    )
    await db.commit()
    await db.refresh(row)
    return row


async def rollback(
    db: AsyncSession,
    member: KnowledgePrincipal,
    profile_id: str,
    *,
    publish_after: bool = False,
) -> RetrievalProfile:
    source = await _get_profile_or_404(db, profile_id)
    await _require_set_manage(db, member, source.knowledge_set_id)
    if source.status == ProfileStatus.draft.value:
        raise BadRequestError(
            message="草稿配置不可回滚",
            message_key="errors.knowledge.profile_rollback_invalid",
        )
    max_version = await db.scalar(
        select(func.coalesce(func.max(RetrievalProfile.version), 0)).where(
            RetrievalProfile.knowledge_set_id == source.knowledge_set_id,
            not_deleted(RetrievalProfile),
        )
    )
    draft = RetrievalProfile(
        knowledge_set_id=source.knowledge_set_id,
        version=int(max_version or 0) + 1,
        config=merge_profile_config(source.config),
        status=ProfileStatus.draft.value,
        created_by_member_id=member.member_id,
    )
    db.add(draft)
    await db.flush()
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.profile_rollback.value,
        resource_type="retrieval_profile",
        resource_id=draft.id,
        details={
            "knowledge_set_id": source.knowledge_set_id,
            "source_profile_id": source.id,
            "source_version": source.version,
            "new_version": draft.version,
            "publish": publish_after,
        },
    )
    if publish_after:
        now = datetime.now(UTC)
        current_active = await get_active_profile(db, draft.knowledge_set_id)
        if current_active is not None:
            current_active.status = ProfileStatus.archived.value
        draft.status = ProfileStatus.active.value
        draft.activated_at = now
        await write_audit(
            db,
            org_id=member.org_id,
            member_id=member.member_id,
            action=AuditAction.profile_publish.value,
            resource_type="retrieval_profile",
            resource_id=draft.id,
            details={
                "knowledge_set_id": draft.knowledge_set_id,
                "version": draft.version,
                "archived_profile_id": current_active.id if current_active else None,
            },
        )
    await db.commit()
    await db.refresh(draft)
    return draft


async def seed_active_profile(
    db: AsyncSession,
    *,
    knowledge_set_id: str,
    created_by_member_id: str,
    config: dict[str, Any] | None = None,
) -> RetrievalProfile:
    row = RetrievalProfile(
        knowledge_set_id=knowledge_set_id,
        version=1,
        config=merge_profile_config(config),
        status=ProfileStatus.active.value,
        created_by_member_id=created_by_member_id,
        activated_at=datetime.now(UTC),
    )
    db.add(row)
    return row
