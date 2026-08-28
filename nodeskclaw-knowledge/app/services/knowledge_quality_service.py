"""Knowledge quality scoring — subscores and coverage without fabricated totals."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.base import not_deleted
from app.models.enums import IndexStateStatus, RuntimeBindingStatus
from app.models.knowledge_application import KnowledgeApplication
from app.models.knowledge_artifact import KnowledgeArtifact
from app.models.knowledge_base import KnowledgeBase
from app.schemas.principal import KnowledgePrincipal
from app.services import index_state_service, knowledge_application_service, knowledge_set_service, runtime_binding_service


def _score_status(subscores: dict[str, float | None]) -> str:
    values = [value for value in subscores.values() if value is not None]
    if not values:
        return "insufficient"
    if all(value >= 0.8 for value in values):
        return "complete"
    if any(value is not None for value in subscores.values()):
        return "partial"
    return "insufficient"


async def _kb_quality(db: AsyncSession, kb: KnowledgeBase) -> dict[str, Any]:
    binding = await runtime_binding_service.get_binding(db, kb.id)
    binding_score = 1.0 if binding and binding.status == RuntimeBindingStatus.active.value else 0.0
    states = await index_state_service.list_states_for_kb(db, kb.id)
    ready_states = [state for state in states if state.status == IndexStateStatus.ready.value]
    index_score = (len(ready_states) / len(states)) if states else None
    artifacts = await db.scalars(
        select(KnowledgeArtifact).where(
            KnowledgeArtifact.knowledge_base_id == kb.id,
            not_deleted(KnowledgeArtifact),
        )
    )
    artifact_rows = list(artifacts.all())
    ready_artifacts = [row for row in artifact_rows if row.status == "ready"]
    artifact_score = (len(ready_artifacts) / len(artifact_rows)) if artifact_rows else None
    subscores = {
        "runtime_binding": binding_score,
        "index_readiness": index_score,
        "artifact_readiness": artifact_score,
    }
    coverage = {
        "index_state_count": len(states),
        "ready_index_count": len(ready_states),
        "artifact_count": len(artifact_rows),
        "ready_artifact_count": len(ready_artifacts),
        "binding_status": binding.status if binding else None,
    }
    issues: list[str] = []
    if binding_score < 1.0:
        issues.append("runtime_binding_inactive")
    if index_score is not None and index_score < 1.0:
        issues.append("index_not_ready")
    if artifact_score is not None and artifact_score < 1.0:
        issues.append("artifact_not_ready")
    return {
        "knowledge_base_id": kb.id,
        "score_status": _score_status(subscores),
        "subscores": subscores,
        "data_coverage": coverage,
        "issues": issues,
        "calculated_at": datetime.now(UTC).isoformat(),
    }


async def get_kb_quality(
    db: AsyncSession,
    member: KnowledgePrincipal,
    kb_id: str,
) -> dict[str, Any]:
    if not settings.KNOWLEDGE_V23_QUALITY_ENABLED:
        return {
            "score_status": "insufficient",
            "subscores": {},
            "data_coverage": {},
            "issues": ["quality_disabled"],
            "calculated_at": datetime.now(UTC).isoformat(),
        }
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None or kb.deleted_at is not None or kb.org_id != member.org_id:
        from app.core.exceptions import NotFoundError

        raise NotFoundError(message="知识库不存在", message_key="errors.knowledge.kb_not_found")
    return await _kb_quality(db, kb)


async def get_application_quality(
    db: AsyncSession,
    member: KnowledgePrincipal,
    application_id: str,
) -> dict[str, Any]:
    if not settings.KNOWLEDGE_V23_QUALITY_ENABLED:
        return {
            "score_status": "insufficient",
            "subscores": {},
            "data_coverage": {},
            "issues": ["quality_disabled"],
            "calculated_at": datetime.now(UTC).isoformat(),
        }
    app = await knowledge_application_service.get_application(db, member, application_id)
    set_ids = await knowledge_application_service.list_bound_set_ids(db, application_id)
    kb_scores: list[dict[str, Any]] = []
    for set_id in set_ids:
        kbs = await knowledge_set_service.list_bound_knowledge_bases(db, member, set_id)
        for kb in kbs:
            kb_scores.append(await _kb_quality(db, kb))
    subscores = {
        "runtime_binding": _average([item["subscores"].get("runtime_binding") for item in kb_scores]),
        "index_readiness": _average([item["subscores"].get("index_readiness") for item in kb_scores]),
        "artifact_readiness": _average([item["subscores"].get("artifact_readiness") for item in kb_scores]),
    }
    issues = sorted({issue for item in kb_scores for issue in item.get("issues") or []})
    if app.runtime_snapshot:
        issues = list(dict.fromkeys(issues + ["runtime_snapshot_present"]))
    return {
        "application_id": application_id,
        "score_status": _score_status(subscores),
        "subscores": subscores,
        "data_coverage": {"knowledge_base_scores": kb_scores, "bound_set_count": len(set_ids)},
        "issues": issues,
        "calculated_at": datetime.now(UTC).isoformat(),
    }


def _average(values: list[float | None]) -> float | None:
    usable = [value for value in values if value is not None]
    if not usable:
        return None
    return sum(usable) / len(usable)


async def build_runtime_snapshot(
    db: AsyncSession,
    member: KnowledgePrincipal,
    application: KnowledgeApplication,
) -> dict[str, Any]:
    set_ids = await knowledge_application_service.list_bound_set_ids(db, application.id)
    kb_summaries: list[dict[str, Any]] = []
    for set_id in set_ids:
        kbs = await knowledge_set_service.list_bound_knowledge_bases(db, member, set_id)
        for kb in kbs:
            binding = await runtime_binding_service.get_binding(db, kb.id)
            states = await index_state_service.list_states_for_kb(db, kb.id)
            manifest_hash = None
            for state in states:
                if getattr(state, "input_manifest_hash", None):
                    manifest_hash = state.input_manifest_hash
                    break
            kb_summaries.append(
                {
                    "knowledge_base_id": kb.id,
                    "binding_status": binding.status if binding else None,
                    "index_states": {state.index_type: state.status for state in states},
                    "input_manifest_hash": manifest_hash,
                }
            )
    return {
        "published_at": datetime.now(UTC).isoformat(),
        "active_profile_id": application.active_profile_id,
        "bound_set_ids": set_ids,
        "acl_version": application.acl_version,
        "knowledge_bases": kb_summaries,
    }
