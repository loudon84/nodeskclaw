"""Knowledge set routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_member_context
from app.schemas.common import ApiResponse
from app.schemas.knowledge import KnowledgeSetBind, KnowledgeSetCreate, KnowledgeSetOut, KnowledgeSetUpdate
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_set_service

router = APIRouter(prefix="/knowledge-sets", tags=["knowledge-sets"])


@router.get("", response_model=ApiResponse[list[KnowledgeSetOut]])
async def list_sets(
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    items = await knowledge_set_service.list_knowledge_sets(db, member)
    return ApiResponse(data=[KnowledgeSetOut.model_validate(i) for i in items])


@router.post("", response_model=ApiResponse[KnowledgeSetOut])
async def create_set(
    body: KnowledgeSetCreate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await knowledge_set_service.create_knowledge_set(
        db,
        member,
        name=body.name,
        description=body.description,
        embedding_model=body.embedding_model,
    )
    return ApiResponse(data=KnowledgeSetOut.model_validate(row))


@router.get("/{set_id}", response_model=ApiResponse[KnowledgeSetOut])
async def get_set(
    set_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await knowledge_set_service.get_knowledge_set(db, member, set_id)
    return ApiResponse(data=KnowledgeSetOut.model_validate(row))


@router.patch("/{set_id}", response_model=ApiResponse[KnowledgeSetOut])
async def patch_set(
    set_id: str,
    body: KnowledgeSetUpdate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await knowledge_set_service.update_knowledge_set(
        db, member, set_id, name=body.name, description=body.description, status=body.status
    )
    return ApiResponse(data=KnowledgeSetOut.model_validate(row))


@router.delete("/{set_id}", response_model=ApiResponse)
async def delete_set(
    set_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    await knowledge_set_service.delete_knowledge_set(db, member, set_id)
    return ApiResponse(message="deleted")


@router.post("/{set_id}/knowledge-bases", response_model=ApiResponse)
async def bind_kb(
    set_id: str,
    body: KnowledgeSetBind,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    item = await knowledge_set_service.bind_knowledge_base(
        db,
        member,
        set_id,
        body.knowledge_base_id,
        weight=body.weight,
        sort_order=body.sort_order,
    )
    return ApiResponse(data={"id": item.id, "knowledge_base_id": item.knowledge_base_id})


@router.delete("/{set_id}/knowledge-bases/{knowledge_base_id}", response_model=ApiResponse)
async def unbind_kb(
    set_id: str,
    knowledge_base_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    await knowledge_set_service.unbind_knowledge_base(db, member, set_id, knowledge_base_id)
    return ApiResponse(message="deleted")
