from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.models.hermes_skill.artifact_permission import ArtifactPermission
from app.models.hermes_skill.hermes_artifact import HermesArtifact
from app.models.org_membership import OrgMembership


_ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "admin": frozenset({
        "skill:view", "skill:scan", "skill:install", "skill:uninstall",
        "skill:manage_collection", "skill:manage_registry", "skill:import",
        "skill:invoke", "skill:audit_read",
        "hermes_task:view", "hermes_task:create", "hermes_task:cancel",
        "hermes_artifact:view", "hermes_artifact:download",
        "hermes_artifact:delete", "hermes_artifact:share",
        "hermes_artifact:manage_permission",
    }),
    "operator": frozenset({
        "skill:view", "skill:scan", "skill:install", "skill:uninstall",
        "skill:manage_collection", "skill:manage_registry", "skill:import",
        "skill:invoke", "skill:audit_read",
        "hermes_task:view", "hermes_task:create", "hermes_task:cancel",
        "hermes_artifact:view", "hermes_artifact:download",
        "hermes_artifact:delete", "hermes_artifact:share",
    }),
    "workspace_manager": frozenset({
        "skill:view", "skill:install", "skill:invoke",
        "hermes_task:view", "hermes_task:create",
        "hermes_artifact:view", "hermes_artifact:download",
        "hermes_artifact:share",
    }),
    "member": frozenset({
        "skill:view", "skill:invoke",
        "hermes_task:view", "hermes_task:create",
        "hermes_artifact:view", "hermes_artifact:download",
    }),
    "viewer": frozenset({
        "skill:view", "hermes_task:view", "hermes_artifact:view",
    }),
}


class PermissionChecker:
    @staticmethod
    async def has_permission(db: AsyncSession, user_id: str, org_id: str, permission: str) -> bool:
        stmt = select(OrgMembership.role).where(
            OrgMembership.user_id == user_id,
            OrgMembership.org_id == org_id,
        )
        result = await db.execute(stmt)
        role = result.scalar_one_or_none()
        if role is None:
            return False
        perms = _ROLE_PERMISSIONS.get(role, frozenset())
        return permission in perms

    @staticmethod
    async def require_permission(db: AsyncSession, user_id: str, org_id: str, permission: str) -> None:
        if not await PermissionChecker.has_permission(db, user_id, org_id, permission):
            raise ForbiddenError(
                f"缺少权限: {permission}",
                "errors.skill.permission_denied",
            )

    @staticmethod
    def filter_by_scope(
        user_id: str,
        org_id: str,
        explicit_artifact_ids: set[str] | None = None,
    ) -> list:
        conditions = [
            HermesArtifact.permission_scope == "org",
            HermesArtifact.workspace_id == HermesArtifact.workspace_id,
        ]
        conditions.append(
            or_(
                HermesArtifact.permission_scope == "workspace",
                HermesArtifact.permission_scope == "org",
            )
        )
        conditions.append(HermesArtifact.created_by == user_id)
        if explicit_artifact_ids:
            conditions.append(HermesArtifact.id.in_(explicit_artifact_ids))
        return [
            or_(
                HermesArtifact.permission_scope == "org",
                HermesArtifact.created_by == user_id,
                HermesArtifact.permission_scope == "task_creator",
                *(
                    [HermesArtifact.id.in_(explicit_artifact_ids)]
                    if explicit_artifact_ids
                    else []
                ),
            ),
        ]

    @staticmethod
    async def get_visible_artifact_ids(
        db: AsyncSession,
        user_id: str,
        org_id: str,
    ) -> set[str]:
        stmt = select(ArtifactPermission.artifact_id).where(
            ArtifactPermission.user_id == user_id,
            ArtifactPermission.org_id == org_id,
            ArtifactPermission.deleted_at.is_(None),
            ArtifactPermission.revoked_at.is_(None),
        )
        result = await db.execute(stmt)
        return {row[0] for row in result.all()}
