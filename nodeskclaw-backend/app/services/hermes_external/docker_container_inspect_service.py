from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

from app.core.config import settings
from app.core.exceptions import BadRequestError

logger = logging.getLogger(__name__)

DOCKER_STATUS_MAP = {
    "running": "running",
    "exited": "exited",
    "paused": "paused",
    "created": "created",
    "restarting": "restarting",
    "dead": "exited",
}


@dataclass
class DockerInspectResult:
    docker_status: str
    docker_health: str
    container_id: str | None
    image: str | None
    inspect_data: dict | None
    gateway_port_mapped: bool
    webui_port_mapped: bool
    last_error: str | None = None


class DockerContainerInspectService:
    async def inspect(self, container_name: str, *, gateway_port: int | None, webui_port: int | None) -> DockerInspectResult:
        docker_status, inspect_data, err = await self._docker_inspect(container_name)
        if docker_status == "missing" or not inspect_data:
            return DockerInspectResult(
                docker_status="missing",
                docker_health="unknown",
                container_id=None,
                image=None,
                inspect_data=None,
                gateway_port_mapped=False,
                webui_port_mapped=False,
                last_error=err or "container not found",
            )

        state = inspect_data.get("State") or {}
        health_raw = (state.get("Health") or {}).get("Status")
        docker_health = str(health_raw).lower() if health_raw else "none"
        config = inspect_data.get("Config") or {}
        internal_port = settings.HERMES_DEFAULT_GATEWAY_INTERNAL_PORT
        gateway_mapped = self._has_port_mapping(inspect_data, gateway_port, internal_port) if gateway_port else False
        webui_mapped = self._has_any_host_mapping(inspect_data, webui_port) if webui_port else False

        if gateway_port and not gateway_mapped:
            return DockerInspectResult(
                docker_status=docker_status,
                docker_health=docker_health,
                container_id=inspect_data.get("Id"),
                image=config.get("Image"),
                inspect_data=inspect_data,
                gateway_port_mapped=False,
                webui_port_mapped=webui_mapped,
                last_error=(
                    f"HERMES_GATEWAY_PORT 未映射到容器内部 {internal_port}，"
                    "请检查 docker-compose ports 配置。"
                ),
            )

        return DockerInspectResult(
            docker_status=docker_status,
            docker_health=docker_health,
            container_id=inspect_data.get("Id"),
            image=config.get("Image"),
            inspect_data=inspect_data,
            gateway_port_mapped=gateway_mapped,
            webui_port_mapped=webui_mapped,
            last_error=err,
        )

    async def _docker_inspect(self, container_name: str) -> tuple[str, dict | None, str | None]:
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
            raw_status = str((data.get("State") or {}).get("Status") or "unknown").lower()
            return DOCKER_STATUS_MAP.get(raw_status, raw_status), data, None
        except Exception as exc:
            logger.warning("docker inspect failed for %s", container_name, exc_info=True)
            return "unknown", None, str(exc)

    def _has_port_mapping(self, inspect_data: dict, host_port: int, container_port: int) -> bool:
        ports = (inspect_data.get("NetworkSettings") or {}).get("Ports") or {}
        key = f"{container_port}/tcp"
        bindings = ports.get(key)
        if not bindings:
            return False
        for binding in bindings:
            if not binding:
                continue
            try:
                if int(binding.get("HostPort") or 0) == host_port:
                    return True
            except (TypeError, ValueError):
                continue
        return False

    def _has_any_host_mapping(self, inspect_data: dict, host_port: int) -> bool:
        ports = (inspect_data.get("NetworkSettings") or {}).get("Ports") or {}
        for bindings in ports.values():
            if not bindings:
                continue
            for binding in bindings:
                if not binding:
                    continue
                try:
                    if int(binding.get("HostPort") or 0) == host_port:
                        return True
                except (TypeError, ValueError):
                    continue
        return False


def raise_if_container_not_found(result: DockerInspectResult) -> None:
    if result.docker_status == "missing":
        raise BadRequestError(
            f"未找到容器 {result.inspect_data}，请检查容器名称或 .env 中的 CONTAINER_NAME。",
            "errors.hermes.container_not_found",
        )
