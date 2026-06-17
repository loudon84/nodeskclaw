"""External Docker Hermes profile management service."""

from __future__ import annotations

import shutil
import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
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
from app.services.hermes_external.hermes_env_parser import parse_env_file
from app.services.hermes_external.path_resolver import (
    DEFAULT_PROFILE_NAME,
    HermesExternalPathResolver,
    validate_profile_name,
)

_path_resolver = HermesExternalPathResolver()
_CORE_FILES = (".env", "config.yaml", "SOUL.md")
_CORE_DIRS = ("skills", "workspace")


@dataclass
class ProfileListContext:
    host_data_dir: Path
    instance_dir: Path | None = None
    agent_profile_name: str | None = None


def _read_env_model_name(env_path: Path) -> str | None:
    if not env_path.is_file():
        return None
    try:
        env = parse_env_file(env_path, require_gateway_port=False)
    except BadRequestError:
        return None
    return env.api_server_model_name


def _detect_active_profile(ctx: ProfileListContext) -> tuple[str, str | None]:
    runtime_env = ctx.host_data_dir / ".env"
    runtime_model_name = _read_env_model_name(runtime_env)

    instance_dir = ctx.instance_dir or ctx.host_data_dir.parent.parent
    root_env = instance_dir / ".env"
    if not runtime_model_name and root_env.is_file():
        runtime_model_name = _read_env_model_name(root_env)

    active_profile = DEFAULT_PROFILE_NAME
    active_marker = ctx.host_data_dir / ".active_profile"
    if active_marker.is_file():
        try:
            marker_value = active_marker.read_text(encoding="utf-8").strip()
            if marker_value:
                try:
                    active_profile = validate_profile_name(marker_value)
                except BadRequestError:
                    pass
        except OSError:
            pass
    elif runtime_env.is_file():
        try:
            raw = runtime_env.read_text(encoding="utf-8")
            for line in raw.splitlines():
                line = line.strip()
                if line.startswith("HERMES_PROFILE="):
                    value = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if value == DEFAULT_PROFILE_NAME or not value:
                        active_profile = DEFAULT_PROFILE_NAME
                    elif value:
                        try:
                            active_profile = validate_profile_name(value)
                        except BadRequestError:
                            pass
                    break
        except OSError:
            pass

    if active_profile == DEFAULT_PROFILE_NAME and ctx.agent_profile_name and runtime_model_name == ctx.agent_profile_name:
        active_profile = DEFAULT_PROFILE_NAME

    return active_profile, runtime_model_name


def _profile_status(
    profile_name: str,
    *,
    active_profile: str,
    env_exists: bool,
    config_exists: bool,
    soul_exists: bool,
    is_invalid: bool = False,
) -> str:
    if is_invalid:
        return "invalid"
    if not (env_exists and config_exists and soul_exists):
        return "missing_files"
    if profile_name == active_profile:
        return "active_runtime"
    return "config_only"


def _build_profile_item(
    pp,
    *,
    active_profile: str,
    runtime_model_name: str | None,
    is_invalid: bool = False,
) -> ProfileListItem:
    env_exists = pp.env_file.is_file()
    config_exists = pp.config_file.is_file()
    soul_exists = pp.soul_file.is_file()
    status = _profile_status(
        pp.profile,
        active_profile=active_profile,
        env_exists=env_exists,
        config_exists=config_exists,
        soul_exists=soul_exists,
        is_invalid=is_invalid,
    )
    item_runtime_model = runtime_model_name if pp.profile == active_profile else None
    return ProfileListItem(
        profile=pp.profile,
        profile_type=pp.profile_type,
        profile_dir=str(pp.profile_dir),
        env_exists=env_exists,
        config_exists=config_exists,
        soul_exists=soul_exists,
        status=status,
        runtime_model_name=item_runtime_model,
    )


def _resolve_host_data_dir(instance: Instance) -> Path:
    ep = resolve_paths(instance)
    _path_resolver.validate_host_data_dir(ep)
    return ep.host_data_dir


def _instance_dir(instance: Instance) -> Path | None:
    ep = resolve_paths(instance)
    return ep.docker_env_file.parent if ep.docker_env_file else None


def list_profiles(instance: Instance) -> ProfileListResponse:
    host_data_dir = _resolve_host_data_dir(instance)
    ctx = ProfileListContext(
        host_data_dir=host_data_dir,
        instance_dir=_instance_dir(instance),
        agent_profile_name=resolve_paths(instance).profile,
    )
    return list_profiles_for_context(ctx)


def list_profiles_for_host_data_dir(
    host_data_dir: Path,
    *,
    instance_dir: Path | None = None,
    agent_profile_name: str | None = None,
) -> ProfileListResponse:
    ctx = ProfileListContext(
        host_data_dir=Path(host_data_dir),
        instance_dir=instance_dir,
        agent_profile_name=agent_profile_name,
    )
    return list_profiles_for_context(ctx)


