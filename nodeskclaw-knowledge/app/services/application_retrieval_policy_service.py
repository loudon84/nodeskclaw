"""ApplicationRetrievalPolicyRevision lifecycle — list/create/publish."""

# @lat: [[knowledge-objects#Application Retrieval Policy]]
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.models.application_retrieval_policy_revision import ApplicationRetrievalPolicyRevision
from app.models.base import not_deleted
from app.models.enums import ApplicationPermission, ApplicationRetrievalPolicyStatus, AuditAction
from app.schemas.principal import KnowledgePrincipal
from app.services.audit_service import write_audit
from app.services.knowledge_application_service import get_application
from app.services.permission_service import has_application_permission


DEFAULT_POLICY_PAYLOAD = {
    "query_intelligence_policy": {"term_expansion": False},
    "provider_policy": {"allow_chunk": True, "allow_question": True},
    "provider_weights": {"chunk": 1.0, "question": 0.5},
    "candidate_budget": {"max_candidates": 1024},
    "fanout_budget": {"max_kb_fanout": 8},
    "latency_budget": {"max_ms": 30000},
    "fallback_policy": {"mode": "chunk_only"},
    "artifact_policy": {"allow_outline": True, "allow_table": True},
    "fusion_policy": {"mode": "rrf", "k": 60},
}


async def _next_revision_number(db: AsyncSession, application_id: str) -> int:
    current = await db.scalar(
        select(func.max(ApplicationRetrievalPolicyRevision.revision_number)).where(
            ApplicationRetrievalPolicyRevision.application_id == application_id,
            not_deleted(ApplicationRetrievalPolicyRevision),
        )
    )
    return int(current or 0) + 1


async def list_revisions(
    db: AsyncSession,
    member: KnowledgePrincipal,
    application_id: str,
) -> list[ApplicationRetrievalPolicyRevision]:
    _require_release_enabled()
    await get_application(db, member, application_id)
    rows = await db.scalars(
        select(ApplicationRetrievalPolicyRevision)
        .where(
            ApplicationRetrievalPolicyRevision.application_id == application_id,
            not_deleted(ApplicationRetrievalPolicyRevision),
        )
        .order_by(ApplicationRetrievalPolicyRevision.revision_number.desc())
    )
    return list(rows.all())


async def get_active_revision(
    db: AsyncSession,
    application_id: str,
) -> ApplicationRetrievalPolicyRevision | None:
    return await db.scalar(
        select(ApplicationRetrievalPolicyRevision).where(
            ApplicationRetrievalPolicyRevision.application_id == application_id,
            ApplicationRetrievalPolicyRevision.status == ApplicationRetrievalPolicyStatus.active.value,
            not_deleted(ApplicationRetrievalPolicyRevision),
        )
    )


async def create_revision(
    db: AsyncSession,
    member: KnowledgePrincipal,
    application_id: str,
    *,
    query_intelligence_policy: dict | None = None,
    provider_policy: dict | None = None,
    provider_weights: dict | None = None,
    candidate_budget: dict | None = None,
    fanout_budget: dict | None = None,
    latency_budget: dict | None = None,
    fallback_policy: dict | None = None,
    artifact_policy: dict | None = None,
    fusion_policy: dict | None = None,
    notes: str | None = None,
) -> ApplicationRetrievalPolicyRevision:
    _require_release_enabled()
    app = await get_application(db, member, application_id)
    if not await has_application_permission(db, member, app, ApplicationPermission.manage.value):
        raise ForbiddenError()
    defaults = DEFAULT_POLICY_PAYLOAD
    revision = ApplicationRetrievalPolicyRevision(
        org_id=member.org_id,
        application_id=application_id,
        revision_number=await _next_revision_number(db, application_id),
        status=ApplicationRetrievalPolicyStatus.draft.value,
        query_intelligence_policy=query_intelligence_policy or defaults["query_intelligence_policy"],
        provider_policy=provider_policy or defaults["provider_policy"],
        provider_weights=provider_weights or defaults["provider_weights"],
        candidate_budget=candidate_budget or defaults["candidate_budget"],
        fanout_budget=fanout_budget or defaults["fanout_budget"],
        latency_budget=latency_budget or defaults["latency_budget"],
        fallback_policy=fallback_policy or defaults["fallback_policy"],
        artifact_policy=artifact_policy or defaults["artifact_policy"],
        fusion_policy=fusion_policy or defaults["fusion_policy"],
        created_by_member_id=member.member_id,
        notes=notes,
    )
    db.add(revision)
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.set_create.value,
        resource_type="application_retrieval_policy_revision",
        resource_id=revision.id,
        details={"application_id": application_id, "revision_number": revision.revision_number},
    )
    await db.commit()
    await db.refresh(revision)
    return revision


