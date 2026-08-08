"""Audit log API."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_member_context
from app.schemas.common import ApiResponse, PageData
from app.schemas.knowledge import AuditLogOut
from app.schemas.principal import KnowledgePrincipal
from app.services.audit_service import list_audits

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=ApiResponse[PageData[AuditLogOut]])
async def list_audit_logs(
    action: str | None = None,
    resource_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    rows, total = await list_audits(
        db,
        member,
        action=action,
        resource_type=resource_type,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        data=PageData(
            items=[AuditLogOut.model_validate(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
        )
    )
