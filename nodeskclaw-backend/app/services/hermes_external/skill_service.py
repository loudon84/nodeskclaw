"""External Docker Hermes skills directory service."""

from __future__ import annotations

import asyncio
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import BadRequestError, NotFoundError
from app.models.instance import Instance
from app.schemas.external_docker import ExternalDockerSkillActionResponse, ExternalDockerSkillItem, ExternalDockerSkillsResponse
from app.services.hermes_expert.expert_filesystem import RESOURCES_ROOT, read_json, safe_extract_zip, write_json
from app.services.hermes_expert.expert_manifest import parse_manifest, write_manifest
from app.services.hermes_external._common import resolve_paths
from app.services.hermes_external.path_resolver import HermesExternalPathResolver

_path_resolver = HermesExternalPathResolver()
SKILL_INDEX_NAME = ".index.json"
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
    return value


def _backup_skill_dir(ep, skill_dir: Path) -> str:
    slug = skill_dir.name
    backup_root = ep.backups_dir / "skills"
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = backup_root / f"{slug}-{stamp}"
    shutil.copytree(skill_dir, dest)
    return str(dest)


def _ensure_skill_dirs(ep) -> None:
    _path_resolver.ensure_auto_create_dirs(ep)
    ep.skills_dir.mkdir(parents=True, exist_ok=True)
    ep.skill_inbox_dir.mkdir(parents=True, exist_ok=True)
    ep.backups_dir.mkdir(parents=True, exist_ok=True)


def _manifest_to_item(skill_dir: Path, *, source: str | None = None) -> ExternalDockerSkillItem:
    manifest = parse_manifest(skill_dir)
    meta = read_json(skill_dir / ".install-meta.json")
    status = "disabled" if not manifest.enabled else "installed"
    if manifest.requires_restart and manifest.enabled:
        status = "pending_restart"
    resolved_source = source or str(meta.get("source") or "manual")
    return ExternalDockerSkillItem(
        name=manifest.name,
        slug=manifest.slug,
        path=str(skill_dir),
        kind="directory",
        category="skills",
        version=manifest.version,
        description=manifest.description or None,
        enabled=manifest.enabled,
        status=status,
        source=resolved_source,
        requires_restart=manifest.requires_restart,
    )


def _build_skill_item(skill_dir: Path) -> ExternalDockerSkillItem | None:
    if not skill_dir.is_dir() or skill_dir.name.startswith("."):
        return None
    if (skill_dir / "manifest.json").is_file():
        try:
            return _manifest_to_item(skill_dir)
        except BadRequestError:
            pass
    meta = read_json(skill_dir / ".install-meta.json")
    enabled = meta.get("enabled", True) if meta else True
    return ExternalDockerSkillItem(
        name=skill_dir.name,
        slug=skill_dir.name,
        path=str(skill_dir),
        kind="directory",
        category="skills",
        enabled=bool(enabled),
        status="disabled" if not enabled else "installed",
        source=str(meta.get("source") or "manual"),
        requires_restart=False,
    )


def _scan_dir(base: Path, category: str) -> list[ExternalDockerSkillItem]:
    if not base.is_dir():
        return []
    items: list[ExternalDockerSkillItem] = []
    for entry in sorted(base.iterdir(), key=lambda p: p.name.lower()):
        if entry.name.startswith("."):
            continue
        if category == "skills" and entry.is_dir():
            built = _build_skill_item(entry)
            if built:
                items.append(built)
            continue
        items.append(
            ExternalDockerSkillItem(
                name=entry.name,
                path=str(entry),
                kind="directory" if entry.is_dir() else "file",
                category=category,
            )
        )
    return items


def _skill_dir(instance: Instance, skill_slug: str):
    ep = resolve_paths(instance)
    slug = _validate_skill_slug(skill_slug)
    path = ep.skills_dir / slug
    if not path.is_dir():
        raise NotFoundError(
            message=f"技能不存在: {slug}",
            message_key="errors.hermes_expert.skill_not_found",
        )
    try:
        path.resolve().relative_to(ep.skills_dir.resolve())
    except ValueError as exc:
        raise BadRequestError(
            message="非法技能路径",
            message_key="errors.external_docker.skill_path_invalid",
        ) from exc
    return ep, path


