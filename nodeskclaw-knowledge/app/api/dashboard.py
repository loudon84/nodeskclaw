"""Dashboard API."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_member_context
from app.schemas.common import ApiResponse
from app.schemas.knowledge import DashboardOut, KnowledgeSetOut, SourceFileOut
from app.schemas.principal import KnowledgePrincipal
from app.services import dashboard_service

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=ApiResponse[DashboardOut])
async def get_dashboard(
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    data = await dashboard_service.get_dashboard(db, member)
    return ApiResponse(
        data=DashboardOut(
            stats=data["stats"],
            parse_status_summary=data["parse_status_summary"],
            recent_knowledge_sets=[KnowledgeSetOut.model_validate(i) for i in data["recent_knowledge_sets"]],
            recent_documents=[SourceFileOut.model_validate(i) for i in data["recent_documents"]],
        )
    )
