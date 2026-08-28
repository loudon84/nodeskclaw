"""ReleasePromotionService — sole writer of KnowledgeReleaseChannel.active_release_id."""

# @lat: [[knowledge#Knowledge Product Lifecycle V24]]
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models.base import not_deleted
from app.models.enums import (
    ApplicationPermission,
    ApplicationReleaseStatus,
    AuditAction,
    QualityGateResult,
    ReleaseChannelName,
)
from app.models.knowledge_application_release import KnowledgeApplicationRelease, KnowledgeReleaseChannel
from app.models.knowledge_quality_snapshot import KnowledgeQualitySnapshot
from app.schemas.principal import KnowledgePrincipal
from app.services.audit_service import write_audit
from app.services.knowledge_application_service import get_application, get_release, list_releases
from app.services.permission_service import has_application_permission


async def _get_channel(
    db: AsyncSession,
    application_id: str,
    channel: str,
) -> KnowledgeReleaseChannel:
    row = await db.scalar(
        select(KnowledgeReleaseChannel).where(
            KnowledgeReleaseChannel.application_id == application_id,
            KnowledgeReleaseChannel.channel == channel,
            not_deleted(KnowledgeReleaseChannel),
        )
    )
    if row is None:
        raise NotFoundError(
            message="发布通道不存在",
            message_key="errors.knowledge.release_channel_not_found",
        )
    return row


async def _assert_release_promotable(
    db: AsyncSession,
    release: KnowledgeApplicationRelease,
    *,
    channel: str,
) -> None:
    if release.status not in {
        ApplicationReleaseStatus.validated.value,
        ApplicationReleaseStatus.promoted.value,
    }:
        raise ConflictError(
            message="Release 未通过校验，无法推广",
            message_key="errors.knowledge.release_not_validated",
        )
    if channel == ReleaseChannelName.stable.value:
        if not release.quality_snapshot_id:
            raise ConflictError(
                message="缺少 Quality Snapshot，无法推广到 stable",
                message_key="errors.knowledge.release_missing_quality_snapshot",
            )
        snapshot = await db.get(KnowledgeQualitySnapshot, release.quality_snapshot_id)
        if snapshot is None or snapshot.deleted_at is not None:
            raise ConflictError(
                message="Quality Snapshot 不存在",
                message_key="errors.knowledge.quality_snapshot_not_found",
            )
        if snapshot.gate_result != QualityGateResult.pass_.value:
            raise ConflictError(
                message="Quality Gate 未通过，无法推广到 stable",
                message_key="errors.knowledge.quality_gate_failed",
                details={"gate_result": snapshot.gate_result},
            )


async def promote(
    db: AsyncSession,
    member: KnowledgePrincipal,
    application_id: str,
    *,
    channel: str,
    release_id: str,
) -> KnowledgeReleaseChannel:
    if not settings.KNOWLEDGE_V24_RELEASE_ENABLED:
        raise BadRequestError(
            message="Knowledge Release v2.4 未启用",
            message_key="errors.knowledge.release_disabled",
        )
    app = await get_application(db, member, application_id)
    if not await has_application_permission(db, member, app, ApplicationPermission.manage.value):
        raise ForbiddenError()
    release = await get_release(db, member, application_id, release_id)
    await _assert_release_promotable(db, release, channel=channel)
    channel_row = await _get_channel(db, application_id, channel)
    previous_release_id = channel_row.active_release_id
    if previous_release_id and previous_release_id != release_id:
        previous = await db.get(KnowledgeApplicationRelease, previous_release_id)
        if previous and previous.deleted_at is None and previous.status == ApplicationReleaseStatus.promoted.value:
            previous.status = ApplicationReleaseStatus.superseded.value
    release.status = ApplicationReleaseStatus.promoted.value
    release.promoted_at = datetime.now(UTC)
    channel_row.active_release_id = release_id
    channel_row.updated_by_member_id = member.member_id
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.set_update.value,
        resource_type="knowledge_release_channel",
        resource_id=channel_row.id,
        details={
            "application_id": application_id,
            "channel": channel,
            "release_id": release_id,
            "previous_release_id": previous_release_id,
            "action": "promote",
        },
    )
    await db.commit()
    await db.refresh(channel_row)
    return channel_row


async def rollback(
    db: AsyncSession,
    member: KnowledgePrincipal,
    application_id: str,
    *,
    channel: str,
) -> KnowledgeReleaseChannel:
    if not settings.KNOWLEDGE_V24_RELEASE_ENABLED:
        raise BadRequestError(
            message="Knowledge Release v2.4 未启用",
            message_key="errors.knowledge.release_disabled",
        )
    app = await get_application(db, member, application_id)
    if not await has_application_permission(db, member, app, ApplicationPermission.manage.value):
        raise ForbiddenError()
    channel_row = await _get_channel(db, application_id, channel)
    current_release_id = channel_row.active_release_id
    if not current_release_id:
        raise ConflictError(
            message="通道无活跃 Release，无法回滚",
            message_key="errors.knowledge.release_channel_empty",
        )
    releases, _ = await list_releases(db, member, application_id, page=1, page_size=200)
    validated = [
        row
        for row in releases
        if row.status
        in {
            ApplicationReleaseStatus.validated.value,
            ApplicationReleaseStatus.promoted.value,
            ApplicationReleaseStatus.superseded.value,
        }
        and row.id != current_release_id
    ]
    validated.sort(key=lambda row: row.version, reverse=True)
    if not validated:
        raise ConflictError(
            message="没有可回滚的历史 Release",
            message_key="errors.knowledge.release_rollback_unavailable",
        )
    target = validated[0]
    await _assert_release_promotable(db, target, channel=channel)
    current = await db.get(KnowledgeApplicationRelease, current_release_id)
    if current and current.deleted_at is None:
        current.status = ApplicationReleaseStatus.superseded.value
    target.status = ApplicationReleaseStatus.promoted.value
    target.promoted_at = datetime.now(UTC)
    previous_release_id = current_release_id
    channel_row.active_release_id = target.id
    channel_row.updated_by_member_id = member.member_id
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.set_update.value,
        resource_type="knowledge_release_channel",
        resource_id=channel_row.id,
        details={
            "application_id": application_id,
            "channel": channel,
            "release_id": target.id,
            "previous_release_id": previous_release_id,
            "action": "rollback",
        },
    )
    await db.commit()
    await db.refresh(channel_row)
    return channel_row


def channel_to_dict(channel: KnowledgeReleaseChannel) -> dict:
    return {
        "id": channel.id,
        "application_id": channel.application_id,
        "channel": channel.channel,
        "active_release_id": channel.active_release_id,
        "traffic_policy": channel.traffic_policy,
        "updated_by_member_id": channel.updated_by_member_id,
        "updated_at": channel.updated_at.isoformat() if channel.updated_at else None,
    }
