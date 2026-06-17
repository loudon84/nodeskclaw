"""Per-profile Hermes file service."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.instance import Instance
from app.schemas.profile_extended import (
    ProfileFileActionResponse,
    ProfileFileItem,
    ProfileFileReadResponse,
    ProfileFilesResponse,
)
from app.services.hermes_external._common import resolve_paths
from app.services.hermes_external._profile_helpers import (
    assert_not_protected_file,
    resolve_profile_paths,
    resolve_scope_path,
)
from app.services.hermes_external.path_resolver import HermesExternalPathResolver

_path_resolver = HermesExternalPathResolver()
_MAX_TEXT_BYTES = 1024 * 1024
_TEXT_EXTENSIONS = {
    ".md", ".txt", ".json", ".yaml", ".yml", ".env", ".toml", ".xml",
    ".html", ".css", ".js", ".ts", ".py", ".sh", ".csv", ".log", ".ini",
}


def _is_probably_text(path: Path) -> bool:
    if path.suffix.lower() in _TEXT_EXTENSIONS:
        return True
    try:
        sample = path.read_bytes()[:512]
        return b"\x00" not in sample
    except OSError:
        return False


def _host_data_dir(instance: Instance) -> Path:
    ep = resolve_paths(instance)
    _path_resolver.validate_host_data_dir(ep)
    return ep.host_data_dir


def list_profile_files(
    host_data_dir: Path,
    profile_name: str,
    *,
    scope: str = "workspace",
    path: str = "",
) -> ProfileFilesResponse:
    pp = resolve_profile_paths(host_data_dir, profile_name)
    allowed_root, target = resolve_scope_path(pp, scope, path)
    if not target.exists():
        return ProfileFilesResponse(
            profile=pp.profile,
            scope=scope,
            base_path=str(allowed_root),
            path=path,
            items=[],
        )
    if not target.is_dir():
        raise BadRequestError(
            message="目标路径不是目录",
            message_key="errors.external_docker.path_not_directory",
        )
    items: list[ProfileFileItem] = []
    for entry in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if entry.name.startswith(".") and entry.name not in (".env",):
            continue
        stat = entry.stat()
        rel = str(entry.relative_to(allowed_root)).replace("\\", "/")
        items.append(
            ProfileFileItem(
                name=entry.name,
                type="dir" if entry.is_dir() else "file",
                size=0 if entry.is_dir() else stat.st_size,
                updated_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                path=rel,
            )
        )
    return ProfileFilesResponse(
        profile=pp.profile,
        scope=scope,
        base_path=str(allowed_root),
        path=path,
        items=items,
    )


def list_profile_files_instance(instance: Instance, profile_name: str, **kwargs) -> ProfileFilesResponse:
    return list_profile_files(_host_data_dir(instance), profile_name, **kwargs)


def read_profile_file(
    host_data_dir: Path,
    profile_name: str,
    *,
    scope: str,
    path: str,
) -> ProfileFileReadResponse:
    pp = resolve_profile_paths(host_data_dir, profile_name)
    _, target = resolve_scope_path(pp, scope, path)
    if not target.is_file():
        return ProfileFileReadResponse(
            profile=pp.profile,
            scope=scope,
            path=path,
            file_path=str(target),
            exists=False,
            message="文件不存在",
        )
    size = target.stat().st_size
    if size > _MAX_TEXT_BYTES:
        return ProfileFileReadResponse(
            profile=pp.profile,
            scope=scope,
            path=path,
            file_path=str(target),
            exists=True,
            binary=True,
            message="文件过大，无法预览",
        )
    if not _is_probably_text(target):
        return ProfileFileReadResponse(
            profile=pp.profile,
            scope=scope,
            path=path,
            file_path=str(target),
            exists=True,
            binary=True,
            message="二进制文件不可预览",
        )
    return ProfileFileReadResponse(
        profile=pp.profile,
        scope=scope,
        path=path,
        file_path=str(target),
        exists=True,
        content=target.read_text(encoding="utf-8"),
        binary=False,
    )


def _backup_file(pp, target: Path) -> str | None:
    if not target.is_file():
        return None
    backup_dir = pp.backups_dir / "files"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_file = backup_dir / f"{target.name}-{stamp}.bak"
    shutil.copy2(target, backup_file)
    return str(backup_file)


def write_profile_file(
    host_data_dir: Path,
    profile_name: str,
    *,
    scope: str,
    path: str,
    content: str,
) -> ProfileFileActionResponse:
    pp = resolve_profile_paths(host_data_dir, profile_name)
    assert_not_protected_file(path)
    _, target = resolve_scope_path(pp, scope, path)
    target.parent.mkdir(parents=True, exist_ok=True)
    backup_file = _backup_file(pp, target)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    _path_resolver.validate_profile_path(pp.profile_dir, tmp)
    tmp.replace(target)
    return ProfileFileActionResponse(success=True, message="保存成功", backup_file=backup_file)


def mkdir_profile_path(
    host_data_dir: Path,
    profile_name: str,
    *,
    scope: str,
    path: str,
) -> ProfileFileActionResponse:
    pp = resolve_profile_paths(host_data_dir, profile_name)
    _, target = resolve_scope_path(pp, scope, path)
    if target.exists():
        raise BadRequestError(message="路径已存在", message_key="errors.external_docker.path_exists")
    target.mkdir(parents=True, exist_ok=False)
    return ProfileFileActionResponse(success=True, message="目录已创建")


def delete_profile_path(
    host_data_dir: Path,
    profile_name: str,
    *,
    scope: str,
    path: str,
) -> ProfileFileActionResponse:
    pp = resolve_profile_paths(host_data_dir, profile_name)
    assert_not_protected_file(path)
    _, target = resolve_scope_path(pp, scope, path)
    if not target.exists():
        raise NotFoundError(message="路径不存在", message_key="errors.external_docker.path_not_found")
    backup_file = None
    if target.is_file():
        backup_file = _backup_file(pp, target)
        target.unlink()
    elif target.is_dir():
        shutil.rmtree(target)
    else:
        raise BadRequestError(message="不支持的文件类型", message_key="errors.external_docker.path_invalid")
    return ProfileFileActionResponse(success=True, message="已删除", backup_file=backup_file)
