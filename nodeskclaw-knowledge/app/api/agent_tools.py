"""Agent HTTP tools — member Principal only; no service token on read tools."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.runtime.ragflow import RagflowRuntimeAdapter
from app.core.deps import get_db, get_member_context, get_runtime_adapter
from app.core.exceptions import BadRequestError, ForbiddenError
from app.schemas.common import ApiResponse
from app.schemas.principal import KnowledgePrincipal
from app.services import citation_service, retrieval_service, runtime_binding_service, source_file_service
from app.services import artifact_security_service
from app.services.permission_service import build_access_plan

router = APIRouter(prefix="/agent/tools", tags=["agent-tools"])


class SearchBody(BaseModel):
    query: str = Field(min_length=1)
    application_id: str | None = None
    knowledge_set_id: str | None = None
    top_k: int | None = None
    channel: str = "stable"
    release_id: str | None = None


class EvidenceBody(BaseModel):
    evidence_id: str
    application_id: str | None = None
    knowledge_set_id: str | None = None


def _require_v2() -> None:
    if not settings.KNOWLEDGE_API_V2_ENABLED:
        raise BadRequestError(
            message="Knowledge API v2 未启用",
            message_key="errors.knowledge.api_v2_disabled",
        )


def strip_runtime_document_ids(data: dict) -> None:
    for chunk in data.get("chunks") or []:
        chunk.pop("document_id", None)
    for ev in data.get("evidence") or []:
        payload = ev.get("payload") or {}
        payload.pop("document_id", None)
        ev["payload"] = payload


async def knowledge_search_or_retrieve(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowRuntimeAdapter,
    *,
    query: str,
    application_id: str | None = None,
    knowledge_set_id: str | None = None,
    top_k: int | None = None,
    channel: str = "stable",
    release_id: str | None = None,
) -> dict:
    _require_v2()
    if not application_id and not knowledge_set_id:
        raise BadRequestError(
            message="需要 application_id 或 knowledge_set_id",
            message_key="errors.knowledge.retrieval_target_required",
        )
    if application_id and knowledge_set_id:
        raise BadRequestError(
            message="application_id 与 knowledge_set_id 不能同时指定",
            message_key="errors.knowledge.retrieval_target_conflict",
        )
    if application_id:
        data = await retrieval_service.retrieve_for_application(
            db,
            member,
            ragflow,
            application_id=application_id,
            query=query,
            top_k=top_k,
            channel=channel,
            release_id=release_id,
        )
    else:
        data = await retrieval_service.retrieve(
            db,
            member,
            ragflow,
            knowledge_set_id=knowledge_set_id,
            query=query,
            top_k=top_k,
            include_capability_plan=True,
        )
    strip_runtime_document_ids(data)
    return data


async def knowledge_get_document(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    source_file_id: str,
) -> dict:
    _require_v2()
    if not source_file_id:
        raise BadRequestError(
            message="缺少 source_file_id",
            message_key="errors.knowledge.source_file_id_required",
        )
    sf = await source_file_service.get_source_file(db, member, source_file_id)
    return {
        "source_file_id": sf.id,
        "name": sf.name,
        "status": sf.status,
        "active_version_id": sf.active_version_id,
        "knowledge_base_id": sf.knowledge_base_id,
    }


async def knowledge_get_evidence(
    db: AsyncSession,
    member: KnowledgePrincipal,
    *,
    evidence_id: str,
) -> dict:
    _require_v2()
    try:
        data = await citation_service.resolve_citation(db, member, evidence_id)
    except Exception as exc:
        raise ForbiddenError(
            message="无权访问该证据",
            message_key="errors.knowledge.evidence_denied",
        ) from exc
    if isinstance(data, dict):
        data.pop("document_id", None)
        data.pop("ragflow_document_id", None)
    return data


async def _artifact_hits(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowRuntimeAdapter,
    *,
    artifact_type: str,
    knowledge_base_id: str,
    query: str,
    source_file_id: str | None = None,
) -> dict:
    from app.core.config import settings as app_settings
    from app.models.enums import AccessPlanKind
    from app.knowledge_artifacts.base import ArtifactBuildContext
    from app.knowledge_artifacts.registry import ensure_default_providers, get_provider
    from app.models.knowledge_base import KnowledgeBase
    from app.services import build_input_manifest_service

    if artifact_type == "outline" and not app_settings.KNOWLEDGE_V23_OUTLINE_ENABLED:
        raise BadRequestError(
            message="Outline Artifact 未启用",
            message_key="errors.knowledge.outline_artifact_disabled",
        )
    if artifact_type == "table" and not app_settings.KNOWLEDGE_V23_TABLE_ENABLED:
        raise BadRequestError(
            message="Table Artifact 未启用",
            message_key="errors.knowledge.table_artifact_disabled",
        )
    kb = await db.get(KnowledgeBase, knowledge_base_id)
    if kb is None or kb.deleted_at is not None or kb.org_id != member.org_id:
        raise BadRequestError(
            message="知识库不存在",
            message_key="errors.knowledge.kb_not_found",
        )
    ensure_default_providers()
    provider = get_provider(artifact_type)
    if provider is None:
        raise BadRequestError(
            message="不支持的 Artifact 类型",
            message_key="errors.knowledge.artifact_type_unsupported",
        )
    plan_access = await artifact_security_service.authorize_kb_artifact_access(db, member, kb)
    if plan_access is None:
        plan_access = await build_access_plan(db, member, [kb])
    manifest_hash, _, manifest_summary = await build_input_manifest_service.compute_manifest(db, kb)
    dataset_id = await runtime_binding_service.require_dataset_id(db, kb)
    context = ArtifactBuildContext(
        org_id=kb.org_id,
        knowledge_base_id=kb.id,
        dataset_id=dataset_id,
        adapter=ragflow,
        manifest_hash=manifest_hash,
        manifest_summary=manifest_summary,
        source_file_id=source_file_id,
    )
    hits = await provider.retrieve(query or "", context)
    allowed = set(plan_access.source_file_ids)
    filtered_hits = []
    for hit in hits:
        refs = [
            ref
            for ref in hit.source_refs
            if ref.source_file_id in allowed
        ]
        if artifact_security_service.artifact_acl_enabled():
            if plan_access.kind == AccessPlanKind.no_access:
                continue
            if plan_access.kind == AccessPlanKind.filtered_access and not refs:
                continue
        elif not (hit.citable and all(ref.source_file_id in allowed for ref in hit.source_refs)):
            continue
        filtered_hits.append(
            hit
            if refs == list(hit.source_refs)
            else type(hit)(
                artifact_type=hit.artifact_type,
                title=hit.title,
                content=hit.content,
                source_refs=refs,
                citable=bool(refs),
                provider_payload=dict(hit.provider_payload),
            )
        )
    hits = filtered_hits
    return {
        "artifact_type": artifact_type,
        "knowledge_base_id": knowledge_base_id,
        "items": [
            {
                "title": hit.title,
                "content": hit.content,
                "citable": hit.citable,
                "source_refs": [
                    {
                        "source_file_id": ref.source_file_id,
                        "file_version_id": ref.file_version_id,
                        "page_start": ref.page_start,
                        "page_end": ref.page_end,
                    }
                    for ref in hit.source_refs
                ],
                "provider_payload": hit.provider_payload,
            }
            for hit in hits
        ],
    }


async def knowledge_get_structure(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowRuntimeAdapter,
    *,
    knowledge_base_id: str,
    query: str | None = None,
    source_file_id: str | None = None,
) -> dict:
    _require_v2()
    if not knowledge_base_id:
        raise BadRequestError(
            message="缺少 knowledge_base_id",
            message_key="errors.knowledge.kb_not_found",
        )
    return await _artifact_hits(
        db,
        member,
        ragflow,
        artifact_type="outline",
        knowledge_base_id=knowledge_base_id,
        query=query or "",
        source_file_id=source_file_id,
    )


async def knowledge_get_table(
    db: AsyncSession,
    member: KnowledgePrincipal,
    ragflow: RagflowRuntimeAdapter,
    *,
    knowledge_base_id: str,
    query: str | None = None,
    source_file_id: str | None = None,
) -> dict:
    _require_v2()
    if not knowledge_base_id:
        raise BadRequestError(
            message="缺少 knowledge_base_id",
            message_key="errors.knowledge.kb_not_found",
        )
    return await _artifact_hits(
        db,
        member,
        ragflow,
        artifact_type="table",
        knowledge_base_id=knowledge_base_id,
        query=query or "",
        source_file_id=source_file_id,
    )


@router.post("/knowledge.search")
@router.post("/knowledge.retrieve")
async def tool_search(
    body: SearchBody,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowRuntimeAdapter = Depends(get_runtime_adapter),
):
    """Member Principal required — KNOWLEDGE_SERVICE_TOKEN must not authorize this route."""
    data = await knowledge_search_or_retrieve(
        db,
        member,
        ragflow,
        query=body.query,
        application_id=body.application_id,
        knowledge_set_id=body.knowledge_set_id,
        top_k=body.top_k,
        channel=body.channel,
        release_id=body.release_id,
    )
    return ApiResponse(data=data)


@router.post("/knowledge.get_document")
async def tool_get_document(
    body: dict,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    data = await knowledge_get_document(
        db,
        member,
        source_file_id=body.get("source_file_id"),
    )
    return ApiResponse(data=data)


@router.post("/knowledge.get_evidence")
async def tool_get_evidence(
    body: EvidenceBody,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    data = await knowledge_get_evidence(db, member, evidence_id=body.evidence_id)
    return ApiResponse(data=data)


@router.post("/knowledge.get_structure")
async def tool_get_structure(
    body: dict,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowRuntimeAdapter = Depends(get_runtime_adapter),
):
    data = await knowledge_get_structure(
        db,
        member,
        ragflow,
        knowledge_base_id=str(body.get("knowledge_base_id") or ""),
        query=body.get("query"),
        source_file_id=body.get("source_file_id"),
    )
    return ApiResponse(data=data)


@router.post("/knowledge.get_table")
async def tool_get_table(
    body: dict,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowRuntimeAdapter = Depends(get_runtime_adapter),
):
    data = await knowledge_get_table(
        db,
        member,
        ragflow,
        knowledge_base_id=str(body.get("knowledge_base_id") or ""),
        query=body.get("query"),
        source_file_id=body.get("source_file_id"),
    )
    return ApiResponse(data=data)
