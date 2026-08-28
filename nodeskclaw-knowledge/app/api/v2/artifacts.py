"""API v2 Artifact Engineering routes (PRD §52)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, get_member_context
from app.core.exceptions import BadRequestError, NotFoundError
from app.knowledge_artifacts.registry import ensure_default_providers, get_provider
from app.models.base import not_deleted
from app.models.knowledge_artifact import KnowledgeArtifact
from app.models.knowledge_base import KnowledgeBase
from app.schemas.common import ApiResponse
from app.schemas.principal import KnowledgePrincipal
from app.services import artifact_store, build_input_manifest_service, build_orchestrator, runtime_binding_service
from app.services import artifact_revision_service, artifact_security_service

router = APIRouter(tags=["v2-artifacts"])


def _require_artifacts_api() -> None:
    if not settings.KNOWLEDGE_API_V2_ENABLED:
        raise BadRequestError(
            message="Knowledge API v2 未启用",
            message_key="errors.knowledge.api_v2_disabled",
        )
    if not settings.KNOWLEDGE_V23_ARTIFACTS_ENABLED:
        raise BadRequestError(
            message="Knowledge Artifact 功能未启用",
            message_key="errors.knowledge.artifacts_disabled",
        )


def _artifact_out(row: KnowledgeArtifact) -> dict[str, Any]:
    return {
        "id": row.id,
        "knowledge_base_id": row.knowledge_base_id,
        "artifact_type": row.artifact_type,
        "provider": row.provider,
        "scope": row.scope,
        "source_file_id": row.source_file_id,
        "file_version_id": row.file_version_id,
        "status": row.status,
        "version": row.version,
        "active_revision_id": row.active_revision_id,
        "input_manifest_hash": row.input_manifest_hash,
        "last_built_at": row.last_built_at.isoformat() if row.last_built_at else None,
        "last_validated_at": row.last_validated_at.isoformat() if row.last_validated_at else None,
        "last_error": row.last_error,
    }


async def _get_kb_or_404(db: AsyncSession, member: KnowledgePrincipal, kb_id: str) -> KnowledgeBase:
    kb = await db.get(KnowledgeBase, kb_id)
    if kb is None or kb.deleted_at is not None or kb.org_id != member.org_id:
        raise NotFoundError(
            message="知识库不存在",
            message_key="errors.knowledge.kb_not_found",
        )
    return kb


@router.get("/knowledge-bases/{kb_id}/artifacts")
async def list_kb_artifacts(
    kb_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[dict[str, Any]]]:
    _require_artifacts_api()
    kb = await _get_kb_or_404(db, member, kb_id)
    plan = await artifact_security_service.authorize_kb_artifact_access(db, member, kb)
    rows = await db.scalars(
        select(KnowledgeArtifact).where(
            KnowledgeArtifact.knowledge_base_id == kb_id,
            KnowledgeArtifact.org_id == member.org_id,
            not_deleted(KnowledgeArtifact),
        )
    )
    visible: list[dict[str, Any]] = []
    for row in rows.all():
        if plan is not None:
            if not await artifact_security_service.can_read_artifact(db, member, row, kb):
                continue
        visible.append(_artifact_out(row))
    return ApiResponse(data=visible)


@router.get("/knowledge-bases/{kb_id}/artifacts/{artifact_type}")
async def get_kb_artifact_by_type(
    kb_id: str,
    artifact_type: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    _require_artifacts_api()
    kb = await _get_kb_or_404(db, member, kb_id)
    row = await db.scalar(
        select(KnowledgeArtifact).where(
            KnowledgeArtifact.knowledge_base_id == kb_id,
            KnowledgeArtifact.org_id == member.org_id,
            KnowledgeArtifact.artifact_type == artifact_type,
            not_deleted(KnowledgeArtifact),
        )
    )
    if row is None:
        raise NotFoundError(
            message="Artifact 不存在",
            message_key="errors.knowledge.artifact_not_found",
        )
    await artifact_security_service.authorize_artifact_read(db, member, row, kb)
    return ApiResponse(data=_artifact_out(row))


@router.post("/knowledge-bases/{kb_id}/artifacts/builds")
async def enqueue_artifact_build(
    kb_id: str,
    body: dict[str, Any],
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    _require_artifacts_api()
    kb = await _get_kb_or_404(db, member, kb_id)
    artifact_type = str(body.get("artifact_type") or "")
    if not artifact_type:
        raise BadRequestError(
            message="artifact_type 必填",
            message_key="errors.knowledge.artifact_type_required",
        )
    ensure_default_providers()
    provider = get_provider(artifact_type)
    if provider is None:
        raise BadRequestError(
            message="不支持的 Artifact 类型",
            message_key="errors.knowledge.artifact_type_unsupported",
        )
    if artifact_type == "outline" and not settings.KNOWLEDGE_V23_OUTLINE_ENABLED:
        raise BadRequestError(
            message="Outline Artifact 未启用",
            message_key="errors.knowledge.outline_artifact_disabled",
        )
    if artifact_type == "table" and not settings.KNOWLEDGE_V23_TABLE_ENABLED:
        raise BadRequestError(
            message="Table Artifact 未启用",
            message_key="errors.knowledge.table_artifact_disabled",
        )
    manifest_hash, _items, manifest_summary = await build_input_manifest_service.compute_manifest(db, kb)
    caps = provider.capabilities()
    source_file_id = body.get("source_file_id")
    file_version_id = body.get("file_version_id")
    row = await artifact_revision_service.get_or_create_identity(
        db,
        org_id=kb.org_id,
        knowledge_base_id=kb.id,
        artifact_type=artifact_type,
        provider=caps.provider,
        scope=caps.scope,
        source_file_id=source_file_id,
        file_version_id=file_version_id,
    )
    row.status = "building"
    row.input_manifest_hash = manifest_hash
    job_index_type = artifact_type
    if source_file_id:
        job_index_type = f"{artifact_type}:file:{source_file_id}"
    job = await build_orchestrator.enqueue_build(
        db,
        org_id=kb.org_id,
        knowledge_base_id=kb.id,
        index_type=job_index_type,
        trigger_reason="artifact_build",
        target_kind="artifact",
        target_key=artifact_type,
        input_manifest_hash=manifest_hash,
        created_by_member_id=member.member_id,
    )
    if job is not None:
        job.stage_results = {
            "input": {
                "artifact_id": row.id,
                "source_file_id": source_file_id,
                "file_version_id": file_version_id,
                "ragflow_document_id": body.get("ragflow_document_id"),
            }
        }
    await db.flush()
    return ApiResponse(
        data={
            "artifact_id": row.id,
            "artifact_type": artifact_type,
            "status": row.status,
            "build_job_id": job.id if job is not None else None,
            "input_manifest_hash": manifest_hash,
        }
    )


@router.get("/artifacts/{artifact_id}")
async def get_artifact(
    artifact_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    _require_artifacts_api()
    row = await db.get(KnowledgeArtifact, artifact_id)
    if row is None or row.deleted_at is not None or row.org_id != member.org_id:
        raise NotFoundError(
            message="Artifact 不存在",
            message_key="errors.knowledge.artifact_not_found",
        )
    kb = await _get_kb_or_404(db, member, row.knowledge_base_id)
    await artifact_security_service.authorize_artifact_read(db, member, row, kb)
    return ApiResponse(data=_artifact_out(row))


@router.get("/artifacts/{artifact_id}/content")
async def get_artifact_content(
    artifact_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[dict[str, Any]]:
    _require_artifacts_api()
    row = await db.get(KnowledgeArtifact, artifact_id)
    if row is None or row.deleted_at is not None or row.org_id != member.org_id:
        raise NotFoundError(
            message="Artifact 不存在",
            message_key="errors.knowledge.artifact_not_found",
        )
    kb = await _get_kb_or_404(db, member, row.knowledge_base_id)
    plan = await artifact_security_service.authorize_artifact_read(db, member, row, kb)
    if not row.artifact_uri:
        raise NotFoundError(
            message="Artifact 内容不存在",
            message_key="errors.knowledge.artifact_content_missing",
        )
    raw = artifact_store.read_bytes(row.artifact_uri)
    import json

    try:
        content = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        content = {"raw": raw.decode("utf-8", errors="replace")}
    if isinstance(content, dict):
        content = artifact_security_service.filter_artifact_content(
            content,
            plan,
            artifact_type=row.artifact_type,
        )
        if "nodes" in content:
            for node in content.get("nodes") or []:
                if isinstance(node, dict) and not node.get("source_refs"):
                    node["citable"] = False
    return ApiResponse(data={"artifact_type": row.artifact_type, "content": content})
