import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.base import not_deleted
from app.models.hermes_skill.skill import HermesSkill
from app.models.instance import Instance
from app.schemas.hermes_skill.common import SourceType
from app.services.hermes_skill.hub_manager import HubManager
from app.services.hermes_skill.manifest_parser import ManifestParser, ManifestParseError
from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
from app.services.hermes_skill.skill_package_manager import SkillPackageManager

logger = logging.getLogger(__name__)

_SKIP_DIRS = frozenset({
    "node_modules", ".git", "dist", "build", ".venv", "__pycache__",
    ".DS_Store", ".idea", ".vscode",
})

READ_ONLY_AGENT_SCANNED_TYPES = frozenset({
    SourceType.SYSTEM_BUILTIN, SourceType.MARKETPLACE,
    SourceType.GITHUB, SourceType.GIT, SourceType.AGENT_SCANNED,
})


@dataclass
class ScanError:
    path: str
    message: str


@dataclass
class ScanResult:
    scanned_count: int = 0
    added_count: int = 0
    updated_count: int = 0
    deleted_count: int = 0
    failed_count: int = 0
    is_partial: bool = False
    errors: list[ScanError] = field(default_factory=list)


class SkillScanner:
    def __init__(self, db: AsyncSession, hub_manager: HubManager | None = None):
        self.db = db
        self.hub_manager = hub_manager or HubManager()
        self.package_manager = SkillPackageManager()
        self.max_depth = settings.HERMES_SKILL_SCAN_MAX_DEPTH
        self.timeout = settings.HERMES_SKILL_SCAN_TIMEOUT_SECONDS

    async def scan_all(
        self, org_id: str = "", source_types: list[str] | None = None
    ) -> ScanResult:
        if not org_id:
            raise ValueError("org_id 不能为空")
        try:
            return await asyncio.wait_for(
                self._scan_all_impl(org_id, source_types=source_types),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            logger.warning("扫描超时 %ds，返回部分结果", self.timeout)
            return ScanResult(is_partial=True)

    async def _scan_all_impl(
        self, org_id: str, source_types: list[str] | None = None
    ) -> ScanResult:
        result = ScanResult()
        hub = self.hub_manager
        hub.ensure_dirs()

        default_sources = {
            SourceType.CENTRAL: (hub.hub_root / "central", SourceType.CENTRAL),
            SourceType.MARKETPLACE: (hub.hub_root / "marketplace", SourceType.MARKETPLACE),
            SourceType.LOCAL_UPLOAD: (hub.hub_root / "imported", SourceType.LOCAL_UPLOAD),
        }

        effective_sources = default_sources
        if source_types is not None:
            effective_sources = {
                k: v for k, v in default_sources.items() if k in source_types
            }

        for source_type_key, (directory, source_type) in effective_sources.items():
            if directory.is_dir():
                dir_result = await self.scan_directory(
                    directory, source_type, org_id=org_id,
                    is_read_only=source_type in READ_ONLY_AGENT_SCANNED_TYPES,
                )
                result.scanned_count += dir_result.scanned_count
                result.added_count += dir_result.added_count
                result.updated_count += dir_result.updated_count
                result.deleted_count += dir_result.deleted_count
                result.failed_count += dir_result.failed_count
                result.errors.extend(dir_result.errors)

        if source_types is None or SourceType.AGENT_SCANNED in source_types:
            agent_result = await self.scan_agent_profiles(org_id)
            result.scanned_count += agent_result.scanned_count
            result.added_count += agent_result.added_count
            result.updated_count += agent_result.updated_count
            result.deleted_count += agent_result.deleted_count
            result.failed_count += agent_result.failed_count
            result.errors.extend(agent_result.errors)

        audit_logger = SkillAuditLogger(self.db)
        await audit_logger.log(
            action="hermes.skill.scanned",
            target_id=org_id,
            org_id=org_id,
            details={
                "scanned_count": result.scanned_count,
                "added_count": result.added_count,
                "updated_count": result.updated_count,
                "deleted_count": result.deleted_count,
                "failed_count": result.failed_count,
                "is_partial": result.is_partial,
                "source_types": source_types,
            },
        )

        await self.db.commit()
        return result

    async def scan_directory(
        self,
        directory: Path,
        source_type: str = SourceType.CENTRAL,
        org_id: str = "",
        is_read_only: bool | None = None,
    ) -> ScanResult:
        result = ScanResult()
        found_skills: dict[str, dict] = {}

        for skill_dir in self._walk_skill_dirs(directory):
            result.scanned_count += 1
            try:
                manifest = ManifestParser.parse_skill_package(skill_dir)
                source_hash = self.package_manager.compute_hash(skill_dir)
                category = manifest.gateway.category or manifest.meta.agent_type or "uncategorized"
                canonical_path = str(self.hub_manager.canonical_path(source_type, category, manifest.meta.skill_id))

                found_skills[canonical_path] = {
                    "skill_id": manifest.meta.skill_id,
                    "tool_name": manifest.gateway.tool_name,
                    "name": manifest.meta.name,
                    "title": manifest.gateway.title or manifest.meta.name,
                    "description": manifest.meta.description,
                    "version": manifest.meta.version,
                    "agent_type": manifest.meta.agent_type,
                    "category": category,
                    "runtime": manifest.meta.runtime,
                    "source_type": source_type,
                    "canonical_path": canonical_path,
                    "source_hash": source_hash,
                    "is_central": source_type == SourceType.CENTRAL,
                    "is_mcp_exposed": manifest.gateway.expose_as_mcp,
                    "manifest_path": str(skill_dir / "SKILL.md"),
                    "gateway_manifest_path": str(skill_dir / "gateway.yaml") if (skill_dir / "gateway.yaml").is_file() else None,
                    "input_schema": manifest.gateway.input_schema,
                    "output_schema": manifest.gateway.output_schema,
                    "tags": manifest.meta.tags,
                    "extra_metadata": self._build_extra_metadata(manifest),
                    "scanned_at": datetime.now(timezone.utc).isoformat(),
                }
            except ManifestParseError as exc:
                result.failed_count += 1
                result.errors.append(ScanError(path=str(skill_dir), message=exc.message))
            except Exception as exc:
                result.failed_count += 1
                result.errors.append(ScanError(path=str(skill_dir), message=str(exc)))

        await self._sync_registry(
            found_skills, source_type, org_id, result,
            is_read_only=is_read_only,
        )
        return result

    def _walk_skill_dirs(self, root: Path):
        def _walk(current: Path, depth: int):
            if depth > self.max_depth:
                return
            try:
                entries = list(current.iterdir())
            except (OSError, PermissionError):
                return

            if (current / "SKILL.md").is_file():
                yield current
                return

            for entry in entries:
                if not entry.is_dir():
                    continue
                if entry.name in _SKIP_DIRS or entry.name.startswith("."):
                    continue
                yield from _walk(entry, depth + 1)

        yield from _walk(root, 0)

    async def _sync_registry(
        self,
        found_skills: dict[str, dict],
        source_type: str,
        org_id: str,
        result: ScanResult,
        is_read_only: bool | None = None,
    ) -> None:
        stmt = select(HermesSkill).where(
            HermesSkill.source_type == source_type,
            not_deleted(HermesSkill),
        )
        if org_id:
            stmt = stmt.where(HermesSkill.org_id == org_id)

        existing_result = await self.db.execute(stmt)
        existing_map: dict[str, HermesSkill] = {}
        for skill in existing_result.scalars().all():
            if skill.canonical_path:
                existing_map[skill.canonical_path] = skill

        for canonical_path, data in found_skills.items():
            existing = existing_map.pop(canonical_path, None)
            read_only = is_read_only if is_read_only is not None else (
                source_type in READ_ONLY_AGENT_SCANNED_TYPES
            )
            if existing is None:
                skill = HermesSkill(
                    org_id=org_id,
                    is_read_only=read_only,
                    is_active=True,
                    **data,
                )
                self.db.add(skill)
                result.added_count += 1
            elif existing.source_hash != data["source_hash"]:
                for key, value in data.items():
                    setattr(existing, key, value)
                result.updated_count += 1

        for existing in existing_map.values():
            existing.soft_delete()
            result.deleted_count += 1

        await self.db.flush()

    @staticmethod
    def _build_extra_metadata(manifest) -> dict | None:
        gateway = manifest.gateway
        extra: dict = {}
        if gateway.ui_schema:
            extra["ui_schema"] = gateway.ui_schema
        if gateway.examples:
            extra["examples"] = gateway.examples
        if gateway.primary_artifact_policy:
            extra["primary_artifact_policy"] = gateway.primary_artifact_policy
        return extra or None

    async def scan_agent_profiles(self, org_id: str) -> ScanResult:
        result = ScanResult()
        stmt = select(Instance).where(
            not_deleted(Instance),
            Instance.org_id == org_id,
            Instance.runtime == "hermes_agent",
        )
        instances_result = await self.db.execute(stmt)

        for instance in instances_result.scalars().all():
            profile_root_path = self._get_profile_root_path(instance)
            if not profile_root_path:
                continue
            skills_dir = Path(profile_root_path) / "skills"
            if not skills_dir.is_dir():
                continue
            try:
                dir_result = await self.scan_directory(
                    skills_dir,
                    SourceType.AGENT_SCANNED,
                    org_id=org_id,
                    is_read_only=True,
                )
                result.scanned_count += dir_result.scanned_count
                result.added_count += dir_result.added_count
                result.updated_count += dir_result.updated_count
                result.deleted_count += dir_result.deleted_count
                result.failed_count += dir_result.failed_count
                result.errors.extend(dir_result.errors)
            except Exception as exc:
                result.failed_count += 1
                result.errors.append(ScanError(path=str(skills_dir), message=str(exc)))

        return result

    @staticmethod
    def _get_profile_root_path(instance: Instance) -> str | None:
        if instance.advanced_config:
            try:
                import json
                config = json.loads(instance.advanced_config)
                return config.get("profile_root_path")
            except (json.JSONDecodeError, TypeError):
                pass
        return None
