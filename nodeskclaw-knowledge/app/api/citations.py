"""Citation resolve API."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_member_context
from app.schemas.common import ApiResponse
from app.schemas.knowledge import CitationResolveOut
from app.schemas.principal import KnowledgePrincipal
from app.services import citation_service

router = APIRouter(prefix="/citations", tags=["citations"])


@router.get("/{citation_id}", response_model=ApiResponse[CitationResolveOut])
async def get_citation(
    citation_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    data = await citation_service.resolve_citation(db, member, citation_id)
    return ApiResponse(data=CitationResolveOut.model_validate(data))
