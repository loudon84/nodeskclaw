"""Knowledge base routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_member_context, get_ragflow_client
from app.integrations.ragflow.client import RagflowClient
from app.schemas.common import ApiResponse
from app.schemas.knowledge import (
    AclOut,
    KbAclCreate,
    KnowledgeBaseCreate,
    KnowledgeBaseOut,
    KnowledgeBaseUpdate,
)
from app.schemas.principal import KnowledgePrincipal
from app.services import knowledge_base_service

router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


@router.get("", response_model=ApiResponse[list[KnowledgeBaseOut]])
async def list_kbs(
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    items = await knowledge_base_service.list_knowledge_bases(db, member)
    return ApiResponse(data=[KnowledgeBaseOut.model_validate(i) for i in items])


@router.post("", response_model=ApiResponse[KnowledgeBaseOut])
async def create_kb(
    body: KnowledgeBaseCreate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowClient = Depends(get_ragflow_client),
):
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
    return ApiResponse(data=KnowledgeBaseOut.model_validate(kb))


@router.get("/{kb_id}", response_model=ApiResponse[KnowledgeBaseOut])
async def get_kb(
    kb_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    kb = await knowledge_base_service.get_knowledge_base(db, member, kb_id)
    return ApiResponse(data=KnowledgeBaseOut.model_validate(kb))


@router.patch("/{kb_id}", response_model=ApiResponse[KnowledgeBaseOut])
async def patch_kb(
    kb_id: str,
    body: KnowledgeBaseUpdate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowClient = Depends(get_ragflow_client),
):
    kb = await knowledge_base_service.update_knowledge_base(
        db,
        member,
        ragflow,
        kb_id,
        name=body.name,
        description=body.description,
    )
    return ApiResponse(data=KnowledgeBaseOut.model_validate(kb))


@router.delete("/{kb_id}", response_model=ApiResponse)
async def delete_kb(
    kb_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
    ragflow: RagflowClient = Depends(get_ragflow_client),
):
    await knowledge_base_service.delete_knowledge_base(db, member, ragflow, kb_id)
    return ApiResponse(message="deleted")


@router.get("/{kb_id}/acl", response_model=ApiResponse[list[AclOut]])
async def list_acl(
    kb_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    rows = await knowledge_base_service.list_kb_acl(db, member, kb_id)
    return ApiResponse(data=[AclOut.model_validate(r) for r in rows])


@router.post("/{kb_id}/acl", response_model=ApiResponse[AclOut])
async def create_acl(
    kb_id: str,
    body: KbAclCreate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await knowledge_base_service.add_kb_acl(
        db,
        member,
        kb_id,
        subject_type=body.subject_type.value,
        subject_id=body.subject_id,
        permission=body.permission.value,
        effect=body.effect.value,
    )
    return ApiResponse(data=AclOut.model_validate(row))


@router.delete("/{kb_id}/acl/{acl_id}", response_model=ApiResponse)
async def delete_acl(
    kb_id: str,
    acl_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    await knowledge_base_service.delete_kb_acl(db, member, kb_id, acl_id)
    return ApiResponse(message="deleted")
