"""External Docker Hermes lifecycle and WebUI access service."""

from __future__ import annotations

import asyncio
import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError
from app.models.instance import Instance
from app.schemas.external_docker import (
    ExternalDockerDetachResponse,
    ExternalDockerLifecycleResponse,
    ExternalDockerLogsResponse,
    ExternalDockerWebuiAccessResponse,
    ExternalDockerWebuiPasswordResponse,
)
from app.services.hermes_external._common import get_lifecycle_config, load_advanced_config, resolve_paths
from app.services.hermes_external import status_service

_PASSWORD_PATTERN = re.compile(r"^HERMES_WEBUI_PASSWORD=(.*)$", re.MULTILINE)


def _read_env_password(env_file_path) -> str | None:
    path = str(env_file_path)
    try:
        from pathlib import Path
        p = Path(path)
        if not p.is_file():
            return None
        content = p.read_text(encoding="utf-8")
    except OSError:
        return None
    match = _PASSWORD_PATTERN.search(content)
    if not match:
        return None
    value = match.group(1).strip().strip('"').strip("'")
    return value or None


async def get_webui_access(instance: Instance) -> ExternalDockerWebuiAccessResponse:
    status = await status_service.get_status(instance)
    ep = resolve_paths(instance)
    password = _read_env_password(ep.docker_env_file)
    advanced = load_advanced_config(instance)
    webui = advanced.get("webui") or {}
    return ExternalDockerWebuiAccessResponse(
        public_url=status.public_url,
        username=webui.get("username"),
        password_available=bool(password),
        password_masked="************" if password else "",
    )


async def get_webui_password(instance: Instance) -> ExternalDockerWebuiPasswordResponse:
    ep = resolve_paths(instance)
    password = _read_env_password(ep.docker_env_file)
    if not password:
        raise BadRequestError(
            message="未找到 WebUI 密码",
            message_key="errors.external_docker.webui_password_not_found",
        )
    return ExternalDockerWebuiPasswordResponse(password=password)


def _container_name(instance: Instance, lifecycle: dict) -> str:
    if lifecycle.get("container_name"):
        return str(lifecycle["container_name"])
    return resolve_paths(instance).container_name


async def _run_cmd(cmd: list[str]) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise BadRequestError(
            message=f"Docker 命令执行失败: {stderr.decode().strip()[:300]}",
            message_key="errors.external_docker.lifecycle_failed",
        )


async def start(instance: Instance) -> ExternalDockerLifecycleResponse:
    lifecycle = get_lifecycle_config(instance)
    if lifecycle.get("lifecycle_mode") == "linked_only":
        raise BadRequestError(
            message="当前实例为仅关联模式，不支持生命周期操作",
            message_key="errors.docker_attach.lifecycle_not_allowed",
        )

    use_compose = (
        lifecycle.get("lifecycle_mode") == "managed_compose"
        and lifecycle.get("compose_path")
        and lifecycle.get("env_file")
        and lifecycle.get("project_name")
    )
    if use_compose:
        cmd = [
            "docker", "compose",
            "-f", str(lifecycle["compose_path"]),
            "--env-file", str(lifecycle["env_file"]),
            "-p", str(lifecycle["project_name"]),
            "up", "-d",
        ]
    else:
        cmd = ["docker", "start", _container_name(instance, lifecycle)]

    await _run_cmd(cmd)
    return ExternalDockerLifecycleResponse(success=True, action="start", message="启动成功")


async def stop(instance: Instance) -> ExternalDockerLifecycleResponse:
    lifecycle = get_lifecycle_config(instance)
    if lifecycle.get("lifecycle_mode") == "linked_only":
        raise BadRequestError(
            message="当前实例为仅关联模式，不支持生命周期操作",
            message_key="errors.docker_attach.lifecycle_not_allowed",
        )

    use_compose = (
        lifecycle.get("lifecycle_mode") == "managed_compose"
        and lifecycle.get("compose_path")
        and lifecycle.get("env_file")
        and lifecycle.get("project_name")
    )
    if use_compose:
        cmd = [
            "docker", "compose",
            "-f", str(lifecycle["compose_path"]),
            "--env-file", str(lifecycle["env_file"]),
            "-p", str(lifecycle["project_name"]),
            "stop",
        ]
    else:
        cmd = ["docker", "stop", _container_name(instance, lifecycle)]

    await _run_cmd(cmd)
    return ExternalDockerLifecycleResponse(success=True, action="stop", message="停止成功")


async def restart(instance: Instance) -> ExternalDockerLifecycleResponse:
    lifecycle = get_lifecycle_config(instance)
    if lifecycle.get("lifecycle_mode") == "linked_only":
        raise BadRequestError(
            message="当前实例为仅关联模式，不支持生命周期操作",
            message_key="errors.docker_attach.lifecycle_not_allowed",
        )

    use_compose = (
        lifecycle.get("lifecycle_mode") == "managed_compose"
        and lifecycle.get("compose_path")
        and lifecycle.get("env_file")
        and lifecycle.get("project_name")
    )
    if use_compose:
        cmd = [
            "docker", "compose",
            "-f", str(lifecycle["compose_path"]),
            "--env-file", str(lifecycle["env_file"]),
            "-p", str(lifecycle["project_name"]),
            "restart",
        ]
    else:
        cmd = ["docker", "restart", _container_name(instance, lifecycle)]

    await _run_cmd(cmd)
    return ExternalDockerLifecycleResponse(success=True, action="restart", message="重启成功")


async def get_logs(instance: Instance, tail: int = 200) -> ExternalDockerLogsResponse:
    ep = resolve_paths(instance)
    tail = max(1, min(tail, 2000))
    proc = await asyncio.create_subprocess_exec(
        "docker", "logs", "--tail", str(tail), ep.container_name,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    logs = stdout.decode(errors="replace") if stdout else ""
    if proc.returncode != 0 and not logs:
        raise BadRequestError(
            message="读取容器日志失败",
            message_key="errors.external_docker.logs_failed",
        )
    return ExternalDockerLogsResponse(container_name=ep.container_name, logs=logs)


async def detach(instance_id: str, db: AsyncSession) -> ExternalDockerDetachResponse:
    from app.services import instance_service

    await instance_service.finalize_instance_deletion_once(instance_id, db)
    return ExternalDockerDetachResponse(success=True, instance_id=instance_id)
