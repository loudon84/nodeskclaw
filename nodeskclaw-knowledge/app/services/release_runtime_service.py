"""Release runtime resolution — application_id + channel → execution context."""

# @lat: [[knowledge#Product Delivery V24]]
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.application_retrieval_policy_revision import ApplicationRetrievalPolicyRevision
from app.models.base import not_deleted
from app.models.enums import ApplicationReleaseStatus
from app.models.knowledge_application_release import (
    KnowledgeApplicationRelease,
    KnowledgeReleaseChannel,
)
from app.schemas.principal import KnowledgePrincipal
from app.services import (
    application_retrieval_policy_service,
    release_integrity_service,
    release_manifest_service,
)


@dataclass
class ReleaseExecutionContext:
    release_id: str
    channel: str
    application_id: str
    manifest: dict[str, Any] = field(default_factory=dict)
    manifest_hash: str = ""
    answer_model: str | None = None
    knowledge_set_ids: list[str] = field(default_factory=list)
    knowledge_bases: list[dict[str, Any]] = field(default_factory=list)
    retrieval_policy_revision_id: str | None = None
    compiled_policy: dict[str, Any] = field(default_factory=dict)
    integrity_status: str = "healthy"


ReleaseResolveResult = ReleaseExecutionContext


def _extract_knowledge_set_ids(manifest: dict[str, Any]) -> list[str]:
    set_ids: list[str] = []
    for item in manifest.get("knowledge_sets") or []:
        if not isinstance(item, dict):
            continue
        set_id = item.get("knowledge_set_id")
        if set_id and set_id not in set_ids:
            set_ids.append(str(set_id))
    return set_ids


def _flatten_knowledge_bases(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for item in manifest.get("knowledge_sets") or []:
        if not isinstance(item, dict):
            continue
        set_id = item.get("knowledge_set_id")
        for kb_pin in item.get("knowledge_bases") or []:
            if not isinstance(kb_pin, dict):
                continue
            pin = dict(kb_pin)
            if set_id:
                pin["knowledge_set_id"] = set_id
            flattened.append(pin)
    return flattened


async def resolve_application_release(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    application_id: str,
    channel: str = "stable",
    release_id: str | None = None,
) -> ReleaseExecutionContext:
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
    if release.status != ApplicationReleaseStatus.validated.value:
        raise BadRequestError(
            message="Release 未通过校验",
            message_key="errors.knowledge.release_not_validated",
        )

    parsed = release_manifest_service.parse(release.release_manifest)
    computed_hash = release_manifest_service.manifest_hash(parsed)
    if release.manifest_hash and release.manifest_hash != computed_hash:
        raise BadRequestError(
            message="Release Manifest hash 不一致",
            message_key="errors.knowledge.release_manifest_hash_mismatch",
        )

    integrity = await release_integrity_service.evaluate(
        db,
        parsed,
        release.manifest_hash,
    )
    if integrity.status != "healthy":
        raise BadRequestError(
            message="Release Integrity 未通过",
            message_key="errors.knowledge.release_integrity_unhealthy",
            details={"status": integrity.status, "reasons": integrity.reasons},
        )

    policy_revision_id = parsed.get("retrieval_policy_revision_id")
    revision = (
        await db.get(ApplicationRetrievalPolicyRevision, policy_revision_id)
        if policy_revision_id
        else None
    )
    if (
        revision is None
        or revision.deleted_at is not None
        or revision.application_id != application_id
    ):
        raise BadRequestError(
            message="缺少 Application Retrieval Policy Revision",
            message_key="errors.knowledge.retrieval_policy_revision_required",
        )

    compiled_policy = application_retrieval_policy_service.compile_execution_policy(revision)
    manifest_hash = release.manifest_hash or computed_hash

    return ReleaseExecutionContext(
        release_id=release.id,
        channel=channel,
        application_id=application_id,
        manifest=parsed,
        manifest_hash=manifest_hash,
        answer_model=parsed.get("answer_model"),
        knowledge_set_ids=_extract_knowledge_set_ids(parsed),
        knowledge_bases=_flatten_knowledge_bases(parsed),
        retrieval_policy_revision_id=str(policy_revision_id) if policy_revision_id else None,
        compiled_policy=compiled_policy,
        integrity_status=integrity.status,
    )
