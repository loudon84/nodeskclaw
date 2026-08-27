"""API v2 Assets — KnowledgeBase / KnowledgeSet / Application (no Runtime resource ids)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, get_member_context, get_ragflow_client
from app.core.exceptions import BadRequestError
from app.integrations.ragflow.client import RagflowClient
from app.models.knowledge_base import KnowledgeBase
from app.schemas.common import ApiResponse, PageData
from app.schemas.knowledge import (
    KnowledgeApplicationBindSet,
    KnowledgeApplicationCreate,
    KnowledgeApplicationOut,
    KnowledgeApplicationUpdate,
    KnowledgeBaseCreate,
    KnowledgeBaseUpdate,
    KnowledgeBaseV2Out,
    KnowledgeSetBind,
    KnowledgeSetUpdate,
    KnowledgeSetV2Create,
    KnowledgeSetV2Out,
    KnowledgeSetV2Update,
)
from app.schemas.principal import KnowledgePrincipal
from app.services import (
    knowledge_application_service,
    knowledge_base_service,
    knowledge_set_service,
    retrieval_profile_service,
)

router = APIRouter(tags=["v2-assets"])


def _require_api_v2() -> None:
    if not settings.KNOWLEDGE_API_V2_ENABLED:
        raise BadRequestError(
            message="Knowledge API v2 未启用",
            message_key="errors.knowledge.api_v2_disabled",
        )


def _require_application() -> None:
    _require_api_v2()
    if not settings.KNOWLEDGE_V2_APPLICATION_ENABLED:
        raise BadRequestError(
            message="Knowledge Application 未启用",
            message_key="errors.knowledge.application_disabled",
        )


def _kb_v2_out(kb) -> KnowledgeBaseV2Out:
    return KnowledgeBaseV2Out(
        id=kb.id,
        org_id=kb.org_id,
        name=kb.name,
        description=kb.description,
        embedding_model=kb.embedding_model,
        chunk_method=kb.chunk_method,
        status=kb.status,
        owner_member_id=kb.owner_member_id,
        acl_version=kb.acl_version,
        visibility=kb.visibility,
        tags=kb.tags,
        active_build_profile_id=getattr(kb, "active_build_profile_id", None),
        knowledge_model_id=getattr(kb, "knowledge_model_id", None),
        build_version=int(getattr(kb, "build_version", 0) or 0),
    )


async def _set_v2_out(db: AsyncSession, member: KnowledgePrincipal, row) -> KnowledgeSetV2Out:
    items = await knowledge_set_service.list_set_items(db, member, row.id)
    bound: list[dict] = []
    for item in items:
        kb = await db.get(KnowledgeBase, item.knowledge_base_id)
        if kb is None or kb.deleted_at is not None:
            continue
        bound.append(
            {
                "knowledge_base_id": kb.id,
                "name": kb.name,
                "weight": float(item.weight),
            }
        )
    return KnowledgeSetV2Out(
        id=row.id,
        org_id=row.org_id,
        name=row.name,
        description=row.description,
        owner_member_id=row.owner_member_id,
        status=row.status,
        acl_version=row.acl_version,
        visibility=row.visibility,
        retrieval_config=await _active_retrieval_config(db, row),
        usage_count=row.usage_count,
        last_used_at=row.last_used_at,
        knowledge_bases=bound,
    )


async def _active_retrieval_config(db, row) -> dict | None:
    profile = await retrieval_profile_service.get_active_profile(db, row.id)
    if profile is not None:
        return retrieval_profile_service.merge_profile_config(profile.config)
    return row.retrieval_config


@router.get("/knowledge-bases", response_model=ApiResponse[PageData[KnowledgeBaseV2Out]])
async def list_knowledge_bases_v2(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    status: str | None = None,
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_api_v2()
    items, total = await knowledge_base_service.list_knowledge_bases(
        db,
        member,
        page=page,
        page_size=page_size,
        q=q,
        status=status,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ApiResponse(
        data=PageData(
            items=[_kb_v2_out(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/knowledge-bases", response_model=ApiResponse[KnowledgeBaseV2Out])
async def create_knowledge_base_v2(
    body: KnowledgeBaseCreate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowClient = Depends(get_ragflow_client),
):
    _require_api_v2()
    kb = await knowledge_base_service.create_knowledge_base(
        db,
        member,
        ragflow,
        name=body.name,
        description=body.description,
        embedding_model=body.embedding_model,
        chunk_method=body.chunk_method,
        parser_config=body.parser_config,
        visibility=body.visibility.value,
        tags=body.tags,
    )
    return ApiResponse(data=_kb_v2_out(kb))


@router.get("/knowledge-bases/{kb_id}", response_model=ApiResponse[KnowledgeBaseV2Out])
async def get_knowledge_base_v2(
    kb_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_api_v2()
    kb = await knowledge_base_service.get_knowledge_base(db, member, kb_id)
    return ApiResponse(data=_kb_v2_out(kb))


@router.patch("/knowledge-bases/{kb_id}", response_model=ApiResponse[KnowledgeBaseV2Out])
async def patch_knowledge_base_v2(
    kb_id: str,
    body: KnowledgeBaseUpdate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowClient = Depends(get_ragflow_client),
):
    _require_api_v2()
    kb = await knowledge_base_service.update_knowledge_base(
        db,
        member,
        ragflow,
        kb_id,
        name=body.name,
        description=body.description,
    )
    return ApiResponse(data=_kb_v2_out(kb))


@router.get("/knowledge-sets", response_model=ApiResponse[PageData[KnowledgeSetV2Out]])
async def list_knowledge_sets_v2(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_api_v2()
    items, total = await knowledge_set_service.list_knowledge_sets(
        db,
        member,
        page=page,
        page_size=page_size,
        q=q,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    out = [await _set_v2_out(db, member, row) for row in items]
    return ApiResponse(
        data=PageData(items=out, total=total, page=page, page_size=page_size)
    )


@router.post("/knowledge-sets", response_model=ApiResponse[KnowledgeSetV2Out])
async def create_knowledge_set_v2(
    body: KnowledgeSetV2Create,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_api_v2()
    retrieval_config = body.retrieval_config.model_dump() if body.retrieval_config else None
    row = await knowledge_set_service.create_knowledge_set(
        db,
        member,
        name=body.name,
        description=body.description,
        embedding_model="bge-m3",
        visibility=body.visibility.value,
        retrieval_config=retrieval_config,
    )
    return ApiResponse(data=await _set_v2_out(db, member, row))


@router.get("/knowledge-sets/{set_id}", response_model=ApiResponse[KnowledgeSetV2Out])
async def get_knowledge_set_v2(
    set_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_api_v2()
    row = await knowledge_set_service.get_knowledge_set(db, member, set_id)
    return ApiResponse(data=await _set_v2_out(db, member, row))


@router.patch("/knowledge-sets/{set_id}", response_model=ApiResponse[KnowledgeSetV2Out])
async def patch_knowledge_set_v2(
    set_id: str,
    body: KnowledgeSetV2Update,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_api_v2()
    row = await knowledge_set_service.update_knowledge_set(
        db,
        member,
        set_id,
        name=body.name,
        description=body.description,
        status=body.status,
        visibility=body.visibility.value if body.visibility is not None else None,
    )
    return ApiResponse(data=await _set_v2_out(db, member, row))


@router.post("/knowledge-sets/{set_id}/knowledge-bases", response_model=ApiResponse)
async def bind_knowledge_base_v2(
    set_id: str,
    body: KnowledgeSetBind,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_api_v2()
    item = await knowledge_set_service.bind_knowledge_base(
        db,
        member,
        set_id,
        body.knowledge_base_id,
        weight=body.weight,
        sort_order=body.sort_order,
    )
    return ApiResponse(data={"id": item.id, "knowledge_base_id": item.knowledge_base_id})


@router.delete("/knowledge-sets/{set_id}/knowledge-bases/{knowledge_base_id}", response_model=ApiResponse)
async def unbind_knowledge_base_v2(
    set_id: str,
    knowledge_base_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    _require_api_v2()
    await knowledge_set_service.unbind_knowledge_base(db, member, set_id, knowledge_base_id)
    return ApiResponse(message="deleted")


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
