"""Portal member endpoints (org reporting chain helpers)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.instance_member import DirectReportUser
from app.services import org_service

router = APIRouter()


@router.get(
    "/{member_id}/subordinate",
    response_model=ApiResponse[list[DirectReportUser]],
)
async def list_member_subordinates(
    member_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    data = await org_service.list_subordinates(member_id, db)
    return ApiResponse(data=data)
