from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.services.hermes_skill.permission_checker import PermissionChecker


class ExpertPermissionService:
    @staticmethod
    async def require(db: AsyncSession, user_id: str, org_id: str, permission: str) -> None:
        if not await PermissionChecker.has_permission(db, user_id, org_id, permission):
            raise ForbiddenError(
                message=f"缺少权限: {permission}",
                message_key="errors.expert.permission_denied",
            )

    @staticmethod
    async def has(db: AsyncSession, user_id: str, org_id: str, permission: str) -> bool:
        return await PermissionChecker.has_permission(db, user_id, org_id, permission)
