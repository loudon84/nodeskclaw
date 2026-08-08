"""Retrieval route."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_member_context, get_ragflow_client
from app.integrations.ragflow.client import RagflowClient
from app.schemas.common import ApiResponse
from app.schemas.knowledge import (
    PlaygroundRequest,
    PlaygroundResponse,
    RetrievalRequest,
    RetrievalResponse,
)
from app.schemas.principal import KnowledgePrincipal
from app.services import retrieval_service

router = APIRouter(tags=["retrieval"])


@router.post("/retrieval", response_model=ApiResponse[RetrievalResponse])
async def retrieve(
    body: RetrievalRequest,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowClient = Depends(get_ragflow_client),
):
    data = await retrieval_service.retrieve(
        db,
        member,
        ragflow,
        knowledge_set_id=body.knowledge_set_id,
        query=body.query,
        options=body.options,
        top_k=body.top_k or (body.options.top_k if body.options else None),
        similarity_threshold=body.similarity_threshold,
        filters=body.filters,
    )
    return ApiResponse(data=RetrievalResponse.model_validate(data))


@router.post("/retrieval/playground", response_model=ApiResponse[PlaygroundResponse])
async def retrieval_playground(
    body: PlaygroundRequest,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowClient = Depends(get_ragflow_client),
):
    data = await retrieval_service.playground_retrieve(
        db,
        member,
        ragflow,
        knowledge_set_id=body.knowledge_set_id,
        query=body.query,
        profile_id=body.profile_id,
        include_trace=body.include_trace,
        filters=body.filters,
    )
    return ApiResponse(data=PlaygroundResponse.model_validate(data))
