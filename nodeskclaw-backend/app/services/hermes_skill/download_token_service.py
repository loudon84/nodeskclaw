import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ArtifactTokenExpiredError, ArtifactNotFoundError
from app.core.feature_gate import feature_gate
from app.models.base import not_deleted
from app.models.hermes_skill.artifact_download_token import ArtifactDownloadToken

logger = logging.getLogger(__name__)


class DownloadTokenService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def generate_token(
        self,
        artifact_id: str,
        org_id: str,
        created_by: str | None = None,
        max_uses: int = 1,
        expires_hours: int = 24,
    ) -> ArtifactDownloadToken:
        if not feature_gate.is_ee:
            from app.core.exceptions import ArtifactShareDisabledError
            raise ArtifactShareDisabledError()

        if expires_hours > 24:
            expires_hours = 24

        token_str = secrets.token_urlsafe(48)
        now = datetime.now(timezone.utc)
        record = ArtifactDownloadToken(
            id=str(uuid.uuid4()),
            artifact_id=artifact_id,
            org_id=org_id,
            token=token_str,
            created_by=created_by,
            max_uses=max_uses,
            uses_remaining=max_uses,
            expires_at=now + timedelta(hours=expires_hours),
            is_active=True,
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def validate_and_consume(
        self,
        token: str,
    ) -> ArtifactDownloadToken:
        stmt = select(ArtifactDownloadToken).where(
            ArtifactDownloadToken.token == token,
            ArtifactDownloadToken.is_active.is_(True),
            not_deleted(ArtifactDownloadToken),
        ).with_for_update()

        result = await self.db.execute(stmt)
        record = result.scalar_one_or_none()

        if record is None:
            raise ArtifactTokenExpiredError()

        now = datetime.now(timezone.utc)
        if record.expires_at <= now:
            record.is_active = False
            await self.db.flush()
            raise ArtifactTokenExpiredError()

        if record.uses_remaining <= 0:
            record.is_active = False
            await self.db.flush()
            raise ArtifactTokenExpiredError()

        record.uses_remaining -= 1
        if record.uses_remaining <= 0:
            record.is_active = False
        await self.db.flush()
        return record

    async def deactivate_tokens_for_artifact(
        self,
        artifact_id: str,
    ) -> None:
        stmt = (
            update(ArtifactDownloadToken)
            .where(
                ArtifactDownloadToken.artifact_id == artifact_id,
                ArtifactDownloadToken.is_active.is_(True),
                not_deleted(ArtifactDownloadToken),
            )
            .values(is_active=False)
        )
        await self.db.execute(stmt)
        await self.db.flush()
