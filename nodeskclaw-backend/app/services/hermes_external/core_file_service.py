"""External Docker Hermes profile core file service."""

from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml

from app.core.exceptions import BadRequestError
from app.models.instance import Instance
from app.schemas.external_docker_profiles import (
    CoreFileReadResponse,
    CoreFileSaveResponse,
    CoreFileValidateResponse,
)
from app.services.hermes_external._common import resolve_paths
from app.services.hermes_external.path_resolver import HermesExternalPathResolver

_path_resolver = HermesExternalPathResolver()

CORE_FILE_KINDS = {
    "env": ".env",
    "config": "config.yaml",
    "soul": "SOUL.md",
}

_BACKUP_PREFIX = {
    "env": "env",
    "config": "config",
    "soul": "SOUL",
}

_BACKUP_SUFFIX = {
    "env": ".bak",
    "config": ".yaml",
    "soul": ".md",
}

_ENV_KEY_PATTERN = re.compile(r"^[A-Z_][A-Z0-9_]*$")


def _normalize_kind(kind: str) -> str:
    value = (kind or "").strip().lower()
    if value not in CORE_FILE_KINDS:
        raise BadRequestError(
            message="不支持的核心文件类型",
            message_key="errors.external_docker.core_file_kind_invalid",
        )
    return value


def _resolve_host_data_dir(instance: Instance) -> Path:
    ep = resolve_paths(instance)
    _path_resolver.validate_host_data_dir(ep)
    return ep.host_data_dir


def _resolve_profile_paths(instance: Instance, profile_name: str):
    host_data_dir = _resolve_host_data_dir(instance)
    return _path_resolver.resolve_profile_from_host_data_dir(host_data_dir, profile_name)


def _resolve_profile_paths_from_host_data_dir(host_data_dir: Path, profile_name: str):
    return _path_resolver.resolve_profile_from_host_data_dir(Path(host_data_dir), profile_name)


def _file_for_kind(pp, kind: str) -> Path:
    if kind == "env":
        return pp.env_file
    if kind == "config":
        return pp.config_file
    return pp.soul_file


def _validate_env_content(text: str) -> CoreFileValidateResponse:
    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            return CoreFileValidateResponse(
                valid=False,
                message=f"第 {line_no} 行不支持 export 语法",
            )
        if "=" not in stripped:
            return CoreFileValidateResponse(
                valid=False,
                message=f"第 {line_no} 行不是有效的 KEY=VALUE 格式",
            )
        key, _, value = stripped.partition("=")
        key = key.strip()
        if not key:
            return CoreFileValidateResponse(
                valid=False,
                message=f"第 {line_no} 行 KEY 不能为空",
            )
        if key.startswith("../") or key.startswith("/"):
            return CoreFileValidateResponse(
                valid=False,
                message=f"第 {line_no} 行 KEY 格式非法：{key}",
            )
        if not _ENV_KEY_PATTERN.match(key):
            return CoreFileValidateResponse(
                valid=False,
                message=f"第 {line_no} 行 KEY 格式非法：{key}",
            )
        if value.strip().startswith("../"):
            return CoreFileValidateResponse(
                valid=False,
                message=f"第 {line_no} 行 VALUE 格式非法",
            )
    return CoreFileValidateResponse(valid=True, message="校验通过")


def validate_core_file(kind: str, content: str) -> CoreFileValidateResponse:
    normalized = _normalize_kind(kind)
    text = content or ""

    if normalized == "env":
        return _validate_env_content(text)

    if normalized == "config":
        stripped = text.strip()
        if not stripped:
            return CoreFileValidateResponse(valid=False, message="config.yaml 内容不能为空")
        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            return CoreFileValidateResponse(valid=False, message=f"YAML 格式错误：{exc}")
        if not isinstance(parsed, dict):
            return CoreFileValidateResponse(valid=False, message="config.yaml 顶层必须是 YAML 对象")
        return CoreFileValidateResponse(valid=True, message="校验通过")

    if not text.strip():
        return CoreFileValidateResponse(valid=False, message="SOUL.md 内容不能为空")
    if len(text.encode("utf-8")) > 1024 * 1024:
        return CoreFileValidateResponse(valid=False, message="SOUL.md 文件过大")
    return CoreFileValidateResponse(valid=True, message="校验通过")


def read_core_file(instance: Instance, profile_name: str, kind: str) -> CoreFileReadResponse:
    pp = _resolve_profile_paths(instance, profile_name)
    return _read_core_file_from_paths(pp, kind)