def list_profiles_for_context(ctx: ProfileListContext) -> ProfileListResponse:
    host_data_dir = Path(ctx.host_data_dir)
    active_profile, runtime_model_name = _detect_active_profile(ctx)
    items: list[ProfileListItem] = []

    default_paths = _path_resolver.resolve_profile_from_host_data_dir(host_data_dir, DEFAULT_PROFILE_NAME)
    items.append(_build_profile_item(
        default_paths,
        active_profile=active_profile,
        runtime_model_name=runtime_model_name,
    ))

    profiles_dir = host_data_dir / "profiles"
    if profiles_dir.is_dir():
        for entry in sorted(profiles_dir.iterdir()):
            if not entry.is_dir() and not entry.is_symlink():
                continue
            is_invalid = False
            if entry.is_symlink():
                is_invalid = True
            else:
                try:
                    validate_profile_name(entry.name)
                except BadRequestError:
                    is_invalid = True
            if is_invalid:
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
            try:
                _path_resolver.ensure_profile_dir_safe(entry, host_data_dir)
                pp = _path_resolver.resolve_profile_from_host_data_dir(host_data_dir, entry.name)
            except BadRequestError:
                items.append(ProfileListItem(
                    profile=entry.name,
                    profile_type="extended",
                    profile_dir=str(entry),
                    env_exists=False,
                    config_exists=False,
                    soul_exists=False,
                    status="invalid",
                ))
                continue
            items.append(_build_profile_item(
                pp,
                active_profile=active_profile,
                runtime_model_name=runtime_model_name,
            ))

    return ProfileListResponse(
        items=items,
        active_profile=active_profile,
        runtime_model_name=runtime_model_name,
    )


def get_profile(instance: Instance, profile_name: str) -> ProfileListItem:
    host_data_dir = _resolve_host_data_dir(instance)
    ctx = ProfileListContext(
        host_data_dir=host_data_dir,
        instance_dir=_instance_dir(instance),
        agent_profile_name=resolve_paths(instance).profile,
    )
    return get_profile_for_context(ctx, profile_name)


def get_profile_for_host_data_dir(
    host_data_dir: Path,
    profile_name: str,
    *,
    instance_dir: Path | None = None,
    agent_profile_name: str | None = None,
) -> ProfileListItem:
    ctx = ProfileListContext(
        host_data_dir=Path(host_data_dir),
        instance_dir=instance_dir,
        agent_profile_name=agent_profile_name,
    )
    return get_profile_for_context(ctx, profile_name)


def get_profile_for_context(ctx: ProfileListContext, profile_name: str) -> ProfileListItem:
    profile = validate_profile_name(profile_name)
    host_data_dir = Path(ctx.host_data_dir)
    active_profile, runtime_model_name = _detect_active_profile(ctx)
    pp = _path_resolver.resolve_profile_from_host_data_dir(host_data_dir, profile)
    if profile != DEFAULT_PROFILE_NAME and not pp.profile_dir.is_dir():
        raise NotFoundError(
            message=f"Profile {profile} 不存在",
            message_key="errors.external_docker.profile_not_found",
        )
    return _build_profile_item(
        pp,
        active_profile=active_profile,
        runtime_model_name=runtime_model_name,
    )


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


def _backup_profile_dir(pp) -> str | None:
    if not pp.profile_dir.is_dir():
        return None
    backup_dir = pp.backups_dir / "delete-backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_file = backup_dir / f"profile-{pp.profile}-{stamp}.tar.gz"
    with tarfile.open(backup_file, "w:gz") as tar:
        tar.add(pp.profile_dir, arcname=pp.profile)
    return str(backup_file)


def delete_profile(
    instance: Instance,
    profile_name: str,
    *,
    confirm_profile: str | None = None,
) -> ProfileDeleteResponse:
    host_data_dir = _resolve_host_data_dir(instance)
    ctx = ProfileListContext(
        host_data_dir=host_data_dir,
        instance_dir=_instance_dir(instance),
        agent_profile_name=resolve_paths(instance).profile,
    )
    return delete_profile_for_context(ctx, profile_name, confirm_profile=confirm_profile)


def delete_profile_for_host_data_dir(
    host_data_dir: Path,
    profile_name: str,
    *,
    confirm_profile: str | None = None,
    instance_dir: Path | None = None,
    agent_profile_name: str | None = None,
) -> ProfileDeleteResponse:
    ctx = ProfileListContext(
        host_data_dir=Path(host_data_dir),
        instance_dir=instance_dir,
        agent_profile_name=agent_profile_name,
    )
    return delete_profile_for_context(ctx, profile_name, confirm_profile=confirm_profile)


def delete_profile_for_context(
    ctx: ProfileListContext,
    profile_name: str,
    *,
    confirm_profile: str | None = None,
) -> ProfileDeleteResponse:
    profile = validate_profile_name(profile_name)
    if profile == DEFAULT_PROFILE_NAME:
        raise BadRequestError(
            message="不能删除 default profile",
            message_key="errors.external_docker.profile_delete_forbidden",
        )

    if confirm_profile is not None and confirm_profile != profile:
        raise BadRequestError(
            message="确认名称不匹配，已取消删除",
            message_key="errors.external_docker.profile_delete_confirm_mismatch",
        )

    host_data_dir = Path(ctx.host_data_dir)
    item = get_profile_for_context(ctx, profile)
    if item.status == "active_runtime":
        raise BadRequestError(
            message="不能删除当前运行 Profile",
            message_key="errors.external_docker.profile_delete_active_forbidden",
        )

    pp = _path_resolver.resolve_profile_from_host_data_dir(host_data_dir, profile)
    if not pp.profile_dir.is_dir():
        raise NotFoundError(
            message=f"Profile {profile} 不存在",
            message_key="errors.external_docker.profile_not_found",
        )

    backup_file = _backup_profile_dir(pp)
    shutil.rmtree(pp.profile_dir)
    return ProfileDeleteResponse(
        success=True,
        profile=profile,
        message="Profile 已删除",
        backup_file=backup_file,
    )
