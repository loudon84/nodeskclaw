"""Retrieval Profile API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_member_context
from app.schemas.common import ApiResponse
from app.schemas.knowledge import (
    RetrievalProfileCreate,
    RetrievalProfileOut,
    RetrievalProfileRollback,
    RetrievalProfileUpdate,
)
from app.schemas.principal import KnowledgePrincipal
from app.services import retrieval_profile_service

set_profiles_router = APIRouter(prefix="/knowledge-sets", tags=["retrieval-profiles"])
profiles_router = APIRouter(prefix="/retrieval-profiles", tags=["retrieval-profiles"])


@set_profiles_router.get("/{set_id}/retrieval-profiles", response_model=ApiResponse[list[RetrievalProfileOut]])
async def list_profiles(
    set_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    rows = await retrieval_profile_service.list_profiles(db, member, set_id)
    return ApiResponse(data=[RetrievalProfileOut.model_validate(r) for r in rows])


@set_profiles_router.post("/{set_id}/retrieval-profiles", response_model=ApiResponse[RetrievalProfileOut])
async def create_profile(
    set_id: str,
    body: RetrievalProfileCreate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    config = body.config.model_dump() if body.config is not None else None
    row = await retrieval_profile_service.create_draft(db, member, set_id, config=config)
    return ApiResponse(data=RetrievalProfileOut.model_validate(row))


@profiles_router.get("/{profile_id}", response_model=ApiResponse[RetrievalProfileOut])
async def get_profile(
    profile_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await retrieval_profile_service.get_profile(db, member, profile_id)
    return ApiResponse(data=RetrievalProfileOut.model_validate(row))


@profiles_router.patch("/{profile_id}", response_model=ApiResponse[RetrievalProfileOut])
async def patch_profile(
    profile_id: str,
    body: RetrievalProfileUpdate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await retrieval_profile_service.update_draft(
        db,
        member,
        profile_id,
        config=body.config.model_dump(),
    )
    return ApiResponse(data=RetrievalProfileOut.model_validate(row))


@profiles_router.post("/{profile_id}/publish", response_model=ApiResponse[RetrievalProfileOut])
async def publish_profile(
    profile_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await retrieval_profile_service.publish(db, member, profile_id)
    return ApiResponse(data=RetrievalProfileOut.model_validate(row))


@profiles_router.post("/{profile_id}/rollback", response_model=ApiResponse[RetrievalProfileOut])
async def rollback_profile(
    profile_id: str,
    body: RetrievalProfileRollback | None = None,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    publish_after = body.publish if body is not None else False
    row = await retrieval_profile_service.rollback(
        db,
        member,
        profile_id,
        publish_after=publish_after,
    )
    return ApiResponse(data=RetrievalProfileOut.model_validate(row))
