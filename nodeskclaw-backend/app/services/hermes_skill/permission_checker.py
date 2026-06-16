import logging

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError
from app.models.hermes_skill.artifact_permission import ArtifactPermission
from app.models.hermes_skill.hermes_artifact import HermesArtifact
from app.models.org_membership import OrgMembership

logger = logging.getLogger(__name__)

_ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "admin": frozenset({
        "skill:view", "skill:scan", "skill:install", "skill:uninstall",
        "skill:manage_collection", "skill:manage_registry", "skill:import",
        "skill:invoke", "skill:audit_read", "skill:manage_routing",
        "hermes_task:view", "hermes_task:create", "hermes_task:cancel", "hermes_task:retry",
        "hermes_artifact:view", "hermes_artifact:download", "hermes_artifact:batch_download",
        "hermes_artifact:delete", "hermes_artifact:share",
        "hermes_artifact:manage_permission",
        "hermes_runtime:diagnostics",
        "hermes_runtime:control",
        "hermes_runtime:metrics",
        "hermes_agent:view", "hermes_agent:manage", "hermes_agent:health_check", "hermes_agent:drain",
        "hermes_queue:view", "hermes_queue:manage", "hermes_queue:requeue",
        "skill:authorize", "skill:bulk_authorize",
    }),
    "operator": frozenset({
        "skill:view", "skill:scan", "skill:install", "skill:uninstall",
        "skill:manage_collection", "skill:manage_registry", "skill:import",
        "skill:invoke", "skill:audit_read", "skill:manage_routing",
        "hermes_task:view", "hermes_task:create", "hermes_task:cancel", "hermes_task:retry",
        "hermes_artifact:view", "hermes_artifact:download", "hermes_artifact:batch_download",
        "hermes_artifact:delete", "hermes_artifact:share",
        "hermes_artifact:manage_permission",
        "hermes_runtime:diagnostics",
        "hermes_runtime:control",
        "hermes_runtime:metrics",
        "hermes_agent:view", "hermes_agent:manage", "hermes_agent:health_check", "hermes_agent:drain",
        "hermes_queue:view", "hermes_queue:manage", "hermes_queue:requeue",
        "skill:authorize", "skill:bulk_authorize",
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

_ADMIN_OPERATOR_ROLES = {"admin", "operator"}


class PermissionChecker:
    ADMIN_OPERATOR_ROLES = _ADMIN_OPERATOR_ROLES

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
    async def get_user_role(db: AsyncSession, user_id: str, org_id: str) -> str | None:
        stmt = select(OrgMembership.role).where(
            OrgMembership.user_id == user_id,
            OrgMembership.org_id == org_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def can_view_artifact(
        db: AsyncSession, artifact: HermesArtifact, user_id: str, org_id: str,
    ) -> bool:
        if artifact.org_id != org_id:
            return False
        if not await PermissionChecker.has_permission(db, user_id, org_id, "hermes_artifact:view"):
            return False

        role = await PermissionChecker.get_user_role(db, user_id, org_id)
        if role in _ADMIN_OPERATOR_ROLES:
            return True

        scope = artifact.permission_scope
        if scope == "org":
            return True
        if scope == "workspace":
            if not artifact.workspace_id:
                return False
            return await PermissionChecker._is_workspace_member(db, user_id, org_id, artifact.workspace_id)
        if scope == "task_creator":
            return artifact.created_by == user_id
        if scope == "explicit":
            return await PermissionChecker._has_explicit_permission(db, artifact.id, user_id, org_id, "viewer")
        return False

    @staticmethod
    async def can_download_artifact(
        db: AsyncSession, artifact: HermesArtifact, user_id: str, org_id: str,
    ) -> bool:
        if not await PermissionChecker.can_view_artifact(db, artifact, user_id, org_id):
            return False
        if not await PermissionChecker.has_permission(db, user_id, org_id, "hermes_artifact:download"):
            return False

        if artifact.permission_scope == "explicit":
            return await PermissionChecker._has_explicit_permission(db, artifact.id, user_id, org_id, "downloader")
        return True

    @staticmethod
    async def can_delete_artifact(
        db: AsyncSession, artifact: HermesArtifact, user_id: str, org_id: str,
    ) -> bool:
        if not await PermissionChecker.has_permission(db, user_id, org_id, "hermes_artifact:delete"):
            return False
        role = await PermissionChecker.get_user_role(db, user_id, org_id)
        if role in _ADMIN_OPERATOR_ROLES:
            return True
        if artifact.created_by == user_id:
            return True
        return False

    @staticmethod
    async def can_manage_artifact_permission(
        db: AsyncSession, artifact: HermesArtifact, user_id: str, org_id: str,
    ) -> bool:
        if not await PermissionChecker.has_permission(db, user_id, org_id, "hermes_artifact:manage_permission"):
            return False
        role = await PermissionChecker.get_user_role(db, user_id, org_id)
        if role in _ADMIN_OPERATOR_ROLES:
            return True
        if artifact.created_by == user_id:
            return True
        return False

    @staticmethod
    async def build_scope_filter(
        db: AsyncSession, user_id: str, org_id: str,
    ):
        role = await PermissionChecker.get_user_role(db, user_id, org_id)
        if role is None:
            return HermesArtifact.id == "__never_match__"

        if role in _ADMIN_OPERATOR_ROLES:
            return HermesArtifact.org_id == org_id

        explicit_ids = await PermissionChecker.get_visible_artifact_ids(db, user_id, org_id)
        workspace_ids = await PermissionChecker._get_user_workspace_ids(db, user_id, org_id)

        conditions = [
            HermesArtifact.permission_scope == "org",
            and_(
                HermesArtifact.permission_scope == "task_creator",
                HermesArtifact.created_by == user_id,
            ),
        ]

        if workspace_ids:
            conditions.append(
                and_(
                    HermesArtifact.permission_scope == "workspace",
                    HermesArtifact.workspace_id.in_(workspace_ids),
                )
            )

        if explicit_ids:
            conditions.append(HermesArtifact.id.in_(explicit_ids))

        return or_(*conditions)

    @staticmethod
    async def _is_workspace_member(
        db: AsyncSession, user_id: str, org_id: str, workspace_id: str,
    ) -> bool:
        try:
            from app.models.workspace_member import WorkspaceMember
            from app.models.base import not_deleted
            stmt = select(WorkspaceMember).where(
                WorkspaceMember.workspace_id == workspace_id,
                WorkspaceMember.user_id == user_id,
                not_deleted(WorkspaceMember),
            )
            result = await db.execute(stmt)
            return result.scalar_one_or_none() is not None
        except Exception as exc:
            logger.warning("_is_workspace_member fallback deny: %s", exc)
            return False

    @staticmethod
    async def _get_user_workspace_ids(
        db: AsyncSession, user_id: str, org_id: str,
    ) -> set[str]:
        try:
            from app.models.workspace_member import WorkspaceMember
            from app.models.workspace import Workspace
            from app.models.base import not_deleted
            stmt = select(WorkspaceMember.workspace_id).where(
                WorkspaceMember.user_id == user_id,
                not_deleted(WorkspaceMember),
            ).join(
                Workspace,
                and_(
                    Workspace.id == WorkspaceMember.workspace_id,
                    Workspace.org_id == org_id,
                    not_deleted(Workspace),
                ),
            )
            result = await db.execute(stmt)
            return {row[0] for row in result.all()}
        except Exception as exc:
            logger.warning("_get_user_workspace_ids fallback empty: %s", exc)
            return set()

    @staticmethod
    async def _has_explicit_permission(
        db: AsyncSession, artifact_id: str, user_id: str, org_id: str, min_level: str,
    ) -> bool:
        level_order = {"viewer": 0, "downloader": 1, "editor": 2}
        min_rank = level_order.get(min_level, 0)

        stmt = select(ArtifactPermission.permission_level).where(
            ArtifactPermission.artifact_id == artifact_id,
            ArtifactPermission.user_id == user_id,
            ArtifactPermission.org_id == org_id,
            ArtifactPermission.deleted_at.is_(None),
            ArtifactPermission.revoked_at.is_(None),
        )
        result = await db.execute(stmt)
        level = result.scalar_one_or_none()
        if level is None:
            return False
        return level_order.get(level, 0) >= min_rank

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
