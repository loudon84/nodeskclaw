"""Docker container health collector for Hermes Insight."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from app.services.hermes_external.docker_container_inspect_service import DockerContainerInspectService
from app.services.hermes_external.insight.usage_collector import InsightWarning

logger = logging.getLogger(__name__)


@dataclass
class ContainerRuntimeInfo:
    container_name: str
    docker_status: str = "unknown"
    health: str = "unknown"
    cpu_percent: float | None = None
    memory_used_bytes: int | None = None
    memory_limit_bytes: int | None = None
    memory_percent: float | None = None
    disk_used_bytes: int | None = None
    disk_total_bytes: int | None = None
    disk_percent: float | None = None
    ports: list[str] = field(default_factory=list)
    last_probe_at: str | None = None
    warnings: list[InsightWarning] = field(default_factory=list)


class ContainerHealthCollector:
    def __init__(self) -> None:
        self._inspect_service = DockerContainerInspectService()

    async def collect(
        self,
        *,
        container_name: str,
        host_data_dir: Path,
        gateway_port: int | None = None,
        webui_port: int | None = None,
    ) -> ContainerRuntimeInfo:
        info = ContainerRuntimeInfo(
            container_name=container_name,
            last_probe_at=datetime.now(UTC).isoformat(),
        )
        inspect = await self._inspect_service.inspect(
            container_name,
            gateway_port=gateway_port,
            webui_port=webui_port,
        )
        info.docker_status = inspect.docker_status
        info.health = inspect.docker_health
        if inspect.inspect_data:
            info.ports = _extract_ports(inspect.inspect_data)

        stats_warning = await self._apply_docker_stats(info, container_name)
        if stats_warning:
            info.warnings.append(stats_warning)

        disk_warning = self._apply_disk_usage(info, host_data_dir)
        if disk_warning:
            info.warnings.append(disk_warning)

        if inspect.last_error and inspect.docker_status == "missing":
            info.warnings.append(
                InsightWarning(
                    code="CONTAINER_NOT_FOUND",
                    message=inspect.last_error,
                )
            )
        return info

    async def _apply_docker_stats(
        self,
        info: ContainerRuntimeInfo,
        container_name: str,
    ) -> InsightWarning | None:
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "stats",
                "--no-stream",
                "--format",
                "{{json .}}",
                container_name,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if proc.returncode != 0:
                return InsightWarning(
                    code="DOCKER_STATS_UNAVAILABLE",
                    message=stderr.decode().strip() or "docker stats unavailable",
                )
            raw = stdout.decode().strip()
            if not raw:
                return InsightWarning(code="DOCKER_STATS_UNAVAILABLE", message="docker stats returned empty")
            data = json.loads(raw)
            if isinstance(data, list):
                data = data[0] if data else {}
            info.cpu_percent = _parse_cpu_percent(data.get("CPUPerc"))
            mem_used, mem_limit = _parse_memory(data.get("MemUsage"))
            info.memory_used_bytes = mem_used
            info.memory_limit_bytes = mem_limit
            if mem_used is not None and mem_limit:
                info.memory_percent = round(mem_used / mem_limit * 100, 1)
        except Exception as exc:
            logger.warning("docker stats failed for %s: %s", container_name, exc)
            return InsightWarning(code="DOCKER_STATS_UNAVAILABLE", message=str(exc))
        return None

    def _apply_disk_usage(self, info: ContainerRuntimeInfo, host_data_dir: Path) -> InsightWarning | None:
        try:
            if host_data_dir.is_dir():
                info.disk_used_bytes = _dir_size_bytes(host_data_dir)
            usage = shutil.disk_usage(host_data_dir if host_data_dir.exists() else Path("/"))
            info.disk_total_bytes = usage.total
            if info.disk_used_bytes is not None and usage.total:
                info.disk_percent = round(info.disk_used_bytes / usage.total * 100, 1)
        except Exception as exc:
            logger.warning("disk usage failed for %s: %s", host_data_dir, exc)
            return InsightWarning(code="DISK_USAGE_UNAVAILABLE", message=str(exc))
        return None


def _extract_ports(inspect_data: dict) -> list[str]:
    ports: list[str] = []
    bindings = (inspect_data.get("NetworkSettings") or {}).get("Ports") or {}
    for container_port, host_bindings in bindings.items():
        if not host_bindings:
            continue
        for binding in host_bindings:
            if not binding:
                continue
            host_port = binding.get("HostPort")
            if host_port:
                ports.append(f"{host_port}->{container_port}")
    return sorted(ports)


def _parse_cpu_percent(value: str | None) -> float | None:
    if not value:
        return None
    text = str(value).strip().rstrip("%")
    try:
        return round(float(text), 1)
    except ValueError:
        return None


def _parse_memory(value: str | None) -> tuple[int | None, int | None]:
    if not value or "/" not in value:
        return None, None
    used_raw, limit_raw = value.split("/", 1)
    return _parse_size_bytes(used_raw.strip()), _parse_size_bytes(limit_raw.strip())


def _parse_size_bytes(text: str) -> int | None:
    text = text.strip().upper()
    units = {
        "B": 1,
        "KIB": 1024,
        "MIB": 1024**2,
        "GIB": 1024**3,
        "KB": 1000,
        "MB": 1000**2,
        "GB": 1000**3,
    }
    for suffix, factor in units.items():
        if text.endswith(suffix):
            try:
                return int(float(text[: -len(suffix)].strip()) * factor)
            except ValueError:
                return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _dir_size_bytes(path: Path) -> int:
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                continue
    return total