def _install_skill_dir(instance: Instance, source_dir: Path, *, source: str) -> ExternalDockerSkillItem:
    ep = resolve_paths(instance)
    _ensure_skill_dirs(ep)
    manifest = parse_manifest(source_dir)
    if not (source_dir / "SKILL.md").is_file():
        raise BadRequestError(
            message="技能包缺少 SKILL.md",
            message_key="errors.hermes_expert.skill_md_missing",
        )
    target = ep.skills_dir / manifest.slug
    if target.exists():
        _backup_skill_dir(ep, target)
        shutil.rmtree(target)
    if source_dir.resolve() != target.resolve():
        shutil.copytree(source_dir, target)
    write_json(
        target / ".install-meta.json",
        {
            "source": source,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    item = _manifest_to_item(target, source=source)
    item.requires_restart = True
    if item.status == "installed":
        item.status = "pending_restart"
    return item


def _write_skill_index(ep) -> None:
    items = _scan_dir(ep.skills_dir, "skills")
    index = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "skills": [
            {
                "slug": item.slug or item.name,
                "name": item.name,
                "version": item.version,
                "enabled": item.enabled,
                "status": item.status,
                "source": item.source,
            }
            for item in items
        ],
    }
    write_json(ep.skills_dir / SKILL_INDEX_NAME, index)


def list_skills(instance: Instance) -> ExternalDockerSkillsResponse:
    ep = resolve_paths(instance)
    _ensure_skill_dirs(ep)

    skill_inbox = ep.skill_inbox_dir
    legacy_inbox = ep.host_data_dir / "skills-inbox"
    inbox_dir = skill_inbox if skill_inbox.is_dir() else legacy_inbox

    items: list[ExternalDockerSkillItem] = []
    items.extend(_scan_dir(ep.skills_dir, "skills"))
    items.extend(_scan_dir(inbox_dir, "skill-inbox"))
    items.extend(_scan_dir(ep.tools_dir, "tools"))
    items.extend(_scan_dir(ep.plugins_dir, "plugins"))

    return ExternalDockerSkillsResponse(
        skills_dir=str(ep.skills_dir),
        skill_inbox_dir=str(inbox_dir),
        tools_dir=str(ep.tools_dir),
        plugins_dir=str(ep.plugins_dir),
        items=items,
    )


def install_builtin_bundle(instance: Instance, bundle: str) -> ExternalDockerSkillActionResponse:
    bundle_name = (bundle or "").strip()
    if not bundle_name:
        raise BadRequestError(
            message="bundle 名称不能为空",
            message_key="errors.validation.required_field",
        )
    bundle_dir = RESOURCES_ROOT / "skill-bundles" / bundle_name
    if not bundle_dir.is_dir():
        raise NotFoundError(
            message=f"内置技能包不存在: {bundle_name}",
            message_key="errors.hermes_expert.skill_bundle_not_found",
        )
    installed: list[ExternalDockerSkillItem] = []
    for child in sorted(bundle_dir.iterdir()):
        if not child.is_dir():
            continue
        installed.append(_install_skill_dir(instance, child, source="builtin"))
    rescan_skills(instance)
    first = installed[0] if installed else None
    return ExternalDockerSkillActionResponse(
        success=True,
        message="内置技能包已安装，重启后生效",
        requires_restart=True,
        item=first,
        items=installed,
    )


def upload_skill_zip(instance: Instance, zip_bytes: bytes) -> ExternalDockerSkillActionResponse:
    ep = resolve_paths(instance)
    _ensure_skill_dirs(ep)
    extracted = safe_extract_zip(
        zip_bytes,
        ep.skills_dir,
        max_size_mb=settings.HERMES_SKILL_IMPORT_MAX_SIZE_MB,
    )
    extract_root = extracted if extracted.name.startswith(".extract-") else extracted.parent
    try:
        item = _install_skill_dir(instance, extracted, source="upload")
    finally:
        if extract_root.name.startswith(".extract-"):
            shutil.rmtree(extract_root, ignore_errors=True)
    rescan_skills(instance)
    return ExternalDockerSkillActionResponse(
        success=True,
        message="技能已上传并安装，重启后生效",
        requires_restart=True,
        item=item,
    )


async def _clone_skill_repo(auth_repo: str, ref: str, temp_dir: Path, skill_slug: str | None) -> Path:
    proc = await asyncio.create_subprocess_exec(
        "git", "clone", "--depth", "1", "--branch", ref, auth_repo, str(temp_dir / "repo"),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise BadRequestError(
            message="Git 克隆失败，请检查仓库地址与分支",
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


async def install_from_git(
    instance: Instance,
    *,
    repo: str,
    ref: str = "main",
    skill_slug: str | None = None,
) -> ExternalDockerSkillActionResponse:
    repo = _validate_git_repo(repo)
    ref = (ref or "main").strip() or "main"
    if skill_slug:
        _validate_skill_slug(skill_slug)

    token = settings.PRIVATE_GIT_TOKEN_SECRET
    username = settings.PRIVATE_GIT_USERNAME
    auth_repo = repo
    if token:
        if repo.startswith("https://") and username:
            auth_repo = repo.replace("https://", f"https://{username}:{token}@", 1)
        elif repo.startswith("https://"):
            auth_repo = repo.replace("https://", f"https://{token}@", 1)

    temp_dir = Path(tempfile.mkdtemp(prefix="external-docker-skill-git-"))
    try:
        source_dir = await _clone_skill_repo(auth_repo, ref, temp_dir, skill_slug)
        item = _install_skill_dir(instance, source_dir, source="git")
        rescan_skills(instance)
        return ExternalDockerSkillActionResponse(
            success=True,
            message="Git 技能已安装，重启后生效",
            requires_restart=True,
            item=item,
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _set_enabled(instance: Instance, skill_slug: str, *, enabled: bool) -> ExternalDockerSkillActionResponse:
    ep, skill_dir = _skill_dir(instance, skill_slug)
    if (skill_dir / "manifest.json").is_file():
        manifest = parse_manifest(skill_dir)
        manifest.enabled = enabled
        write_manifest(skill_dir, manifest)
    else:
        meta = read_json(skill_dir / ".install-meta.json")
        meta["enabled"] = enabled
        meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        meta.setdefault("source", "external_docker_ui")
        write_json(skill_dir / ".install-meta.json", meta)
    item = _build_skill_item(skill_dir)
    if item:
        item.requires_restart = True
    rescan_skills(instance)
    message = "技能已启用，重启后生效" if enabled else "技能已禁用，重启后生效"
    return ExternalDockerSkillActionResponse(
        success=True,
        message=message,
        requires_restart=True,
        item=item,
    )


def enable_skill(instance: Instance, skill_slug: str) -> ExternalDockerSkillActionResponse:
    return _set_enabled(instance, skill_slug, enabled=True)


def disable_skill(instance: Instance, skill_slug: str) -> ExternalDockerSkillActionResponse:
    return _set_enabled(instance, skill_slug, enabled=False)


def delete_skill(instance: Instance, skill_slug: str) -> ExternalDockerSkillActionResponse:
    ep, skill_dir = _skill_dir(instance, skill_slug)
    _backup_skill_dir(ep, skill_dir)
    shutil.rmtree(skill_dir)
    rescan_skills(instance)
    return ExternalDockerSkillActionResponse(
        success=True,
        message="技能已删除，重启后生效",
        requires_restart=True,
    )


def rescan_skills(instance: Instance) -> ExternalDockerSkillActionResponse:
    ep = resolve_paths(instance)
    _ensure_skill_dirs(ep)
    _write_skill_index(ep)
    response = list_skills(instance)
    return ExternalDockerSkillActionResponse(
        success=True,
        message="技能目录已重扫",
        requires_restart=False,
        items=response.items,
    )
