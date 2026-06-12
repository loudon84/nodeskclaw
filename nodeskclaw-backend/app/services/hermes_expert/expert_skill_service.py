"""Instance-level Hermes expert skill management."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.instance import Instance
from app.services.hermes_expert.expert_filesystem import (
    RESOURCES_ROOT,
    backup_path,
    expert_skill_inbox_dir_for_instance,
    expert_skills_dir_for_instance,
    read_json,
    safe_extract_zip,
    write_json,
)
from app.services.hermes_expert.expert_manifest import (
    ExpertSkillManifest,
    list_skill_files,
    parse_manifest,
    write_manifest,
)
from app.services.hermes_expert.schemas import ExpertSkillInfo

EXPERT_RUNTIME = "hermes-webui-expert"
SKILL_INDEX_NAME = ".index.json"


class ExpertSkillService:
    def list_skills(self, instance: Instance) -> list[ExpertSkillInfo]:
        self._require_expert_instance(instance)
        skills_dir = expert_skills_dir_for_instance(instance)
        items: list[ExpertSkillInfo] = []
        for child in sorted(skills_dir.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            try:
                items.append(self._build_skill_info(child))
            except BadRequestError:
                continue
        return items

    def get_skill(self, instance: Instance, skill_slug: str) -> ExpertSkillInfo:
        self._require_expert_instance(instance)
        skill_dir = self._skill_dir(instance, skill_slug)
        return self._build_skill_info(skill_dir)

    def install_builtin_bundle(self, instance: Instance, bundle: str) -> list[ExpertSkillInfo]:
        self._require_expert_instance(instance)
        bundle_dir = RESOURCES_ROOT / "skill-bundles" / bundle
        if not bundle_dir.is_dir():
            raise NotFoundError(
                message=f"内置技能包不存在: {bundle}",
                message_key="errors.hermes_expert.skill_bundle_not_found",
            )
        installed: list[ExpertSkillInfo] = []
        for child in sorted(bundle_dir.iterdir()):
            if not child.is_dir():
                continue
            installed.append(self._install_skill_dir(instance, child, source="builtin"))
        self.rescan_skills(instance)
        return installed

    def upload_skill_zip(self, instance: Instance, zip_bytes: bytes) -> ExpertSkillInfo:
        self._require_expert_instance(instance)
        skills_dir = expert_skills_dir_for_instance(instance)
        extracted = safe_extract_zip(
            zip_bytes,
            skills_dir,
            max_size_mb=settings.HERMES_SKILL_IMPORT_MAX_SIZE_MB,
        )
        manifest = parse_manifest(extracted)
        target = skills_dir / manifest.slug
        if target.exists():
            backup_path(target)
            shutil.rmtree(target)
        shutil.move(str(extracted), str(target))
        if extracted.exists():
            shutil.rmtree(extracted, ignore_errors=True)
        info = self._install_skill_dir(instance, target, source="upload")
        self.rescan_skills(instance)
        return info

    def install_from_git(
        self,
        instance: Instance,
        *,
        repo: str,
        ref: str,
        skill_slug: str | None = None,
    ) -> ExpertSkillInfo:
        self._require_expert_instance(instance)
        repo = (repo or "").strip()
        if not repo:
            raise BadRequestError(
                message="Git 仓库地址不能为空",
                message_key="errors.validation.required_field",
            )
        token = settings.PRIVATE_GIT_TOKEN_SECRET
        username = settings.PRIVATE_GIT_USERNAME
        if not token:
            raise BadRequestError(
                message="未配置私有 Git Token，请联系管理员在系统配置中设置 PRIVATE_GIT_TOKEN_SECRET",
                message_key="errors.hermes_expert.private_git_not_configured",
            )
        auth_repo = repo
        if repo.startswith("https://") and username:
            auth_repo = repo.replace("https://", f"https://{username}:{token}@", 1)
        elif repo.startswith("https://"):
            auth_repo = repo.replace("https://", f"https://{token}@", 1)

        import asyncio
        import tempfile

        temp_dir = Path(tempfile.mkdtemp(prefix="hermes-skill-git-"))
        try:
            source_dir = asyncio.run(self._clone_skill_repo(auth_repo, ref, temp_dir, skill_slug))
            manifest = parse_manifest(source_dir)
            target = expert_skills_dir_for_instance(instance) / manifest.slug
            if target.exists():
                backup_path(target)
                shutil.rmtree(target)
            shutil.copytree(source_dir, target)
            info = self._install_skill_dir(instance, target, source="git")
            self.rescan_skills(instance)
            return info
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def _clone_skill_repo(
        self,
        auth_repo: str,
        ref: str,
        temp_dir: Path,
        skill_slug: str | None,
    ) -> Path:
        import asyncio
        proc = await asyncio.create_subprocess_exec(
            "git", "clone", "--depth", "1", "--branch", ref, auth_repo, str(temp_dir / "repo"),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise BadRequestError(
                message="从私有 Git 拉取技能包失败，请检查仓库地址与凭据配置",
                message_key="errors.hermes_expert.skill_git_clone_failed",
            )
        repo_dir = temp_dir / "repo"
        if skill_slug:
            candidate = repo_dir / skill_slug
            if not candidate.is_dir():
                raise NotFoundError(
                    message=f"仓库中不存在技能目录: {skill_slug}",
                    message_key="errors.hermes_expert.skill_not_found",
                )
            return candidate
        for child in repo_dir.iterdir():
            if child.is_dir() and (child / "SKILL.md").is_file():
                return child
        if (repo_dir / "SKILL.md").is_file():
            return repo_dir
        raise BadRequestError(
            message="Git 仓库中未找到有效技能包",
            message_key="errors.hermes_expert.skill_git_invalid_structure",
        )

    def enable_skill(self, instance: Instance, skill_slug: str) -> ExpertSkillInfo:
        return self._set_enabled(instance, skill_slug, enabled=True)

    def disable_skill(self, instance: Instance, skill_slug: str) -> ExpertSkillInfo:
        return self._set_enabled(instance, skill_slug, enabled=False)

    def delete_skill(self, instance: Instance, skill_slug: str) -> None:
        self._require_expert_instance(instance)
        skill_dir = self._skill_dir(instance, skill_slug)
        backup_path(skill_dir)
        shutil.rmtree(skill_dir)
        self.rescan_skills(instance)

    def rescan_skills(self, instance: Instance) -> list[ExpertSkillInfo]:
        skills = self.list_skills(instance)
        index = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "skills": [
                {
                    "slug": item.slug,
                    "name": item.name,
                    "version": item.version,
                    "enabled": item.enabled,
                    "status": item.status,
                    "source": item.source,
                }
                for item in skills
            ],
        }
        write_json(expert_skills_dir_for_instance(instance) / SKILL_INDEX_NAME, index)
        return skills

    def _set_enabled(self, instance: Instance, skill_slug: str, *, enabled: bool) -> ExpertSkillInfo:
        self._require_expert_instance(instance)
        skill_dir = self._skill_dir(instance, skill_slug)
        manifest = parse_manifest(skill_dir)
        manifest.enabled = enabled
        write_manifest(skill_dir, manifest)
        info = self._build_skill_info(skill_dir)
        self.rescan_skills(instance)
        return info

    def _install_skill_dir(self, instance: Instance, source_dir: Path, *, source: str) -> ExpertSkillInfo:
        manifest = parse_manifest(source_dir)
        if not (source_dir / "SKILL.md").is_file():
            raise BadRequestError(
                message="技能包缺少 SKILL.md",
                message_key="errors.hermes_expert.skill_md_missing",
            )
        target = expert_skills_dir_for_instance(instance) / manifest.slug
        if target.exists():
            backup_path(target)
            shutil.rmtree(target)
        if source_dir.resolve() != target.resolve():
            shutil.copytree(source_dir, target)
        meta_path = target / ".install-meta.json"
        meta_path.write_text(json.dumps({
            "source": source,
            "installed_at": datetime.now(timezone.utc).isoformat(),
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        status = "pending_restart" if manifest.requires_restart else "installed"
        if not manifest.enabled:
            status = "disabled"
        return ExpertSkillInfo(
            slug=manifest.slug,
            name=manifest.name,
            version=manifest.version,
            description=manifest.description,
            enabled=manifest.enabled,
            status=status,
            source=source,
            requires_restart=manifest.requires_restart,
            installed_at=datetime.now(timezone.utc).isoformat(),
            files=list_skill_files(target),
        )

    def _build_skill_info(self, skill_dir: Path) -> ExpertSkillInfo:
        manifest = parse_manifest(skill_dir)
        meta = read_json(skill_dir / ".install-meta.json")
        status = "disabled" if not manifest.enabled else "installed"
        if manifest.requires_restart and manifest.enabled:
            status = "pending_restart"
        return ExpertSkillInfo(
            slug=manifest.slug,
            name=manifest.name,
            version=manifest.version,
            description=manifest.description,
            enabled=manifest.enabled,
            status=status,
            source=str(meta.get("source") or "filesystem"),
            requires_restart=manifest.requires_restart,
            installed_at=meta.get("installed_at"),
            files=list_skill_files(skill_dir),
        )

    @staticmethod
    def _skill_dir(instance: Instance, skill_slug: str) -> Path:
        path = expert_skills_dir_for_instance(instance) / skill_slug
        if not path.is_dir():
            raise NotFoundError(
                message=f"技能不存在: {skill_slug}",
                message_key="errors.hermes_expert.skill_not_found",
            )
        return path

    @staticmethod
    def _require_expert_instance(instance: Instance) -> None:
        if instance.runtime != EXPERT_RUNTIME:
            raise BadRequestError(
                message="该实例不是 Hermes 专家服务",
                message_key="errors.hermes_expert.invalid_runtime",
            )
