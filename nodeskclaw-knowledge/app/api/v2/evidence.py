"""API v2 Evidence — resolve persistent evidence by id."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db, get_member_context
from app.core.exceptions import BadRequestError
from app.schemas.common import ApiResponse
from app.schemas.knowledge import EvidenceResolveOut
from app.schemas.principal import KnowledgePrincipal
from app.services import citation_service

router = APIRouter(prefix="/evidence", tags=["v2-evidence"])


@router.get("/{evidence_id}", response_model=ApiResponse[EvidenceResolveOut])
async def get_evidence(
    evidence_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    if not settings.KNOWLEDGE_API_V2_ENABLED:
        raise BadRequestError(
            message="Knowledge API v2 未启用",
            message_key="errors.knowledge.api_v2_disabled",
        )
    data = await citation_service.resolve_citation(db, member, evidence_id)
    if isinstance(data, dict):
        data.pop("document_id", None)
    return ApiResponse(data=EvidenceResolveOut.model_validate(data))
