"""External Docker instance status service."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.models.instance import Instance
from app.schemas.external_docker import ExternalDockerOverviewResponse, ExternalDockerStatusResponse
from app.services.docker_constants import get_docker_public_url
from app.services.hermes_external._common import get_lifecycle_config, load_advanced_config, resolve_paths
from app.services.hermes_external.binding_type import get_binding_type_label
from app.utils.display_status import compute_docker_display_status

logger = logging.getLogger(__name__)


def _docker_endpoint_host() -> str:
    if os.path.exists("/.dockerenv") or settings.DOCKER_DATA_DIR:
        return "host.docker.internal"
    return "localhost"


def _resolve_public_url(instance: Instance, advanced: dict, host_port: int | None = None) -> str | None:
    webui = advanced.get("webui") or {}
    public_url = webui.get("public_url")
    if public_url:
        return str(public_url)
    port = webui.get("port") or host_port
    if port:
        return get_docker_public_url(int(port))
    return None


async def _docker_inspect(container_name: str) -> tuple[str, dict | None, str | None]:
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker",
            "inspect",
            "--format",
            "{{json .}}",
            container_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            err = stderr.decode().strip()
            if "No such object" in err or "No such container" in err:
                return "missing", None, err
            return "unknown", None, err
        data = json.loads(stdout.decode().strip())
        if isinstance(data, list):
            data = data[0] if data else None
        if not data:
            return "missing", None, "container not found"
        state = data.get("State") or {}
        raw_status = str(state.get("Status") or "unknown").lower()
        status_map = {
            "running": "running",
            "exited": "exited",
            "paused": "stopped",
            "created": "stopped",
            "restarting": "restarting",
            "dead": "stopped",
        }
        return status_map.get(raw_status, raw_status), data, None
    except Exception as exc:
        logger.warning("docker inspect failed for %s", container_name, exc_info=True)
        return "unknown", None, str(exc)


async def _probe_webui_health(public_url: str | None) -> tuple[str, str | None]:
    if not public_url:
        return "unknown", "WebUI 地址未配置"
    probe_url = public_url.rstrip("/") + "/health"
    host = _docker_endpoint_host()
    if "localhost" in probe_url or "127.0.0.1" in probe_url:
        probe_url = probe_url.replace("localhost", host).replace("127.0.0.1", host)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(probe_url)
            if resp.status_code < 400:
                return "healthy", None
            return "unhealthy", f"HTTP {resp.status_code}"
    except Exception as exc:
        return "unhealthy", str(exc)


def _extract_host_port(inspect_data: dict | None) -> int | None:
    if not inspect_data:
        return None
    ports = (inspect_data.get("NetworkSettings") or {}).get("Ports") or {}
    for key, bindings in ports.items():
        if not bindings:
            continue
        binding = bindings[0] if isinstance(bindings, list) and bindings else None
        if not binding:
            continue
        host_port_raw = binding.get("HostPort")
        if host_port_raw:
            try:
                return int(host_port_raw)
            except (TypeError, ValueError):
                continue
    return None


async def get_status(instance: Instance) -> ExternalDockerStatusResponse:
    paths = resolve_paths(instance)
    advanced = load_advanced_config(instance)
    docker_status, inspect_data, inspect_error = await _docker_inspect(paths.container_name)

    docker_health = None
    started_at = None
    container_id = None
    image = None
    if inspect_data:
        state = inspect_data.get("State") or {}
        health = state.get("Health") or {}
        if health.get("Status"):
            docker_health = str(health["Status"]).lower()
        started_raw = state.get("StartedAt")
        if started_raw:
            try:
                started_at = datetime.fromisoformat(str(started_raw).replace("Z", "+00:00"))
            except ValueError:
                started_at = None
        container_id = inspect_data.get("Id")
        config = inspect_data.get("Config") or {}
        image = config.get("Image")

    host_port = _extract_host_port(inspect_data)
    public_url = _resolve_public_url(instance, advanced, host_port)

    webui_health = "unknown"
    webui_error = None
    if docker_status == "running":
        webui_health, webui_error = await _probe_webui_health(public_url)
    elif docker_status == "missing":
        webui_health = "unknown"

    health_for_display = webui_health if docker_status == "running" else "unknown"
    display_status = compute_docker_display_status(docker_status, health_for_display)

    return ExternalDockerStatusResponse(
        container_name=paths.container_name,
        container_id=container_id,
        image=image,
        docker_status=docker_status,
        docker_health=docker_health,
        webui_health=webui_health,
        display_status=display_status,
        public_url=public_url,
        started_at=started_at,
        last_checked_at=datetime.now(timezone.utc),
        last_error=inspect_error or webui_error,
    )


async def get_overview(instance: Instance) -> ExternalDockerOverviewResponse:
    paths = resolve_paths(instance)
    advanced = load_advanced_config(instance)
    lifecycle = get_lifecycle_config(instance)
    status = await get_status(instance)
    return ExternalDockerOverviewResponse(
        binding_type="external_docker",
        binding_type_label=get_binding_type_label("external_docker"),
        profile=paths.profile,
        container_name=paths.container_name,
        lifecycle_mode=lifecycle.get("lifecycle_mode") or "",
        public_url=status.public_url,
        docker_env_file=str(paths.docker_env_file),
        host_data_dir=str(paths.host_data_dir),
        container_data_dir=paths.container_data_dir,
        compose_path=lifecycle.get("compose_path"),
        compose_project=lifecycle.get("project_name"),
        service_name=lifecycle.get("service_name"),
    )
