"""Shared helpers for per-profile Hermes services."""

from __future__ import annotations

from pathlib import Path

from app.core.exceptions import BadRequestError
from app.models.instance import Instance
from app.services.hermes_external._common import resolve_paths
from app.services.hermes_external.path_resolver import (
    HermesExternalPathResolver,
    HermesProfilePaths,
    validate_profile_name,
)

_path_resolver = HermesExternalPathResolver()
_PROTECTED_FILE_NAMES = {".env", "config.yaml", "SOUL.md"}
_MAX_TEXT_BYTES = 1024 * 1024


def resolve_profile_paths(host_data_dir: Path, profile_name: str) -> HermesProfilePaths:
    return _path_resolver.resolve_profile_from_host_data_dir(Path(host_data_dir), profile_name)


def resolve_profile_paths_for_instance(instance: Instance, profile_name: str) -> HermesProfilePaths:
    ep = resolve_paths(instance)
    _path_resolver.validate_host_data_dir(ep)
    return _path_resolver.resolve_profile(instance, profile_name)


def profile_backup_root(pp: HermesProfilePaths, host_data_dir: Path) -> Path:
    if pp.profile_type == "default":
        root = host_data_dir / "backups" / "profiles" / pp.profile
    else:
        root = pp.profile_dir / "backups"
    root.mkdir(parents=True, exist_ok=True)
    return root


def profile_export_root(host_data_dir: Path) -> Path:
    root = host_data_dir / "backups" / "exports"
    root.mkdir(parents=True, exist_ok=True)
    return root


def assert_not_protected_file(rel_path: str) -> None:
    name = Path(rel_path).name
    if name in _PROTECTED_FILE_NAMES:
        raise BadRequestError(
            message="核心配置文件请通过模型配置 API 修改",
            message_key="errors.external_docker.profile_file_protected",
        )


def resolve_scope_path(pp: HermesProfilePaths, scope: str, sub_path: str) -> tuple[Path, Path]:
    scope = (scope or "workspace").strip().lower()
    if scope == "workspace":
        allowed_root = pp.workspace_dir
    elif scope == "system":
        allowed_root = pp.profile_dir
    else:
        raise BadRequestError(
            message="不支持的文件 scope",
            message_key="errors.external_docker.invalid_file_scope",
        )
    allowed_root.mkdir(parents=True, exist_ok=True)
    normalized = (sub_path or "").strip().replace("\\", "/").strip("/")
    target = allowed_root if not normalized else (allowed_root / normalized)
    _path_resolver.validate_profile_path(pp.profile_dir, target)
    return allowed_root, target


def validate_profile_name_or_raise(name: str) -> str:
    return validate_profile_name(name)
