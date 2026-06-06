import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

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
            hub_root = Path(settings.HERMES_SKILL_HUB_ROOT)
            marketplace_dir = hub_root / "marketplace" / registry_id
            marketplace_dir.mkdir(parents=True, exist_ok=True)

            if registry.source_type in ("github", "git"):
                await self._sync_git_source(registry, marketplace_dir)
            elif registry.source_type == "local":
                await self._sync_local_source(registry, marketplace_dir)
            elif registry.source_type == "internal":
                await self._sync_internal_source(registry, marketplace_dir)

            from app.services.hermes_skill.skill_scanner import SkillScanner
            scanner = SkillScanner(self.db)
            await scanner.scan_all(org_id, source_types=["marketplace"])

            registry.cache_path = str(marketplace_dir)
            registry.cache_updated_at = datetime.now(timezone.utc)
            registry.last_synced_at = datetime.now(timezone.utc)
            registry.last_sync_status = SyncStatus.SUCCESS
            registry.last_sync_error = None

            from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
            audit_logger = SkillAuditLogger(self.db)
            await audit_logger.log(
                action="hermes.skill.registry.synced",
                target_id=registry_id,
                org_id=org_id,
                details={"source_type": registry.source_type, "url": registry.url},
            )
        except Exception as exc:
            registry.last_sync_status = SyncStatus.FAILED
            registry.last_sync_error = str(exc)[:1024]
            logger.error("Registry 同步失败: %s", exc)

        await self.db.flush()
        return registry

    async def _sync_git_source(self, registry: HermesSkillRegistry, target_dir: Path) -> None:
        from app.services.hermes_skill.git_importer import GitImporter
        importer = GitImporter(self.db)
        clone_dir = await importer._clone_repo(registry.url, registry.branch or "main")

        import shutil
        if target_dir.exists():
            for item in target_dir.iterdir():
                if item.is_dir():
                    shutil.rmtree(str(item), ignore_errors=True)
                elif item.is_file():
                    item.unlink()

        for skill_dir in importer._walk_skill_dirs(clone_dir):
            try:
                shutil.copytree(str(skill_dir), str(target_dir / skill_dir.name), dirs_exist_ok=True)
            except Exception:
                pass

    async def _sync_local_source(self, registry: HermesSkillRegistry, target_dir: Path) -> None:
        import shutil
        from pathlib import Path as _Path

        source = _Path(registry.url)
        if not source.is_dir():
            raise BadRequestError("本地源目录不存在", "errors.skill.registry_local_dir_not_found")

        shutil.copytree(str(source), str(target_dir), dirs_exist_ok=True)

    async def _sync_internal_source(self, registry: HermesSkillRegistry, target_dir: Path) -> None:
        import shutil
        from pathlib import Path as _Path

        hub_root = _Path(settings.HERMES_SKILL_HUB_ROOT)
        central_dir = hub_root / "central"
        if central_dir.is_dir():
            shutil.copytree(str(central_dir), str(target_dir), dirs_exist_ok=True)

    async def delete_source(self, registry_id: str, org_id: str) -> None:
        registry = await self.get_source(registry_id, org_id)
        if not registry:
            raise NotFoundError("Registry Source 不存在", "errors.skill.registry_not_found")
        registry.soft_delete()
        await self.db.flush()
