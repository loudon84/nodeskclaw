"""Release runtime resolution — application_id + channel → manifest."""

# @lat: [[knowledge#Product Delivery V24]]
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.base import not_deleted
from app.models.knowledge_application_release import (
    KnowledgeApplicationRelease,
    KnowledgeReleaseChannel,
)
from app.schemas.principal import KnowledgePrincipal


@dataclass
class ReleaseResolveResult:
    release_id: str
    channel: str
    manifest: dict[str, Any] = field(default_factory=dict)


async def resolve_application_release(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    application_id: str,
    channel: str = "stable",
    release_id: str | None = None,
) -> ReleaseResolveResult:
    if not settings.KNOWLEDGE_V24_RELEASE_ENABLED:
        raise BadRequestError(
            message="Release 运行时未启用",
            message_key="errors.knowledge.release_disabled",
        )

    channel_row = await db.scalar(
        select(KnowledgeReleaseChannel).where(
            KnowledgeReleaseChannel.application_id == application_id,
            KnowledgeReleaseChannel.channel == channel,
            not_deleted(KnowledgeReleaseChannel),
        )
    )
    if channel_row is None or not channel_row.active_release_id:
        raise NotFoundError(
            message="应用 Release Channel 未配置",
            message_key="errors.knowledge.release_channel_not_found",
        )

    resolved_release_id = channel_row.active_release_id
    if release_id and release_id != resolved_release_id:
        raise BadRequestError(
            message="release_id 与 channel 当前指针冲突",
            message_key="errors.knowledge.release_id_conflict",
        )
    if release_id:
        resolved_release_id = release_id

    release = await db.get(KnowledgeApplicationRelease, resolved_release_id)
    if (
        release is None
        or release.deleted_at is not None
        or release.application_id != application_id
    ):
        raise NotFoundError(
            message="Release 不存在",
            message_key="errors.knowledge.release_not_found",
        )
    if release.status not in {"validated", "promoted"}:
        raise BadRequestError(
            message="Release 未通过校验",
            message_key="errors.knowledge.release_not_validated",
        )

    manifest = dict(release.release_manifest or {})
    return ReleaseResolveResult(
        release_id=release.id,
        channel=channel,
        manifest=manifest,
    )
