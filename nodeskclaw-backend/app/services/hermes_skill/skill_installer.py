import logging
import os
import shutil
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, BadRequestError
from app.models.base import not_deleted
from app.models.hermes_skill.skill import HermesSkill
from app.models.hermes_skill.skill_installation import HermesSkillInstallation
from app.schemas.hermes_skill.common import InstallMode, InstallStatus
from app.services.hermes_skill.conflict_detector import ConflictDetector
from app.services.hermes_skill.path_guard import PathGuard

logger = logging.getLogger(__name__)


class SkillInstaller:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.conflict_detector = ConflictDetector(db)

    async def install(
        self,
        skill_id: str,
        agent_id: str,
        org_id: str,
        profile_id: str | None = None,
        workspace_id: str | None = None,
        install_mode: str = InstallMode.COPY,
        conflict_strategy: str = "install_as_new_version",
        installed_by: str | None = None,
        target_agent_type: str | None = None,
        allowed_modes: list[str] | None = None,
    ) -> HermesSkillInstallation:
        skill = await self._get_active_skill(skill_id, org_id)
        if not skill:
            raise NotFoundError("Skill 不存在或未启用", "errors.skill.not_found")

        if target_agent_type and skill.agent_type and target_agent_type != skill.agent_type:
            raise BadRequestError(
                f"agent_type 不匹配: skill={skill.agent_type}, target={target_agent_type}",
                "errors.skill.agent_type_mismatch",
            )

        mode = self._auto_select_mode(skill, install_mode)

        if allowed_modes and mode not in allowed_modes:
            raise BadRequestError(
                f"install_mode={mode} 不在 allowed_modes={allowed_modes} 中",
                "errors.skill.install_mode_not_allowed",
            )

        target_path = await self._build_target_path(skill, agent_id, profile_id, mode)

        hub_root = Path(settings.HERMES_SKILL_HUB_ROOT)
        PathGuard.validate_within_root(target_path, hub_root)
        PathGuard.reject_system_dirs(target_path)

        report = await self.conflict_detector.detect(
            skill_id=skill.skill_id,
            agent_id=agent_id,
            target_path=str(target_path),
            new_version=skill.version,
            new_source_type=skill.source_type,
            is_read_only=skill.is_read_only,
            skill_agent_type=skill.agent_type or "",
            target_agent_type="",
        )

        from app.schemas.hermes_skill.common import ConflictStrategy
        strategy = ConflictStrategy(conflict_strategy)
        resolved = await self.conflict_detector.resolve(report, strategy)

        if resolved == ConflictStrategy.ABORT:
            raise BadRequestError("安装冲突，策略为 abort", "errors.skill.install_conflict_abort")
        if resolved == ConflictStrategy.SKIP:
            raise BadRequestError("安装冲突，策略为 skip", "errors.skill.install_conflict_skip")

        installation = HermesSkillInstallation(
            id=str(uuid.uuid4()),
            org_id=org_id,
            skill_id=skill.skill_id,
            agent_id=agent_id,
            profile_id=profile_id,
            workspace_id=workspace_id,
            install_mode=mode,
            installed_version=skill.version,
            source_path=skill.canonical_path,
            status=InstallStatus.PENDING,
            installed_by=installed_by,
        )
        self.db.add(installation)
        await self.db.flush()

        try:
            await self._execute_file_operation(installation, skill, target_path, mode)
            installation.status = InstallStatus.INSTALLED
            installation.installed_path = str(target_path)

            profile_root_path = await self._get_profile_root_path(agent_id)
            if profile_root_path:
                installation.profile_root_path = profile_root_path

            from app.services.hermes_skill.skill_scanner import SkillScanner
            from app.services.hermes_skill.skill_audit_logger import SkillAuditLogger
            scanner = SkillScanner(self.db)
            await scanner.scan_agent_profiles(org_id, agent_ids=[agent_id])

            audit_logger = SkillAuditLogger(self.db)
            await audit_logger.log(
                action="hermes.skill.installed",
                target_id=skill.id,
                org_id=org_id,
                actor_id=installed_by or "",
                details={"skill_id": skill.skill_id, "agent_id": agent_id, "install_mode": mode},
            )
        except Exception as exc:
            installation.status = InstallStatus.FAILED
            installation.error_message = str(exc)
            logger.error("Skill 安装文件操作失败: %s", exc)

        await self.db.flush()
        return installation

    async def uninstall(
        self,
        installation_id: str,
        org_id: str,
    ) -> HermesSkillInstallation:
        installation = await self.db.get(HermesSkillInstallation, installation_id)
        if not installation or installation.deleted_at is not None or installation.org_id != org_id:
            raise NotFoundError("安装记录不存在", "errors.skill.installation_not_found")
        if installation.status != InstallStatus.INSTALLED:
            raise BadRequestError("只能卸载已安装的 Skill", "errors.skill.cannot_uninstall")

        try:
            await self._execute_file_cleanup(installation)
        except Exception as exc:
            logger.warning("卸载文件清理失败: %s", exc)

        installation.status = InstallStatus.REMOVED
        await self.db.flush()
        return installation

    async def sync_installation(
        self,
        installation_id: str,
        org_id: str,
    ) -> HermesSkillInstallation:
        installation = await self.db.get(HermesSkillInstallation, installation_id)
        if not installation or installation.deleted_at is not None or installation.org_id != org_id:
            raise NotFoundError("安装记录不存在", "errors.skill.installation_not_found")

        if installation.install_mode == InstallMode.SYMLINK and installation.symlink_target:
            if not os.path.exists(os.readlink(installation.symlink_target)):
                installation.status = InstallStatus.OUTDATED

        await self.db.flush()
        return installation

    def _auto_select_mode(self, skill: HermesSkill, requested_mode: str) -> str:
        if requested_mode and requested_mode != "auto":
            return requested_mode

        if skill.is_mcp_exposed and not skill.runtime:
            return InstallMode.REGISTRY_BIND
        return InstallMode.COPY

    async def _build_target_path(
        self,
        skill: HermesSkill,
        agent_id: str,
        profile_id: str | None,
        mode: str,
    ) -> Path:
        if mode == InstallMode.REGISTRY_BIND:
            return Path("")

        safe_skill_id = skill.skill_id.replace(".", "-")

        profile_root_path = await self._get_profile_root_path(agent_id)
        if profile_root_path:
            return Path(profile_root_path) / "skills" / safe_skill_id

        hub_root = Path(settings.HERMES_SKILL_HUB_ROOT)
        profile_part = profile_id or "default"
        return hub_root / "agents" / agent_id / profile_part / "skills" / safe_skill_id

    async def _get_profile_root_path(self, agent_id: str) -> str | None:
        from app.models.instance import Instance
        stmt = select(Instance).where(
            not_deleted(Instance),
            Instance.id == agent_id,
        )
        result = await self.db.execute(stmt)
        instance = result.scalar_one_or_none()
        if not instance:
            return None

        advanced_config = getattr(instance, "advanced_config", None)
        if advanced_config and isinstance(advanced_config, dict):
            return advanced_config.get("profile_root_path")
        return None

    async def _execute_file_operation(
        self,
        installation: HermesSkillInstallation,
        skill: HermesSkill,
        target_path: Path,
        mode: str,
    ) -> None:
        source = Path(skill.canonical_path) if skill.canonical_path else None
        if not source or not source.is_dir():
            if mode != InstallMode.REGISTRY_BIND:
                raise ValueError(f"Skill 源路径不存在: {source}")
            return

        if mode == InstallMode.COPY:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(str(source), str(target_path), dirs_exist_ok=True)
        elif mode == InstallMode.SYMLINK:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if target_path.exists() or target_path.is_symlink():
                target_path.unlink()
            os.symlink(str(source.resolve()), str(target_path))
            installation.link_type = "symlink"
            installation.symlink_target = str(source.resolve())
        elif mode == InstallMode.DOCKER_MOUNT:
            installation.link_type = "docker_mount"
            installation.symlink_target = str(source.resolve())
        elif mode == InstallMode.REGISTRY_BIND:
            installation.link_type = "registry_bind"
        elif mode == InstallMode.API_DEPLOY:
            installation.link_type = "api_deploy"

    async def _execute_file_cleanup(self, installation: HermesSkillInstallation) -> None:
        if not installation.installed_path:
            return
        path = Path(installation.installed_path)
        mode = installation.install_mode

        if mode == InstallMode.COPY and path.is_dir():
            shutil.rmtree(str(path), ignore_errors=True)
        elif mode == InstallMode.SYMLINK and path.is_symlink():
            path.unlink()
        elif mode in (InstallMode.DOCKER_MOUNT, InstallMode.REGISTRY_BIND, InstallMode.API_DEPLOY):
            pass

    async def _get_active_skill(self, skill_id: str, org_id: str) -> HermesSkill | None:
        result = await self.db.execute(
            select(HermesSkill).where(
                not_deleted(HermesSkill),
                HermesSkill.skill_id == skill_id,
                HermesSkill.org_id == org_id,
                HermesSkill.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()
