"""Per-profile Hermes skills service."""

from __future__ import annotations

import asyncio
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.instance import Instance
from app.schemas.profile_extended import (
    ProfileSkillActionResponse,
    ProfileSkillItem,
    ProfileSkillsResponse,
)
from app.services.hermes_expert.expert_filesystem import RESOURCES_ROOT, safe_extract_zip
from app.services.hermes_expert.expert_manifest import parse_manifest
from app.services.hermes_external._profile_helpers import resolve_profile_paths, resolve_profile_paths_for_instance
from app.services.hermes_external.path_resolver import HermesProfilePaths

SLUG_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+$")


def _validate_skill_slug(slug: str) -> str:
    value = (slug or "").strip()
    if not value or not SLUG_PATTERN.match(value):
        raise BadRequestError(
            message="技能 slug 格式无效",
            message_key="errors.validation.invalid_slug",
        )
    if ".." in value or "/" in value or "\\" in value:
        raise BadRequestError(
            message="技能 slug 格式无效",
            message_key="errors.validation.invalid_slug",
        )
    return value


def _validate_git_repo(repo: str) -> str:
    value = (repo or "").strip()
    if not value.startswith(("http://", "https://")):
        raise BadRequestError(
            message="Git 仓库地址必须是 http 或 https",
            message_key="errors.external_docker.skill_git_invalid_url",
        )
    hosts = [h.strip().lower() for h in settings.HERMES_GIT_ALLOWED_HOSTS.split(",") if h.strip()]
    if hosts:
        host = (urlparse(value).hostname or "").lower()
        if host not in hosts:
            raise BadRequestError(
                message="Git 仓库域名不在白名单内",
                message_key="errors.external_docker.skill_git_host_not_allowed",
            )
    return value


def _ensure_skills_dir(pp: HermesProfilePaths) -> Path:
    pp.skills_dir.mkdir(parents=True, exist_ok=True)
    return pp.skills_dir


def _skill_enabled(skill_dir: Path) -> bool:
    return not (skill_dir / ".disabled").is_file()


def _set_skill_enabled(skill_dir: Path, enabled: bool) -> None:
    marker = skill_dir / ".disabled"
    if enabled:
        marker.unlink(missing_ok=True)
    else:
        marker.write_text("disabled\n", encoding="utf-8")


def _backup_skill_dir(pp: HermesProfilePaths, skill_dir: Path) -> str:
    slug = skill_dir.name
    backup_root = pp.backups_dir / "skills"
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = backup_root / f"{slug}-{stamp}"
    shutil.copytree(skill_dir, dest)
    return str(dest)


def _build_skill_item(skill_dir: Path) -> ProfileSkillItem | None:
    if not skill_dir.is_dir() or skill_dir.name.startswith("."):
        return None
    stat = skill_dir.stat()
    slug = skill_dir.name
    name = slug
    source = "profile"
    try:
        manifest = parse_manifest(skill_dir)
        slug = manifest.slug or slug
        name = manifest.name or slug
    except BadRequestError:
        pass
    return ProfileSkillItem(
        slug=slug,
        name=name,
        path=str(skill_dir),
        enabled=_skill_enabled(skill_dir),
        has_skill_md=(skill_dir / "SKILL.md").is_file(),
        source=source,
        updated_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
    )


def _install_skill_dir(pp: HermesProfilePaths, source_dir: Path, *, source: str) -> ProfileSkillItem:
    _ensure_skills_dir(pp)
    if not (source_dir / "SKILL.md").is_file():
        raise BadRequestError(
            message="技能包缺少 SKILL.md",
            message_key="errors.hermes_expert.skill_md_missing",
        )
    try:
        manifest = parse_manifest(source_dir)
        slug = manifest.slug or source_dir.name
    except BadRequestError:
        slug = _validate_skill_slug(source_dir.name)
    slug = _validate_skill_slug(slug)
    target = pp.skills_dir / slug
    if target.exists():
        _backup_skill_dir(pp, target)
        shutil.rmtree(target)
    if source_dir.resolve() != target.resolve():
        shutil.copytree(source_dir, target)
    return _build_skill_item(target) or ProfileSkillItem(
        slug=slug,
        name=slug,
        path=str(target),
        enabled=True,
        has_skill_md=True,
        source=source,
        updated_at=datetime.now(timezone.utc),
    )


def list_profile_skills(host_data_dir: Path, profile_name: str) -> ProfileSkillsResponse:
    pp = resolve_profile_paths(host_data_dir, profile_name)
    skills_dir = _ensure_skills_dir(pp)
    items: list[ProfileSkillItem] = []
    for entry in sorted(skills_dir.iterdir(), key=lambda p: p.name.lower()):
        built = _build_skill_item(entry)
        if built:
            items.append(built)
    return ProfileSkillsResponse(profile=pp.profile, skills_dir=str(skills_dir), items=items)


def list_profile_skills_instance(instance: Instance, profile_name: str) -> ProfileSkillsResponse:
    from app.services.hermes_external._common import resolve_paths
    ep = resolve_paths(instance)
    return list_profile_skills(ep.host_data_dir, profile_name)