def read_core_file_for_host_data_dir(
    host_data_dir: Path,
    profile_name: str,
    kind: str,
) -> CoreFileReadResponse:
    pp = _resolve_profile_paths_from_host_data_dir(host_data_dir, profile_name)
    return _read_core_file_from_paths(pp, kind)


def _read_core_file_from_paths(pp, kind: str) -> CoreFileReadResponse:
    normalized = _normalize_kind(kind)
    target = _file_for_kind(pp, normalized)
    _path_resolver.validate_profile_path(pp.profile_dir, target)
    exists = target.is_file()
    content = target.read_text(encoding="utf-8") if exists else ""
    return CoreFileReadResponse(
        profile=pp.profile,
        kind=normalized,
        file_name=CORE_FILE_KINDS[normalized],
        file_path=str(target),
        exists=exists,
        content=content,
        requires_restart=True,
        readonly=False,
        message=None if exists else "文件尚未创建",
    )


def _backup_core_file(pp, kind: str, target: Path) -> str | None:
    if not target.is_file():
        return None
    backup_dir = pp.core_file_backup_dir
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_name = f"{_BACKUP_PREFIX[kind]}-{stamp}{_BACKUP_SUFFIX[kind]}"
    backup_file = backup_dir / backup_name
    shutil.copy2(target, backup_file)
    return str(backup_file)


async def save_core_file(
    instance: Instance,
    profile_name: str,
    kind: str,
    content: str,
    *,
    restart_after_save: bool = False,
) -> CoreFileSaveResponse:
    pp = _resolve_profile_paths(instance, profile_name)
    ep = resolve_paths(instance)
    return await _save_core_file(
        instance,
        pp,
        kind,
        content,
        restart_after_save=restart_after_save,
        container_name=ep.container_name,
        gateway_url=None,
    )


async def save_core_file_for_host_data_dir(
    host_data_dir: Path,
    profile_name: str,
    kind: str,
    content: str,
    *,
    restart_after_save: bool = False,
    container_name: str | None = None,
    gateway_url: str | None = None,
) -> CoreFileSaveResponse:
    pp = _resolve_profile_paths_from_host_data_dir(host_data_dir, profile_name)
    return await _save_core_file(
        None,
        pp,
        kind,
        content,
        restart_after_save=restart_after_save,
        container_name=container_name,
        gateway_url=gateway_url,
    )


async def _save_core_file(
    instance: Instance | None,
    pp,
    kind: str,
    content: str,
    *,
    restart_after_save: bool = False,
    container_name: str | None = None,
    gateway_url: str | None = None,
) -> CoreFileSaveResponse:
    normalized = _normalize_kind(kind)
    validation = validate_core_file(normalized, content)
    if not validation.valid:
        raise BadRequestError(
            message=validation.message,
            message_key="errors.external_docker.core_file_invalid",
        )

    target = _file_for_kind(pp, normalized)
    _path_resolver.validate_profile_path(pp.profile_dir, target)
    target.parent.mkdir(parents=True, exist_ok=True)
    backup_file = _backup_core_file(pp, normalized, target)

    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    _path_resolver.validate_profile_path(pp.profile_dir, tmp)
    tmp.replace(target)

    restarted = False
    docker_status = None
    api_server_status = None
    agent_call_status = None
    runtime_status = None
    error_code = None
    message = "保存成功"

    if restart_after_save:
        from app.services.hermes_external import lifecycle_service
        from app.services.hermes_external.runtime_recovery_service import wait_for_runtime_recovery

        if instance is not None:
            await lifecycle_service.restart(instance)
            ep = resolve_paths(instance)
            container_name = ep.container_name
            if not gateway_url and instance.advanced_config:
                import json
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
            env_file=pp.env_file,
        )
        docker_status = recovery.docker_status
        api_server_status = recovery.api_server_status
        agent_call_status = recovery.agent_call_status
        runtime_status = recovery.runtime_status
        error_code = recovery.error_code
        if recovery.recovered:
            message = "保存成功，容器已重启，Runtime 已恢复"
        else:
            message = recovery.message or "文件已保存，但 Runtime 未恢复，请进入运行状态页查看日志"

    return CoreFileSaveResponse(
        success=True,
        profile=pp.profile,
        kind=normalized,
        file_path=str(target),
        backup_file=backup_file,
        restarted=restarted,
        docker_status=docker_status,
        api_server_status=api_server_status,
        agent_call_status=agent_call_status,
        runtime_status=runtime_status,
        error_code=error_code,
        message=message,
    )
