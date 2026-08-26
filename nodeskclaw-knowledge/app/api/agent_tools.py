"""Agent HTTP tools — member Principal only; no service token on read tools."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, get_member_context, get_ragflow_client
from app.core.exceptions import BadRequestError, ForbiddenError
from app.integrations.ragflow.client import RagflowClient
from app.schemas.common import ApiResponse
from app.schemas.principal import KnowledgePrincipal
from app.services import citation_service, retrieval_service, source_file_service

router = APIRouter(prefix="/agent/tools", tags=["agent-tools"])


class SearchBody(BaseModel):
    query: str = Field(min_length=1)
    application_id: str | None = None
    knowledge_set_id: str | None = None
    top_k: int | None = None


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


@router.post("/knowledge.search")
@router.post("/knowledge.retrieve")
async def tool_search(
    body: SearchBody,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowClient = Depends(get_ragflow_client),
):
    """Member Principal required — KNOWLEDGE_SERVICE_TOKEN must not authorize this route."""
    _require_v2()
    if body.application_id:
        data = await retrieval_service.retrieve_for_application(
            db,
            member,
            ragflow,
            application_id=body.application_id,
            query=body.query,
            top_k=body.top_k,
        )
    elif body.knowledge_set_id:
        data = await retrieval_service.retrieve(
            db,
            member,
            ragflow,
            knowledge_set_id=body.knowledge_set_id,
            query=body.query,
            top_k=body.top_k,
            include_capability_plan=True,
        )
    else:
        raise BadRequestError(
            message="需要 application_id 或 knowledge_set_id",
            message_key="errors.knowledge.retrieval_target_required",
        )
    # Never expose runtime resource ids
    for chunk in data.get("chunks") or []:
        chunk.pop("document_id", None)
    for ev in data.get("evidence") or []:
        payload = ev.get("payload") or {}
        payload.pop("document_id", None)
        ev["payload"] = payload
    return ApiResponse(data=data)


@router.post("/knowledge.get_document")
async def tool_get_document(
    body: dict,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_v2()
    source_file_id = body.get("source_file_id")
    if not source_file_id:
        raise BadRequestError(
            message="缺少 source_file_id",
            message_key="errors.knowledge.source_file_id_required",
        )
    sf = await source_file_service.get_source_file(db, member, source_file_id)
    return ApiResponse(
        data={
            "source_file_id": sf.id,
            "name": sf.name,
            "status": sf.status,
            "active_version_id": sf.active_version_id,
            "knowledge_base_id": sf.knowledge_base_id,
        }
    )


@router.post("/knowledge.get_evidence")
async def tool_get_evidence(
    body: EvidenceBody,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_v2()
    # Evidence resolve reuses citation path when persistent; request-scope opaque ids are not stored
    try:
        data = await citation_service.resolve_citation(db, member, body.evidence_id)
    except Exception as exc:
        raise ForbiddenError(
            message="无权访问该证据",
            message_key="errors.knowledge.evidence_denied",
        ) from exc
    if isinstance(data, dict):
        data.pop("document_id", None)
        data.pop("ragflow_document_id", None)
    return ApiResponse(data=data)
