"""Release Integrity — compare manifest pins vs live corpus/index/artifact/model/binding."""

# @lat: [[knowledge#Knowledge Product Lifecycle V24]]
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import not_deleted
from app.models.knowledge_artifact import KnowledgeArtifact, KnowledgeArtifactRevision
from app.models.knowledge_model import KnowledgeModel
from app.models.knowledge_model_revision import KnowledgeModelRevision
from app.services import index_state_service, release_manifest_service, runtime_binding_service

IntegrityStatus = Literal["healthy", "stale", "unavailable"]


@dataclass
class ReleaseIntegrityResult:
    status: IntegrityStatus
    reasons: list[str] = field(default_factory=list)


def _resolve_status(unavailable: list[str], stale: list[str]) -> ReleaseIntegrityResult:
    if unavailable:
        return ReleaseIntegrityResult(status="unavailable", reasons=unavailable + stale)
    if stale:
        return ReleaseIntegrityResult(status="stale", reasons=stale)
    return ReleaseIntegrityResult(status="healthy", reasons=[])


async def evaluate(
    db: AsyncSession,
    manifest: dict[str, Any] | None,
    stored_hash: str | None = None,
) -> ReleaseIntegrityResult:
    parsed = release_manifest_service.parse(manifest)
    unavailable: list[str] = []
    stale: list[str] = []

    if stored_hash is not None:
        computed_hash = release_manifest_service.manifest_hash(parsed)
        if stored_hash != computed_hash:
            return ReleaseIntegrityResult(
                status="unavailable",
                reasons=["manifest_hash_mismatch"],
            )

    for knowledge_set in parsed.get("knowledge_sets") or []:
        for kb_pin in knowledge_set.get("knowledge_bases") or []:
            if not isinstance(kb_pin, dict):
                continue
            kb_id = kb_pin.get("knowledge_base_id")
            if not kb_id:
                continue
            await _evaluate_kb_pin(db, kb_id, kb_pin, unavailable, stale)

    return _resolve_status(unavailable, stale)


async def _evaluate_kb_pin(
    db: AsyncSession,
    kb_id: str,
    kb_pin: dict[str, Any],
    unavailable: list[str],
    stale: list[str],
) -> None:
    model_revision_id = kb_pin.get("knowledge_model_revision_id")
    if model_revision_id:
        revision = await db.get(KnowledgeModelRevision, model_revision_id)
        if revision is None or revision.deleted_at is not None:
            unavailable.append(f"knowledge_model_revision_missing:{kb_id}:{model_revision_id}")
        else:
            model = await db.get(KnowledgeModel, revision.knowledge_model_id)
            if (
                model is not None
                and model.deleted_at is None
                and model.active_revision_id
                and model.active_revision_id != model_revision_id
            ):
                stale.append(f"knowledge_model_revision_drift:{kb_id}")

    pinned_artifacts = kb_pin.get("artifact_revision_id")
    if isinstance(pinned_artifacts, dict) and pinned_artifacts:
        for artifact_type, revision_id in pinned_artifacts.items():
            if not revision_id:
                continue
            artifact_revision = await db.get(KnowledgeArtifactRevision, revision_id)
            if artifact_revision is None or artifact_revision.deleted_at is not None:
                unavailable.append(
                    f"artifact_revision_missing:{kb_id}:{artifact_type}:{revision_id}"
                )

        live_artifacts = await db.scalars(
            select(KnowledgeArtifact).where(
                KnowledgeArtifact.knowledge_base_id == kb_id,
                KnowledgeArtifact.status == "ready",
                not_deleted(KnowledgeArtifact),
            )
        )
        live_by_type = {
            row.artifact_type: row.active_revision_id
            for row in live_artifacts.all()
            if row.active_revision_id
        }
        for artifact_type, pinned_revision_id in pinned_artifacts.items():
            if not pinned_revision_id:
                continue
            live_revision_id = live_by_type.get(artifact_type)
            if live_revision_id is not None and live_revision_id != pinned_revision_id:
                stale.append(f"artifact_revision_drift:{kb_id}:{artifact_type}")

    states = await index_state_service.list_states_for_kb(db, kb_id)
    live_index_versions = {state.index_type: state.build_version for state in states}
    live_input_manifest_hash = next(
        (state.input_manifest_hash for state in states if state.input_manifest_hash),
        None,
    )

    pinned_index_versions = kb_pin.get("index_versions")
    if isinstance(pinned_index_versions, dict):
        for index_type, pinned_version in pinned_index_versions.items():
            live_version = live_index_versions.get(index_type)
            if live_version is not None and live_version != pinned_version:
                stale.append(f"index_version_drift:{kb_id}:{index_type}")

    pinned_input_manifest_hash = kb_pin.get("input_manifest_hash")
    if (
        pinned_input_manifest_hash
        and live_input_manifest_hash is not None
        and live_input_manifest_hash != pinned_input_manifest_hash
    ):
        stale.append(f"input_manifest_hash_drift:{kb_id}")

    binding = await runtime_binding_service.get_binding(db, kb_id)
    pinned_binding_id = kb_pin.get("runtime_binding_id")
    if pinned_binding_id and binding is not None and binding.id != pinned_binding_id:
        stale.append(f"runtime_binding_drift:{kb_id}")

    pinned_config_revision = kb_pin.get("runtime_config_revision")
    if (
        pinned_config_revision is not None
        and binding is not None
        and binding.config_revision != pinned_config_revision
    ):
        stale.append(f"runtime_config_revision_drift:{kb_id}")
