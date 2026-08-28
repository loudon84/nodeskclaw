"""API v2 Retrieval — application retrieval, playground, knowledge models."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.runtime.ragflow import RagflowRuntimeAdapter
from app.core.deps import get_db, get_member_context, get_runtime_adapter
from app.core.exceptions import BadRequestError
from app.schemas.common import ApiResponse
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_model_service, retrieval_service

router = APIRouter(tags=["v2-retrieval"])


def _require_api_v2() -> None:
    if not settings.KNOWLEDGE_API_V2_ENABLED:
        raise BadRequestError(
            message="Knowledge API v2 未启用",
            message_key="errors.knowledge.api_v2_disabled",
        )


class ApplicationRetrievalRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int | None = None
    similarity_threshold: float | None = None
    filters: dict[str, list] | None = None
    profile_id: str | None = None


class PlaygroundV2Request(BaseModel):
    query: str = Field(min_length=1)
    application_id: str | None = None
    knowledge_set_id: str | None = None
    profile_id: str | None = None
    filters: dict[str, list] | None = None
    include_trace: bool = True


@router.post("/applications/{application_id}/retrieval")
async def application_retrieval(
    application_id: str,
    body: ApplicationRetrievalRequest,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowRuntimeAdapter = Depends(get_runtime_adapter),
):
    _require_api_v2()
    data = await retrieval_service.retrieve_for_application(
        db,
        member,
        ragflow,
        application_id=application_id,
        query=body.query,
        top_k=body.top_k,
        similarity_threshold=body.similarity_threshold,
        filters=body.filters,
        profile_id=body.profile_id,
    )
    return ApiResponse(data=data)


@router.post("/retrieval/playground")
async def retrieval_playground_v2(
    body: PlaygroundV2Request,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowRuntimeAdapter = Depends(get_runtime_adapter),
):
    _require_api_v2()
    if body.application_id:
        data = await retrieval_service.retrieve_for_application(
            db,
            member,
            ragflow,
            application_id=body.application_id,
            query=body.query,
            filters=body.filters,
            profile_id=body.profile_id,
        )
    elif body.knowledge_set_id:
        data = await retrieval_service.playground_retrieve(
            db,
            member,
            ragflow,
            knowledge_set_id=body.knowledge_set_id,
            query=body.query,
            profile_id=body.profile_id,
            filters=body.filters,
            include_trace=body.include_trace,
        )
    else:
        raise BadRequestError(
            message="需要 application_id 或 knowledge_set_id",
            message_key="errors.knowledge.retrieval_target_required",
        )
    return ApiResponse(data=data)


@router.post("/knowledge-models")
async def create_knowledge_model(
    body: dict,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_api_v2()
    row = await knowledge_model_service.create_model(
        db,
        member,
        name=body["name"],
        description=body.get("description"),
        entities=body.get("entities"),
        relations=body.get("relations"),
        terms=body.get("terms"),
        extraction_policy=body.get("extraction_policy"),
    )
    active = await knowledge_model_service.get_active_revision(db, row)
    return ApiResponse(data=knowledge_model_service.model_to_dict(row, revision=active))


@router.get("/knowledge-models/{model_id}")
async def get_knowledge_model(
    model_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_api_v2()
    row = await knowledge_model_service.get_model(db, member, model_id)
    active = await knowledge_model_service.get_active_revision(db, row)
    return ApiResponse(data=knowledge_model_service.model_to_dict(row, revision=active))
