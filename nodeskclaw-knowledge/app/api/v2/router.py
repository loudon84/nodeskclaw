"""API v2 router — Applications retrieval / playground (flag gated)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, get_member_context, get_ragflow_client
from app.core.exceptions import BadRequestError
from app.integrations.ragflow.client import RagflowClient
from app.schemas.common import ApiResponse
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_application_service, retrieval_service

router = APIRouter(tags=["v2"])


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
    ragflow: RagflowClient = Depends(get_ragflow_client),
):
    if not settings.KNOWLEDGE_API_V2_ENABLED:
        raise BadRequestError(
            message="Knowledge API v2 未启用",
            message_key="errors.knowledge.api_v2_disabled",
        )
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
    ragflow: RagflowClient = Depends(get_ragflow_client),
):
    if not settings.KNOWLEDGE_API_V2_ENABLED:
        raise BadRequestError(
            message="Knowledge API v2 未启用",
            message_key="errors.knowledge.api_v2_disabled",
        )
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
        data = await retrieval_service.retrieve(
            db,
            member,
            ragflow,
            knowledge_set_id=body.knowledge_set_id,
            query=body.query,
            filters=body.filters,
            profile_id=body.profile_id,
            include_capability_plan=True,
        )
    else:
        raise BadRequestError(
            message="需要 application_id 或 knowledge_set_id",
            message_key="errors.knowledge.retrieval_target_required",
        )
    return ApiResponse(data=data)


@router.post("/applications")
async def create_application(
    body: dict,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    if not settings.KNOWLEDGE_API_V2_ENABLED or not settings.KNOWLEDGE_V2_APPLICATION_ENABLED:
        raise BadRequestError(
            message="Knowledge Application 未启用",
            message_key="errors.knowledge.application_disabled",
        )
    app = await knowledge_application_service.create_application(
        db,
        member,
        name=body["name"],
        description=body.get("description"),
        answer_model=body.get("answer_model"),
        knowledge_set_ids=body.get("knowledge_set_ids"),
    )
    return ApiResponse(
        data={
            "id": app.id,
            "name": app.name,
            "status": app.status,
            "answer_model": app.answer_model,
        }
    )


@router.post("/applications/{application_id}/publish")
async def publish_application(
    application_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    if not settings.KNOWLEDGE_API_V2_ENABLED or not settings.KNOWLEDGE_V2_APPLICATION_ENABLED:
        raise BadRequestError(
            message="Knowledge Application 未启用",
            message_key="errors.knowledge.application_disabled",
        )
    app = await knowledge_application_service.publish_application(db, member, application_id)
    return ApiResponse(data={"id": app.id, "status": app.status})