async def publish_revision(
    db: AsyncSession,
    member: KnowledgePrincipal,
    application_id: str,
    revision_id: str,
) -> ApplicationRetrievalPolicyRevision:
    _require_release_enabled()
    app = await get_application(db, member, application_id)
    if not await has_application_permission(db, member, app, ApplicationPermission.manage.value):
        raise ForbiddenError()
    revision = await db.get(ApplicationRetrievalPolicyRevision, revision_id)
    if (
        revision is None
        or revision.deleted_at is not None
        or revision.application_id != application_id
        or revision.org_id != member.org_id
    ):
        raise NotFoundError(
            message="检索策略版本不存在",
            message_key="errors.knowledge.retrieval_policy_revision_not_found",
        )
    if revision.status != ApplicationRetrievalPolicyStatus.draft.value:
        raise ConflictError(
            message="仅 draft 版本可发布",
            message_key="errors.knowledge.retrieval_policy_revision_not_draft",
        )
    active_rows = await db.scalars(
        select(ApplicationRetrievalPolicyRevision).where(
            ApplicationRetrievalPolicyRevision.application_id == application_id,
            ApplicationRetrievalPolicyRevision.status == ApplicationRetrievalPolicyStatus.active.value,
            not_deleted(ApplicationRetrievalPolicyRevision),
        )
    )
    for row in active_rows.all():
        row.status = ApplicationRetrievalPolicyStatus.archived.value
    revision.status = ApplicationRetrievalPolicyStatus.active.value
    revision.published_at = datetime.now(UTC)
    await write_audit(
        db,
        org_id=member.org_id,
        member_id=member.member_id,
        action=AuditAction.set_update.value,
        resource_type="application_retrieval_policy_revision",
        resource_id=revision.id,
        details={"application_id": application_id, "action": "publish"},
    )
    await db.commit()
    await db.refresh(revision)
    return revision


def revision_to_dict(revision: ApplicationRetrievalPolicyRevision) -> dict:
    return {
        "id": revision.id,
        "application_id": revision.application_id,
        "revision_number": revision.revision_number,
        "status": revision.status,
        "query_intelligence_policy": revision.query_intelligence_policy,
        "provider_policy": revision.provider_policy,
        "provider_weights": revision.provider_weights,
        "candidate_budget": revision.candidate_budget,
        "fanout_budget": revision.fanout_budget,
        "latency_budget": revision.latency_budget,
        "fallback_policy": revision.fallback_policy,
        "artifact_policy": revision.artifact_policy,
        "fusion_policy": revision.fusion_policy,
        "created_by_member_id": revision.created_by_member_id,
        "published_at": revision.published_at.isoformat() if revision.published_at else None,
        "notes": revision.notes,
        "created_at": revision.created_at.isoformat() if revision.created_at else None,
    }


def _require_release_enabled() -> None:
    if not settings.KNOWLEDGE_V24_RELEASE_ENABLED:
        raise BadRequestError(
            message="Knowledge Release v2.4 未启用",
            message_key="errors.knowledge.release_disabled",
        )
