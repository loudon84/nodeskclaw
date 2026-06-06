import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ArtifactShareDisabledError, ArtifactNotFoundError
from app.core.feature_gate import feature_gate
from app.models.base import not_deleted
from app.models.hermes_skill.hermes_artifact import HermesArtifact
from app.services.hermes_skill.download_token_service import DownloadTokenService
from app.services.hermes_skill.artifact_audit_service import ArtifactAuditService
from app.services.hermes_skill.permission_checker import PermissionChecker

logger = logging.getLogger(__name__)


class ArtifactShareService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.token_service = DownloadTokenService(db)
        self.audit = ArtifactAuditService(db)

    async def share_artifact(
        self,
        artifact_id: str,
        org_id: str,
        actor_id: str = "",
        actor_name: str | None = None,
        max_uses: int = 1,
        expires_hours: int = 24,
    ) -> dict:
        if not feature_gate.is_ee:
            raise ArtifactShareDisabledError()

        artifact = await self.db.get(HermesArtifact, artifact_id)
        if not artifact or artifact.deleted_at is not None or artifact.org_id != org_id:
            raise ArtifactNotFoundError()

        await PermissionChecker.require_permission(
            self.db, actor_id, org_id, "hermes_artifact:share"
        )

        token_record = await self.token_service.generate_token(
            artifact_id=artifact_id,
            org_id=org_id,
            created_by=actor_id,
            max_uses=max_uses,
            expires_hours=expires_hours,
        )

        await self.audit.log_artifact_action(
            action="artifact.shared",
            artifact_id=artifact_id,
            org_id=org_id,
            actor_id=actor_id,
            actor_name=actor_name,
            workspace_id=artifact.workspace_id,
            details={
                "max_uses": max_uses,
                "expires_hours": expires_hours,
                "token_id": token_record.id,
            },
        )

        share_url = f"/api/v1/hermes/artifacts/download-by-token/{token_record.token}"
        return {
            "token": token_record.token,
            "share_url": share_url,
            "expires_at": token_record.expires_at,
            "max_uses": token_record.max_uses,
        }
