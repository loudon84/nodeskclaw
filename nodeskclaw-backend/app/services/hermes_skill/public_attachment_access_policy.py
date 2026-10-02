from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.services.hermes_skill.permission_checker import PermissionChecker


async def require_public_attachment_upload(
    db: AsyncSession,
    user_id: str,
    org_id: str,
) -> None:
    if await PermissionChecker.has_permission(db, user_id, org_id, "skill:invoke"):
        return
    if await PermissionChecker.has_permission(db, user_id, org_id, "expert:invoke"):
        return
    raise ForbiddenError(
        "缺少权限: skill:invoke 或 expert:invoke",
        "errors.skill.permission_denied",
    )
