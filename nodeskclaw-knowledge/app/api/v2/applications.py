"""API v2 Applications — CRUD and knowledge-set binding."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, get_member_context
from app.core.exceptions import BadRequestError
from app.schemas.common import ApiResponse, PageData
from app.schemas.knowledge import (
    KnowledgeApplicationBindSet,
    KnowledgeApplicationCreate,
    KnowledgeApplicationOut,
    KnowledgeApplicationUpdate,
)
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_application_service

router = APIRouter(tags=["v2-applications"])


def _require_application() -> None:
    if not settings.KNOWLEDGE_API_V2_ENABLED:
        raise BadRequestError(
            message="Knowledge API v2 未启用",
            message_key="errors.knowledge.api_v2_disabled",
        )
    if not settings.KNOWLEDGE_V2_APPLICATION_ENABLED:
        raise BadRequestError(
            message="Knowledge Application 未启用",
            message_key="errors.knowledge.application_disabled",
        )


@router.get("/applications", response_model=ApiResponse[PageData[KnowledgeApplicationOut]])
async def list_applications_v2(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_application()
    items, total = await knowledge_application_service.list_applications(
        db, member, page=page, page_size=page_size
    )
    out = [
        KnowledgeApplicationOut.model_validate(
            await knowledge_application_service.application_to_out(db, app)
        )
        for app in items
    ]
    return ApiResponse(data=PageData(items=out, total=total, page=page, page_size=page_size))


@router.post("/applications", response_model=ApiResponse[KnowledgeApplicationOut])
async def create_application_v2(
    body: KnowledgeApplicationCreate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_application()
    app = await knowledge_application_service.create_application(
        db,
        member,
        name=body.name,
        description=body.description,
        answer_model=body.answer_model,
        knowledge_set_ids=body.knowledge_set_ids,
    )
    data = await knowledge_application_service.application_to_out(db, app)
    return ApiResponse(data=KnowledgeApplicationOut.model_validate(data))


@router.get("/applications/{application_id}", response_model=ApiResponse[KnowledgeApplicationOut])
async def get_application_v2(
    application_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_application()
    app = await knowledge_application_service.get_application(db, member, application_id)
    data = await knowledge_application_service.application_to_out(db, app)
    return ApiResponse(data=KnowledgeApplicationOut.model_validate(data))


@router.patch("/applications/{application_id}", response_model=ApiResponse[KnowledgeApplicationOut])
async def patch_application_v2(
    application_id: str,
    body: KnowledgeApplicationUpdate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_application()
    app = await knowledge_application_service.update_application(
        db,
        member,
        application_id,
        name=body.name,
        description=body.description,
        answer_model=body.answer_model,
        status=body.status,
    )
    data = await knowledge_application_service.application_to_out(db, app)
    return ApiResponse(data=KnowledgeApplicationOut.model_validate(data))


@router.post("/applications/{application_id}/publish", response_model=ApiResponse[KnowledgeApplicationOut])
async def publish_application_v2(
    application_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_application()
    app = await knowledge_application_service.publish_application(db, member, application_id)
    data = await knowledge_application_service.application_to_out(db, app)
    return ApiResponse(data=KnowledgeApplicationOut.model_validate(data))


@router.post("/applications/{application_id}/knowledge-sets", response_model=ApiResponse)
async def bind_application_set_v2(
    application_id: str,
    body: KnowledgeApplicationBindSet,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_application()
    item = await knowledge_application_service.bind_knowledge_set(
        db,
        member,
        application_id,
        body.knowledge_set_id,
        sort_order=body.sort_order,
    )
    return ApiResponse(
        data={"id": item.id, "knowledge_set_id": item.knowledge_set_id, "sort_order": item.sort_order}
    )


@router.delete(
    "/applications/{application_id}/knowledge-sets/{knowledge_set_id}",
    response_model=ApiResponse,
)
async def unbind_application_set_v2(
    application_id: str,
    knowledge_set_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_application()
    await knowledge_application_service.unbind_knowledge_set(
        db, member, application_id, knowledge_set_id
    )
    return ApiResponse(message="deleted")
