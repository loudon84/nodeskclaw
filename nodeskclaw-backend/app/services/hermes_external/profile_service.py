"""External Docker Hermes profile management service."""

from __future__ import annotations

import shutil
from pathlib import Path

from app.core.exceptions import BadRequestError, NotFoundError
from app.models.instance import Instance
from app.schemas.external_docker_profiles import (
    ProfileCreateResponse,
    ProfileDeleteResponse,
    ProfileListItem,
    ProfileListResponse,
)
from app.services.hermes_external._common import resolve_paths
from app.services.hermes_external.path_resolver import (
    DEFAULT_PROFILE_NAME,
    HermesExternalPathResolver,
    validate_profile_name,
)

_path_resolver = HermesExternalPathResolver()
_CORE_FILES = (".env", "config.yaml", "SOUL.md")
_CORE_DIRS = ("skills", "workspace")


def _profile_status(env_exists: bool, config_exists: bool, soul_exists: bool) -> str:
    if env_exists and config_exists and soul_exists:
        return "config_only"
    return "missing_files"


def _build_profile_item(pp) -> ProfileListItem:
    env_exists = pp.env_file.is_file()
    config_exists = pp.config_file.is_file()
    soul_exists = pp.soul_file.is_file()
    return ProfileListItem(
        profile=pp.profile,
        profile_type=pp.profile_type,
        profile_dir=str(pp.profile_dir),
        env_exists=env_exists,
        config_exists=config_exists,
        soul_exists=soul_exists,
        status=_profile_status(env_exists, config_exists, soul_exists),
    )


def _resolve_host_data_dir(instance: Instance) -> Path:
    ep = resolve_paths(instance)
    _path_resolver.validate_host_data_dir(ep)
    return ep.host_data_dir


def list_profiles(instance: Instance) -> ProfileListResponse:
    host_data_dir = _resolve_host_data_dir(instance)
    return list_profiles_for_host_data_dir(host_data_dir)


def list_profiles_for_host_data_dir(host_data_dir: Path) -> ProfileListResponse:
    host_data_dir = Path(host_data_dir)
    items: list[ProfileListItem] = []

    default_paths = _path_resolver.resolve_profile_from_host_data_dir(host_data_dir, DEFAULT_PROFILE_NAME)
    items.append(_build_profile_item(default_paths))

    profiles_dir = host_data_dir / "profiles"
    if profiles_dir.is_dir():
        for entry in sorted(profiles_dir.iterdir()):
            if not entry.is_dir():
                continue
            try:
                validate_profile_name(entry.name)
            except BadRequestError:
                items.append(ProfileListItem(
                    profile=entry.name,
                    profile_type="extended",
                    profile_dir=str(entry),
                    env_exists=(entry / ".env").is_file(),
                    config_exists=(entry / "config.yaml").is_file(),
                    soul_exists=(entry / "SOUL.md").is_file(),
                    status="invalid",
                ))
                continue
            pp = _path_resolver.resolve_profile_from_host_data_dir(host_data_dir, entry.name)
            items.append(_build_profile_item(pp))

    return ProfileListResponse(items=items)


def get_profile(instance: Instance, profile_name: str) -> ProfileListItem:
    host_data_dir = _resolve_host_data_dir(instance)
    return get_profile_for_host_data_dir(host_data_dir, profile_name)


def get_profile_for_host_data_dir(host_data_dir: Path, profile_name: str) -> ProfileListItem:
    profile = validate_profile_name(profile_name)
    host_data_dir = Path(host_data_dir)
    pp = _path_resolver.resolve_profile_from_host_data_dir(host_data_dir, profile)
    if profile != DEFAULT_PROFILE_NAME:
        if not pp.profile_dir.is_dir():
            raise NotFoundError(
                message=f"Profile {profile} 不存在",
                message_key="errors.external_docker.profile_not_found",
            )
    return _build_profile_item(pp)


def create_profile(
    instance: Instance,
    profile_name: str,
    *,
    from_profile: str | None = None,
) -> ProfileCreateResponse:
    host_data_dir = _resolve_host_data_dir(instance)
    return create_profile_for_host_data_dir(host_data_dir, profile_name, from_profile=from_profile)


def create_profile_for_host_data_dir(
    host_data_dir: Path,
    profile_name: str,
    *,
    from_profile: str | None = None,
) -> ProfileCreateResponse:
    profile = validate_profile_name(profile_name)
    if profile == DEFAULT_PROFILE_NAME:
        raise BadRequestError(
            message="default profile 已存在，不能重复创建",
            message_key="errors.external_docker.profile_create_failed",
        )

    host_data_dir = Path(host_data_dir)
    target = _path_resolver.resolve_profile_from_host_data_dir(host_data_dir, profile)
    if target.profile_dir.exists():
        raise BadRequestError(
            message=f"Profile {profile} 已存在",
            message_key="errors.external_docker.profile_already_exists",
        )

    source_name = from_profile or DEFAULT_PROFILE_NAME
    source = _path_resolver.resolve_profile_from_host_data_dir(host_data_dir, source_name)
    if source_name != DEFAULT_PROFILE_NAME and not source.profile_dir.is_dir():
        raise NotFoundError(
            message=f"源 Profile {source_name} 不存在",
            message_key="errors.external_docker.profile_not_found",
        )

    target.profile_dir.mkdir(parents=True, exist_ok=True)
    for name in _CORE_FILES:
        src = source.profile_dir / name
        if src.is_file():
            shutil.copy2(src, target.profile_dir / name)
    for name in _CORE_DIRS:
        src = source.profile_dir / name
        if src.is_dir():
            shutil.copytree(src, target.profile_dir / name, dirs_exist_ok=True)

    return ProfileCreateResponse(
        success=True,
        profile=profile,
        profile_dir=str(target.profile_dir),
        message="Profile 创建成功",
    )


def delete_profile(instance: Instance, profile_name: str) -> ProfileDeleteResponse:
    host_data_dir = _resolve_host_data_dir(instance)
    return delete_profile_for_host_data_dir(host_data_dir, profile_name)


def delete_profile_for_host_data_dir(host_data_dir: Path, profile_name: str) -> ProfileDeleteResponse:
    profile = validate_profile_name(profile_name)
    if profile == DEFAULT_PROFILE_NAME:
        raise BadRequestError(
            message="不能删除 default profile",
            message_key="errors.external_docker.profile_delete_forbidden",
        )

    host_data_dir = Path(host_data_dir)
    pp = _path_resolver.resolve_profile_from_host_data_dir(host_data_dir, profile)
    if not pp.profile_dir.is_dir():
        raise NotFoundError(
            message=f"Profile {profile} 不存在",
            message_key="errors.external_docker.profile_not_found",
        )

    shutil.rmtree(pp.profile_dir)
    return ProfileDeleteResponse(
        success=True,
        profile=profile,
        message="Profile 已删除",
    )