def install_builtin(host_data_dir: Path, profile_name: str, bundle: str) -> ProfileSkillActionResponse:
    pp = resolve_profile_paths(host_data_dir, profile_name)
    bundle_name = (bundle or "").strip()
    if not bundle_name:
        raise BadRequestError(message="bundle 名称不能为空", message_key="errors.validation.required_field")
    bundle_dir = RESOURCES_ROOT / "skill-bundles" / bundle_name
    if not bundle_dir.is_dir():
        raise NotFoundError(
            message=f"内置技能包不存在: {bundle_name}",
            message_key="errors.hermes_expert.skill_bundle_not_found",
        )
    installed: ProfileSkillItem | None = None
    for child in sorted(bundle_dir.iterdir()):
        if not child.is_dir():
            continue
        installed = _install_skill_dir(pp, child, source="builtin")
    if not installed:
        raise BadRequestError(message="内置技能包为空", message_key="errors.hermes_expert.skill_bundle_not_found")
    return ProfileSkillActionResponse(
        success=True,
        message="内置技能已安装",
        skill_slug=installed.slug,
        installed_path=installed.path,
    )


def upload_skill_zip(host_data_dir: Path, profile_name: str, zip_bytes: bytes) -> ProfileSkillActionResponse:
    pp = resolve_profile_paths(host_data_dir, profile_name)
    skills_dir = _ensure_skills_dir(pp)
    extracted = safe_extract_zip(
        zip_bytes,
        skills_dir,
        max_size_mb=settings.HERMES_SKILL_IMPORT_MAX_SIZE_MB,
    )
    extract_root = extracted if extracted.name.startswith(".extract-") else extracted.parent
    try:
        item = _install_skill_dir(pp, extracted, source="upload")
    finally:
        if extract_root.name.startswith(".extract-"):
            shutil.rmtree(extract_root, ignore_errors=True)
    return ProfileSkillActionResponse(
        success=True,
        message="技能已上传并安装",
        skill_slug=item.slug,
        installed_path=item.path,
    )


async def _clone_skill_repo(auth_repo: str, ref: str, temp_dir: Path, subdir: str | None) -> Path:
    proc = await asyncio.create_subprocess_exec(
        "git", "clone", "--depth", "1", "--branch", ref, auth_repo, str(temp_dir / "repo"),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    if proc.returncode != 0:
        raise BadRequestError(
            message="Git 克隆失败，请检查仓库地址与分支",
            message_key="errors.hermes_expert.skill_git_clone_failed",
        )
    repo_dir = temp_dir / "repo"
    if subdir:
        candidate = repo_dir / subdir.strip("/")
        if not candidate.is_dir():
            raise NotFoundError(
                message=f"仓库中不存在技能目录: {subdir}",
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


async def install_from_git(
    host_data_dir: Path,
    profile_name: str,
    *,
    repo_url: str,
    ref: str = "main",
    subdir: str | None = None,
) -> ProfileSkillActionResponse:
    pp = resolve_profile_paths(host_data_dir, profile_name)
    repo = _validate_git_repo(repo_url)
    ref = (ref or "main").strip() or "main"
    token = settings.PRIVATE_GIT_TOKEN_SECRET
    username = settings.PRIVATE_GIT_USERNAME
    auth_repo = repo
    if token:
        if repo.startswith("https://") and username:
            auth_repo = repo.replace("https://", f"https://{username}:{token}@", 1)
        elif repo.startswith("https://"):
            auth_repo = repo.replace("https://", f"https://{token}@", 1)
    temp_dir = Path(tempfile.mkdtemp(prefix="profile-skill-git-"))
    try:
        source_dir = await _clone_skill_repo(auth_repo, ref, temp_dir, subdir)
        item = _install_skill_dir(pp, source_dir, source="git")
        return ProfileSkillActionResponse(
            success=True,
            message="Git 技能已安装",
            skill_slug=item.slug,
            installed_path=item.path,
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _skill_dir(pp: HermesProfilePaths, skill_slug: str) -> Path:
    slug = _validate_skill_slug(skill_slug)
    path = pp.skills_dir / slug
    if not path.is_dir():
        raise NotFoundError(
            message=f"技能不存在: {slug}",
            message_key="errors.hermes_expert.skill_not_found",
        )
    return path


def enable_skill(host_data_dir: Path, profile_name: str, skill_slug: str) -> ProfileSkillActionResponse:
    pp = resolve_profile_paths(host_data_dir, profile_name)
    skill_dir = _skill_dir(pp, skill_slug)
    _set_skill_enabled(skill_dir, True)
    item = _build_skill_item(skill_dir)
    return ProfileSkillActionResponse(
        success=True,
        message="技能已启用",
        skill_slug=skill_slug,
        installed_path=str(skill_dir) if item else None,
    )


def disable_skill(host_data_dir: Path, profile_name: str, skill_slug: str) -> ProfileSkillActionResponse:
    pp = resolve_profile_paths(host_data_dir, profile_name)
    skill_dir = _skill_dir(pp, skill_slug)
    _set_skill_enabled(skill_dir, False)
    return ProfileSkillActionResponse(
        success=True,
        message="技能已禁用",
        skill_slug=skill_slug,
        installed_path=str(skill_dir),
    )


def delete_skill(host_data_dir: Path, profile_name: str, skill_slug: str) -> ProfileSkillActionResponse:
    pp = resolve_profile_paths(host_data_dir, profile_name)
    skill_dir = _skill_dir(pp, skill_slug)
    _backup_skill_dir(pp, skill_dir)
    shutil.rmtree(skill_dir)
    return ProfileSkillActionResponse(
        success=True,
        message="技能已删除",
        skill_slug=skill_slug,
    )


def rescan_skills(host_data_dir: Path, profile_name: str) -> ProfileSkillsResponse:
    return list_profile_skills(host_data_dir, profile_name)
