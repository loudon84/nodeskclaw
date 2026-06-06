import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, BadRequestError
from app.models.base import not_deleted
from app.models.hermes_skill.skill_registry_source import HermesSkillRegistry
from app.schemas.hermes_skill.common import SyncStatus
from app.services.hermes_skill.manifest_parser import ManifestParser

logger = logging.getLogger(__name__)


class RegistrySourceManager:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_source(
        self,
        org_id: str,
        name: str,
        source_type: str,
        url: str = "",
        branch: str = "main",
        auth_mode: str = "none",
        auth_secret_ref: str | None = None,
        created_by: str | None = None,
    ) -> HermesSkillRegistry:
        registry = HermesSkillRegistry(
            id=str(uuid.uuid4()),
            org_id=org_id,
            name=name,
            source_type=source_type,
            url=url,
            branch=branch,
            auth_mode=auth_mode,
            auth_secret_ref=auth_secret_ref,
            created_by=created_by,
        )
        self.db.add(registry)
        await self.db.flush()
        return registry

    async def get_source(self, registry_id: str, org_id: str) -> HermesSkillRegistry | None:
        result = await self.db.execute(
            select(HermesSkillRegistry).where(
                not_deleted(HermesSkillRegistry),
                HermesSkillRegistry.id == registry_id,
                HermesSkillRegistry.org_id == org_id,
            )
        )
        return result.scalar_one_or_none()

    async def sync(self, registry_id: str, org_id: str) -> HermesSkillRegistry:
        registry = await self.get_source(registry_id, org_id)
        if not registry:
            raise NotFoundError("Registry Source 不存在", "errors.skill.registry_not_found")
        if not registry.is_enabled:
            raise BadRequestError("Registry 已禁用", "errors.skill.registry_disabled")

        registry.last_sync_status = SyncStatus.RUNNING
        await self.db.flush()

        try:
            registry.last_synced_at = datetime.now(timezone.utc)
            registry.last_sync_status = SyncStatus.SUCCESS
            registry.last_sync_error = None
        except Exception as exc:
            registry.last_sync_status = SyncStatus.FAILED
            registry.last_sync_error = str(exc)[:1024]
            logger.error("Registry 同步失败: %s", exc)

        await self.db.flush()
        return registry

    async def delete_source(self, registry_id: str, org_id: str) -> None:
        registry = await self.get_source(registry_id, org_id)
        if not registry:
            raise NotFoundError("Registry Source 不存在", "errors.skill.registry_not_found")
        registry.soft_delete()
        await self.db.flush()
