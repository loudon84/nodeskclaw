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
    ApplicationStatus,
    AuditAction,
    QualityGateResult,
    ReleaseChannelName,
)
from app.models.knowledge_application_release import (
    KnowledgeApplicationRelease,
    KnowledgeReleaseChannel,
    KnowledgeReleaseChannelEvent,
)
from app.models.knowledge_quality_snapshot import KnowledgeQualitySnapshot
from app.schemas.principal import KnowledgePrincipal
from app.services.advisory_lock import application_advisory_xact_lock
from app.services.audit_service import write_audit
from app.services.knowledge_application_service import get_application, get_release
from app.services.permission_service import has_application_permission
from app.services import release_integrity_service


async def _get_channel(
    db: AsyncSession,
    application_id: str,
    channel: str,
) -> KnowledgeReleaseChannel:
    row = await db.scalar(
        select(KnowledgeReleaseChannel)
        .where(
            KnowledgeReleaseChannel.application_id == application_id,
            KnowledgeReleaseChannel.channel == channel,
            not_deleted(KnowledgeReleaseChannel),
        )
        .with_for_update()
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
    if release.status != ApplicationReleaseStatus.validated.value:
        raise ConflictError(
            message="Release 未通过校验，无法推广",
            message_key="errors.knowledge.release_not_validated",
        )

    integrity = await release_integrity_service.evaluate(
        db,
        release.release_manifest,
        release.manifest_hash,
    )

    if channel == ReleaseChannelName.stable.value:
        if integrity.status != "healthy":
            raise ConflictError(
                message="Release Integrity 未通过，无法推广到 stable",
                message_key="errors.knowledge.release_integrity_unhealthy",
                details={"status": integrity.status, "reasons": integrity.reasons},
            )
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
        if (
            snapshot.manifest_hash
            and release.manifest_hash
            and snapshot.manifest_hash != release.manifest_hash
        ):
            raise ConflictError(
                message="Quality Snapshot 与 Release manifest_hash 不一致",
                message_key="errors.knowledge.snapshot_manifest_hash_mismatch",
            )
        calculated_at = snapshot.calculated_at
        if calculated_at.tzinfo is None:
            calculated_at = calculated_at.replace(tzinfo=UTC)
        age_seconds = (datetime.now(UTC) - calculated_at).total_seconds()
        if age_seconds > settings.KNOWLEDGE_RELEASE_QUALITY_MAX_AGE_SECONDS:
            raise ConflictError(
                message="Quality Snapshot 已过期，无法推广到 stable",
                message_key="errors.knowledge.release_quality_snapshot_stale",
                details={
                    "calculated_at": calculated_at.isoformat(),
                    "max_age_seconds": settings.KNOWLEDGE_RELEASE_QUALITY_MAX_AGE_SECONDS,
                },
            )
    elif integrity.status == "unavailable":
        raise ConflictError(
            message="Release Integrity 不可用，无法推广",
            message_key="errors.knowledge.release_integrity_unavailable",
            details={"reasons": integrity.reasons},
        )


def _record_channel_event(
    db: AsyncSession,
    *,
    org_id: str,
    application_id: str,
    channel: str,
    from_release_id: str | None,
    to_release_id: str,
    action: str,
    actor_member_id: str,
) -> None:
    db.add(
        KnowledgeReleaseChannelEvent(
            org_id=org_id,
            application_id=application_id,
            channel=channel,
            from_release_id=from_release_id,
            to_release_id=to_release_id,
            action=action,
            actor_member_id=actor_member_id,
        )
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
    await application_advisory_xact_lock(db, application_id)
    channel_row = await _get_channel(db, application_id, channel)
    await _assert_release_promotable(db, release, channel=channel)
    previous_release_id = channel_row.active_release_id
    release.promoted_at = datetime.now(UTC)
    channel_row.active_release_id = release_id
    channel_row.updated_by_member_id = member.member_id
    if channel == ReleaseChannelName.stable.value:
        app.status = ApplicationStatus.active.value
    _record_channel_event(
        db,
        org_id=member.org_id,
        application_id=application_id,
        channel=channel,
        from_release_id=previous_release_id,
        to_release_id=release_id,
        action="promote",
        actor_member_id=member.member_id,
    )
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
    await application_advisory_xact_lock(db, application_id)
    channel_row = await _get_channel(db, application_id, channel)
    current_release_id = channel_row.active_release_id
    if not current_release_id:
        raise ConflictError(
            message="通道无活跃 Release，无法回滚",
            message_key="errors.knowledge.release_channel_empty",
        )
    event_rows = await db.scalars(
        select(KnowledgeReleaseChannelEvent)
        .where(
            KnowledgeReleaseChannelEvent.application_id == application_id,
            KnowledgeReleaseChannelEvent.channel == channel,
            not_deleted(KnowledgeReleaseChannelEvent),
        )
        .order_by(
            KnowledgeReleaseChannelEvent.created_at.asc(),
            KnowledgeReleaseChannelEvent.id.asc(),
        )
    )
    pointer_stack: list[str] = []
    for event in event_rows.all():
        if event.action == "promote":
            pointer_stack.append(event.to_release_id)
        elif event.action == "rollback" and pointer_stack:
            pointer_stack.pop()
    if len(pointer_stack) < 2:
        raise ConflictError(
            message="没有可回滚的历史 Release",
            message_key="errors.knowledge.release_rollback_unavailable",
        )
    target_id = pointer_stack[-2]
    target = await db.get(KnowledgeApplicationRelease, target_id)
    if target is None or target.deleted_at is not None or target.application_id != application_id:
        raise ConflictError(
            message="没有可回滚的历史 Release",
            message_key="errors.knowledge.release_rollback_unavailable",
        )
    await _assert_release_promotable(db, target, channel=channel)
    target.promoted_at = datetime.now(UTC)
    previous_release_id = current_release_id
    channel_row.active_release_id = target_id
    channel_row.updated_by_member_id = member.member_id
    _record_channel_event(
        db,
        org_id=member.org_id,
        application_id=application_id,
        channel=channel,
        from_release_id=previous_release_id,
        to_release_id=target_id,
        action="rollback",
        actor_member_id=member.member_id,
    )
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
            "release_id": target_id,
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
