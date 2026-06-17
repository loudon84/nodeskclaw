"""Per-profile Hermes runtime activation service."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from app.core.exceptions import BadRequestError
from app.models.instance import Instance
from app.schemas.profile_extended import ProfileActivateResponse
from app.services.hermes_external import core_file_service, profile_service
from app.services.hermes_external._common import resolve_paths
from app.services.hermes_external._profile_helpers import resolve_profile_paths
from app.services.hermes_external.path_resolver import DEFAULT_PROFILE_NAME

_CORE_FILES = (".env", "config.yaml", "SOUL.md")
_ACTIVE_MARKER = ".active_profile"


def _backup_runtime_core_files(host_data_dir: Path) -> None:
    backup_dir = host_data_dir / "backups" / "core-files" / "activate"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    for name in _CORE_FILES:
        src = host_data_dir / name
        if src.is_file():
            shutil.copy2(src, backup_dir / f"{name}-{stamp}.bak")


def _sync_core_files_to_runtime(host_data_dir: Path, source_pp) -> None:
    for name in _CORE_FILES:
        src = source_pp.profile_dir / name
        if not src.is_file():
            raise BadRequestError(
                message=f"Profile 缺少核心文件 {name}",
                message_key="errors.external_docker.profile_missing_core_file",
            )
        dst = host_data_dir / name
        shutil.copy2(src, dst)


def _validate_profile_for_activation(host_data_dir: Path, profile_name: str) -> None:
    from app.services.hermes_external.profile_service import ProfileListContext, get_profile_for_context
    ctx = ProfileListContext(host_data_dir=host_data_dir)
    item = get_profile_for_context(ctx, profile_name)
    if item.status in ("missing_files", "invalid"):
        raise BadRequestError(
            message=f"Profile {profile_name} 状态为 {item.status}，无法激活",
            message_key="errors.external_docker.profile_activate_forbidden",
        )
    pp = resolve_profile_paths(host_data_dir, profile_name)
    for kind, path in (("env", pp.env_file), ("config", pp.config_file), ("soul", pp.soul_file)):
        if not path.is_file():
            raise BadRequestError(
                message=f"Profile 缺少 {path.name}",
                message_key="errors.external_docker.profile_missing_core_file",
            )
        content = path.read_text(encoding="utf-8")
        result = core_file_service.validate_core_file(kind, content)
        if not result.valid:
            raise BadRequestError(
                message=result.message,
                message_key="errors.external_docker.core_file_invalid",
            )


async def activate_profile(
    host_data_dir: Path,
    profile_name: str,
    *,
    restart_after_activate: bool = True,
    instance: Instance | None = None,
    container_name: str | None = None,
    gateway_url: str | None = None,
) -> ProfileActivateResponse:
    host_data_dir = Path(host_data_dir)
    _validate_profile_for_activation(host_data_dir, profile_name)

    from app.services.hermes_external.profile_service import ProfileListContext, list_profiles_for_context
    ctx = ProfileListContext(host_data_dir=host_data_dir)
    before = list_profiles_for_context(ctx)
    previous_active = before.active_profile or DEFAULT_PROFILE_NAME

    pp = resolve_profile_paths(host_data_dir, profile_name)
    _backup_runtime_core_files(host_data_dir)
    if profile_name != DEFAULT_PROFILE_NAME:
        _sync_core_files_to_runtime(host_data_dir, pp)

    marker = host_data_dir / _ACTIVE_MARKER
    marker.write_text(f"{profile_name}\n", encoding="utf-8")

    restarted = False
    runtime_status = None
    api_server_status = None
    message = "Profile 已设为运行"

    if restart_after_activate:
        from app.services.hermes_external import lifecycle_service
        from app.services.hermes_external.runtime_recovery_service import wait_for_runtime_recovery

        if instance is not None:
            await lifecycle_service.restart(instance)
            ep = resolve_paths(instance)
            container_name = ep.container_name
            if not gateway_url and instance.advanced_config:
                try:
                    cfg = json.loads(instance.advanced_config) if isinstance(instance.advanced_config, str) else instance.advanced_config
                    webui = cfg.get("webui") or {}
                    from app.services.docker_constants import get_docker_public_url
                    if webui.get("port"):
                        gateway_url = get_docker_public_url(int(webui["port"]))
                except (json.JSONDecodeError, TypeError, ValueError):
                    pass
        elif container_name:
            await lifecycle_service.restart_container(container_name)

        restarted = True
        recovery = await wait_for_runtime_recovery(
            container_name=container_name or "",
            gateway_url=gateway_url,
            env_file=host_data_dir / ".env",
        )
        runtime_status = recovery.runtime_status
        api_server_status = recovery.api_server_status
        if recovery.recovered:
            message = "Profile 已设为运行，Runtime 已恢复"
        else:
            message = recovery.message or "Profile 已设为运行，但 Runtime 未恢复"

    return ProfileActivateResponse(
        success=True,
        active_profile=profile_name,
        previous_active_profile=previous_active,
        restarted=restarted,
        runtime_status=runtime_status,
        api_server_status=api_server_status,
        message=message,
    )


async def activate_profile_for_instance(
    instance: Instance,
    profile_name: str,
    *,
    restart_after_activate: bool = True,
) -> ProfileActivateResponse:
    ep = resolve_paths(instance)
    return await activate_profile(
        ep.host_data_dir,
        profile_name,
        restart_after_activate=restart_after_activate,
        instance=instance,
    )
