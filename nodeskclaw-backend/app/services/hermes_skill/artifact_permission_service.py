import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ArtifactNotFoundError,
    ArtifactScopeInvalidError,
    ArtifactAlreadyGrantedError,
    BadRequestError,
    ForbiddenError,
)
from app.models.base import not_deleted, BaseModel
from app.models.hermes_skill.hermes_artifact import HermesArtifact, PermissionScope
from app.models.hermes_skill.artifact_permission import ArtifactPermission
from app.models.org_membership import OrgMembership
from app.services.hermes_skill.artifact_audit_service import ArtifactAuditService

logger = logging.getLogger(__name__)

_VALID_SCOPES = {s.value for s in PermissionScope}
_VALID_PERMISSION_LEVELS = frozenset({"viewer", "downloader", "editor"})


class ArtifactPermissionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.audit = ArtifactAuditService(db)

    async def change_scope(
        self,
        artifact_id: str,
        org_id: str,
        new_scope: str,
        actor_id: str = "",
        actor_name: str | None = None,
    ) -> HermesArtifact:
        if new_scope not in _VALID_SCOPES:
            raise ArtifactScopeInvalidError()

        artifact = await self.db.get(HermesArtifact, artifact_id)
        if not artifact or artifact.deleted_at is not None or artifact.org_id != org_id:
            raise ArtifactNotFoundError()

        old_scope = artifact.permission_scope
        artifact.permission_scope = new_scope
        await self.db.flush()

        await self.audit.log_artifact_action(
            action="artifact.permission_changed",
            artifact_id=artifact_id,
            org_id=org_id,
            actor_id=actor_id,
            actor_name=actor_name,
            workspace_id=artifact.workspace_id,
            details={"old_scope": old_scope, "new_scope": new_scope},
        )
        return artifact

    async def grant_permission(
        self,
        artifact_id: str,
        org_id: str,
        user_id: str,
        permission_level: str = "viewer",
        granted_by: str = "",
        granted_by_name: str | None = None,
    ) -> ArtifactPermission:
        if permission_level not in _VALID_PERMISSION_LEVELS:
            raise BadRequestError(
                f"permission_level 非法: {permission_level}",
                "errors.artifact.permission_level_invalid",
            )

        artifact = await self.db.get(HermesArtifact, artifact_id)
        if not artifact or artifact.deleted_at is not None or artifact.org_id != org_id:
            raise ArtifactNotFoundError()

        membership = await self.db.execute(
            select(OrgMembership).where(
                OrgMembership.user_id == user_id,
                OrgMembership.org_id == org_id,
            )
        )
        if membership.scalar_one_or_none() is None:
            raise BadRequestError(
                "被授权用户不属于该组织",
                "errors.artifact.permission_user_not_in_org",
            )

        if artifact.created_by == user_id:
            raise ArtifactAlreadyGrantedError()

        existing = await self.db.execute(
            select(ArtifactPermission).where(
                ArtifactPermission.artifact_id == artifact_id,
                ArtifactPermission.user_id == user_id,
                ArtifactPermission.org_id == org_id,
                not_deleted(ArtifactPermission),
                ArtifactPermission.revoked_at.is_(None),
            )
        )
        if existing.scalar_one_or_none():
            raise ArtifactAlreadyGrantedError()

        record = ArtifactPermission(
            id=str(uuid.uuid4()),
            artifact_id=artifact_id,
            org_id=org_id,
            user_id=user_id,
            granted_by=granted_by,
            permission_level=permission_level,
            granted_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        await self.db.flush()

        await self.audit.log_artifact_action(
            action="artifact.permission_granted",
            artifact_id=artifact_id,
            org_id=org_id,
            actor_id=granted_by,
            actor_name=granted_by_name,
            workspace_id=artifact.workspace_id,
            details={"user_id": user_id, "permission_level": permission_level},
        )
        return record

    async def revoke_permission(
        self,
        artifact_id: str,
        org_id: str,
        user_id: str,
        revoked_by: str = "",
        revoked_by_name: str | None = None,
    ) -> None:
        stmt = select(ArtifactPermission).where(
            ArtifactPermission.artifact_id == artifact_id,
            ArtifactPermission.user_id == user_id,
            ArtifactPermission.org_id == org_id,
            not_deleted(ArtifactPermission),
            ArtifactPermission.revoked_at.is_(None),
        )
        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()
        if record:
            record.revoked_at = datetime.now(timezone.utc)
            await self.db.flush()

            await self.audit.log_artifact_action(
                action="artifact.permission_revoked",
                artifact_id=artifact_id,
                org_id=org_id,
                actor_id=revoked_by,
                actor_name=revoked_by_name,
                details={"user_id": user_id},
            )

    async def list_permissions(
        self,
        artifact_id: str,
        org_id: str,
    ) -> list[ArtifactPermission]:
        result = await self.db.execute(
            select(ArtifactPermission).where(
                ArtifactPermission.artifact_id == artifact_id,
                ArtifactPermission.org_id == org_id,
                not_deleted(ArtifactPermission),
                ArtifactPermission.revoked_at.is_(None),
            ).order_by(ArtifactPermission.granted_at)
        )
        return result.scalars().all()

    async def cascade_revoke_for_artifact(
        self,
        artifact_id: str,
    ) -> None:
        now = datetime.now(timezone.utc)
        stmt = (
            update(ArtifactPermission)
            .where(
                ArtifactPermission.artifact_id == artifact_id,
                not_deleted(ArtifactPermission),
                ArtifactPermission.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        await self.db.execute(stmt)
        await self.db.flush()
