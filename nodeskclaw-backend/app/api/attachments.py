from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, require_org_member
from app.services.hermes_skill.permission_checker import PermissionChecker
from app.services.hermes_skill.public_attachment_service import (
    PublicAttachmentContractError,
    upload_public_attachment,
)

router = APIRouter(tags=["Attachments"])


def _canonical_attachment_error(exc: PublicAttachmentContractError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message_key": exc.message_key,
            "message": exc.message,
        },
    )


@router.post("/attachments")
# @lat: [[architecture/skill-agent#RM-18 Public Attachment Input]]
async def upload_attachment(
    file: UploadFile,
    user_org=Depends(require_org_member),
    db: AsyncSession = Depends(get_db),
):
    user, org = user_org
    await PermissionChecker.require_permission(db, user.id, org.id, "skill:invoke")
    try:
        return await upload_public_attachment(
            db,
            org_id=org.id,
            user_id=user.id,
            file=file,
        )
    except PublicAttachmentContractError as exc:
        return _canonical_attachment_error(exc)
