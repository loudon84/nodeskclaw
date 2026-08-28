"""Release Manifest V1 — sole schema / hash / parse owner."""

# @lat: [[knowledge#Knowledge Product Lifecycle V24]]
from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError
from app.models.base import not_deleted
from app.models.knowledge_application import KnowledgeApplication
from app.models.knowledge_artifact import KnowledgeArtifact
from app.models.knowledge_set_item import KnowledgeSetItem
from app.schemas.principal import KnowledgePrincipal

SCHEMA_VERSION = 1


def manifest_hash(manifest: dict[str, Any]) -> str:
    raw = json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def parse(manifest: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(manifest, dict):
        raise BadRequestError(
            message="Release Manifest 无效",
            message_key="errors.knowledge.release_manifest_invalid",
        )
    if "knowledge_set_ids" in manifest:
        raise BadRequestError(
            message="Release Manifest 禁止 knowledge_set_ids 平行字段",
            message_key="errors.knowledge.release_manifest_invalid",
        )
    if "knowledge_bases" in manifest and not isinstance(manifest.get("knowledge_sets"), list):
        raise BadRequestError(
            message="Release Manifest 禁止顶层 knowledge_bases 平行字段",
            message_key="errors.knowledge.release_manifest_invalid",
        )
    knowledge_sets = manifest.get("knowledge_sets")
    if not isinstance(knowledge_sets, list):
        raise BadRequestError(
            message="Release Manifest 缺少 knowledge_sets",
            message_key="errors.knowledge.release_manifest_invalid",
        )
    for item in knowledge_sets:
        if not isinstance(item, dict) or not item.get("knowledge_set_id"):
            raise BadRequestError(
                message="Release Manifest knowledge_sets 项无效",
                message_key="errors.knowledge.release_manifest_invalid",
            )
        kbs = item.get("knowledge_bases")
        if kbs is not None and not isinstance(kbs, list):
            raise BadRequestError(
                message="Release Manifest knowledge_bases 无效",
                message_key="errors.knowledge.release_manifest_invalid",
            )
    return dict(manifest)


async def build(
    db: AsyncSession,
    member: KnowledgePrincipal,
    app: KnowledgeApplication,
    *,
    release_version: int,
    retrieval_policy_revision_id: str,
) -> dict[str, Any]:
    from app.services import index_state_service, knowledge_application_service, knowledge_set_service, runtime_binding_service

    set_ids = await knowledge_application_service.list_bound_set_ids(db, app.id)
    knowledge_sets: list[dict[str, Any]] = []
    for set_id in set_ids:
        items = await db.scalars(
            select(KnowledgeSetItem).where(
                KnowledgeSetItem.knowledge_set_id == set_id,
                not_deleted(KnowledgeSetItem),
            )
        )
        set_items = list(items.all())
        weight_by_kb = {item.knowledge_base_id: float(item.weight) for item in set_items}
        kbs = await knowledge_set_service.list_bound_knowledge_bases(db, member, set_id)
        kb_payloads: list[dict[str, Any]] = []
        for kb in kbs:
            binding = await runtime_binding_service.get_binding(db, kb.id)
            states = await index_state_service.list_states_for_kb(db, kb.id)
            index_versions = {state.index_type: state.build_version for state in states}
            input_manifest_hash = next(
                (state.input_manifest_hash for state in states if state.input_manifest_hash),
                None,
            )
            artifacts = await db.scalars(
                select(KnowledgeArtifact).where(
                    KnowledgeArtifact.knowledge_base_id == kb.id,
                    KnowledgeArtifact.status == "ready",
                    not_deleted(KnowledgeArtifact),
                )
            )
            artifact_revisions = {
                row.artifact_type: row.active_revision_id
                for row in artifacts.all()
                if row.active_revision_id
            }
            model_revision_id = None
            if kb.knowledge_model_id:
                from app.models.knowledge_model import KnowledgeModel

                model = await db.get(KnowledgeModel, kb.knowledge_model_id)
                if model and model.deleted_at is None:
                    model_revision_id = model.active_revision_id
            kb_payloads.append(
                {
                    "knowledge_base_id": kb.id,
                    "weight": float(weight_by_kb.get(kb.id, 1.0)),
                    "runtime_binding_id": binding.id if binding else None,
                    "runtime_config_revision": binding.config_revision if binding else None,
                    "input_manifest_hash": input_manifest_hash,
                    "build_profile_id": kb.active_build_profile_id,
                    "knowledge_model_revision_id": model_revision_id,
                    "index_versions": index_versions,
                    "artifact_revision_id": artifact_revisions,
                }
            )
        knowledge_sets.append(
            {
                "knowledge_set_id": set_id,
                "knowledge_bases": kb_payloads,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "application_id": app.id,
        "release_version": release_version,
        "retrieval_policy_revision_id": retrieval_policy_revision_id,
        "answer_model": app.answer_model,
        "knowledge_sets": knowledge_sets,
    }
