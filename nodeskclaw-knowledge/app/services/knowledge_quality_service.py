"""Knowledge quality scoring — subscores and coverage without fabricated totals."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.base import not_deleted
from app.models.enums import IndexStateStatus, QualityGateResult, QualitySnapshotScopeType, RuntimeBindingStatus
from app.models.knowledge_application import KnowledgeApplication
from app.models.knowledge_artifact import KnowledgeArtifact
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_quality_snapshot import KnowledgeQualityGatePolicy, KnowledgeQualitySnapshot
from app.schemas.principal import KnowledgePrincipal
from app.services import index_state_service, knowledge_application_service, knowledge_set_service, runtime_binding_service


DEFAULT_GATE_POLICY = {
    "runtime_binding_required": "ready",
    "runtime_drift_required": "in_sync",
    "min_runtime_binding_score": 1.0,
    "min_index_readiness_score": 0.8,
}


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
    binding_score = 1.0 if binding and binding.status == RuntimeBindingStatus.ready.value else 0.0
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
    payload = await _kb_quality(db, kb)
    return payload


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
    payload = await _compute_application_quality(db, member, application_id, app)
    if settings.KNOWLEDGE_V24_RELEASE_ENABLED:
        await persist_application_snapshot(
            db,
            member,
            application_id,
            manifest=None,
            quality_payload=payload,
        )
        await db.commit()
    return payload


async def _compute_application_quality(
    db: AsyncSession,
    member: KnowledgePrincipal,
    application_id: str,
    app: KnowledgeApplication,
) -> dict[str, Any]:
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


async def get_gate_policy(db: AsyncSession, org_id: str) -> dict[str, Any]:
    row = await db.scalar(
        select(KnowledgeQualityGatePolicy).where(
            KnowledgeQualityGatePolicy.org_id == org_id,
            not_deleted(KnowledgeQualityGatePolicy),
        )
    )
    if row is None:
        return dict(DEFAULT_GATE_POLICY)
    merged = dict(DEFAULT_GATE_POLICY)
    merged.update(row.policy or {})
    return merged


def evaluate_gate(
    quality_payload: dict[str, Any],
    *,
    policy: dict[str, Any] | None = None,
    binding_drift_issues: list[str] | None = None,
) -> tuple[str, dict[str, Any]]:
    gate_policy = dict(DEFAULT_GATE_POLICY)
    if policy:
        gate_policy.update(policy)
    details: dict[str, Any] = {"policy": gate_policy, "checks": []}
    subscores = quality_payload.get("subscores") or {}
    issues = list(quality_payload.get("issues") or [])
    if binding_drift_issues:
        issues.extend(binding_drift_issues)
    fail_reasons: list[str] = []
    warn_reasons: list[str] = []

    binding_score = subscores.get("runtime_binding")
    if binding_score is not None and binding_score < gate_policy.get("min_runtime_binding_score", 1.0):
        fail_reasons.append("runtime_binding_below_threshold")
    if "runtime_binding_inactive" in issues:
        fail_reasons.append("runtime_binding_inactive")

    index_score = subscores.get("index_readiness")
    if index_score is not None and index_score < gate_policy.get("min_index_readiness_score", 0.8):
        fail_reasons.append("index_readiness_below_threshold")
    if "index_not_ready" in issues:
        fail_reasons.append("index_not_ready")

    if binding_drift_issues:
        if gate_policy.get("runtime_drift_required") == "in_sync":
            fail_reasons.append("runtime_drift_not_in_sync")

    details["checks"] = {
        "fail_reasons": fail_reasons,
        "warn_reasons": warn_reasons,
        "issues": issues,
    }
    if fail_reasons:
        return QualityGateResult.fail.value, details
    if warn_reasons or quality_payload.get("score_status") == "partial":
        return QualityGateResult.warn.value, details
    return QualityGateResult.pass_.value, details


async def persist_application_snapshot(
    db: AsyncSession,
    member: KnowledgePrincipal,
    application_id: str,
    *,
    release_id: str | None = None,
    manifest: dict | None = None,
    quality_payload: dict[str, Any] | None = None,
) -> KnowledgeQualitySnapshot:
    app = await knowledge_application_service.get_application(db, member, application_id)
    payload = quality_payload or await _compute_application_quality(db, member, application_id, app)
    manifest_hash = None
    if manifest is not None:
        import hashlib
        import json

        manifest_hash = hashlib.sha256(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
    policy = await get_gate_policy(db, member.org_id)
    gate_result, gate_details = evaluate_gate(payload, policy=policy)
    snapshot = KnowledgeQualitySnapshot(
        org_id=member.org_id,
        scope_type=QualitySnapshotScopeType.application.value,
        scope_id=application_id,
        manifest_hash=manifest_hash,
        release_id=release_id,
        subscores=payload.get("subscores") or {},
        coverage=payload.get("data_coverage") or {},
        issues=payload.get("issues") or [],
        overall_status=payload.get("score_status") or "insufficient",
        gate_result=gate_result,
        gate_details=gate_details,
        calculated_at=datetime.now(UTC),
    )
    db.add(snapshot)
    await db.flush()
    return snapshot


async def persist_kb_snapshot(
    db: AsyncSession,
    member: KnowledgePrincipal,
    kb_id: str,
    *,
    quality_payload: dict[str, Any] | None = None,
) -> KnowledgeQualitySnapshot:
    if quality_payload is None:
        kb = await db.get(KnowledgeBase, kb_id)
        if kb is None or kb.deleted_at is not None or kb.org_id != member.org_id:
            from app.core.exceptions import NotFoundError

            raise NotFoundError(message="知识库不存在", message_key="errors.knowledge.kb_not_found")
        payload = await _kb_quality(db, kb)
    else:
        payload = quality_payload
    policy = await get_gate_policy(db, member.org_id)
    gate_result, gate_details = evaluate_gate(payload, policy=policy)
    snapshot = KnowledgeQualitySnapshot(
        org_id=member.org_id,
        scope_type=QualitySnapshotScopeType.knowledge_base.value,
        scope_id=kb_id,
        manifest_hash=None,
        release_id=None,
        subscores=payload.get("subscores") or {},
        coverage=payload.get("data_coverage") or {},
        issues=payload.get("issues") or [],
        overall_status=payload.get("score_status") or "insufficient",
        gate_result=gate_result,
        gate_details=gate_details,
        calculated_at=datetime.now(UTC),
    )
    db.add(snapshot)
    await db.flush()
    return snapshot


async def get_quality_history(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    scope_type: str,
    scope_id: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if scope_type == QualitySnapshotScopeType.knowledge_base.value:
        kb = await db.get(KnowledgeBase, scope_id)
        if kb is None or kb.deleted_at is not None or kb.org_id != member.org_id:
            from app.core.exceptions import NotFoundError

            raise NotFoundError(message="知识库不存在", message_key="errors.knowledge.kb_not_found")
    elif scope_type == QualitySnapshotScopeType.application.value:
        await knowledge_application_service.get_application(db, member, scope_id)
    rows = await db.scalars(
        select(KnowledgeQualitySnapshot)
        .where(
            KnowledgeQualitySnapshot.scope_type == scope_type,
            KnowledgeQualitySnapshot.scope_id == scope_id,
            not_deleted(KnowledgeQualitySnapshot),
        )
        .order_by(KnowledgeQualitySnapshot.calculated_at.desc())
        .limit(limit)
    )
    return [
        {
            "id": row.id,
            "scope_type": row.scope_type,
            "scope_id": row.scope_id,
            "manifest_hash": row.manifest_hash,
            "release_id": row.release_id,
            "subscores": row.subscores,
            "coverage": row.coverage,
            "issues": row.issues,
            "overall_status": row.overall_status,
            "gate_result": row.gate_result,
            "gate_details": row.gate_details,
            "calculated_at": row.calculated_at.isoformat() if row.calculated_at else None,
        }
        for row in rows.all()
    ]


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
