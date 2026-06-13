"""Resolve Docker Hermes instance layout from container inspect data."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from app.services.docker_constants import (
    DOCKER_DATA_DIR,
    get_docker_attach_scan_dirs,
    get_docker_compose_file_fallback,
    get_docker_public_host,
    get_docker_public_scheme,
    get_docker_public_url,
)

DEFAULT_CONTAINER_DATA_DIR = "/data/hermes"
DEFAULT_CONTAINER_PORT = 8787



def _docker_endpoint_host() -> str:
    if os.path.exists("/.dockerenv") or os.environ.get("DOCKER_DATA_DIR"):
        return "host.docker.internal"
    return "localhost"


@dataclass
class DockerInstanceLayout:
    profile: str
    container_name: str
    instance_root: str
    host_data_dir: str
    container_data_dir: str
    env_file: str
    compose_path: str | None
    project_name: str
    service_name: str | None
    host_port: int | None
    container_port: int
    public_url: str | None
    health_url: str | None
    lifecycle_mode: str
    paths: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def attachable(self) -> bool:
        return bool(self.host_data_dir)


def _profile_from_container_name(container_name: str) -> str:
    if container_name.startswith("hermes-"):
        return container_name.removeprefix("hermes-")
    return container_name


def _host_data_dir_from_mounts(inspect_data: dict) -> str | None:
    mounts = inspect_data.get("Mounts") or []
    for mount in mounts:
        if not isinstance(mount, dict):
            continue
        destination = str(mount.get("Destination") or "")
        source = str(mount.get("Source") or "")
        if destination in {DEFAULT_CONTAINER_DATA_DIR, "/root/.hermes"} and source:
            return source
    return None


def _instance_root_from_host_data_dir(host_data_dir: str) -> str:
    p = Path(host_data_dir)
    if p.name == "hermes" and p.parent.name == "data":
        return str(p.parent.parent)
    return str(p)


def _parse_ports(inspect_data: dict) -> tuple[int | None, int]:
    ports = (inspect_data.get("NetworkSettings") or {}).get("Ports") or {}
    preferred_key = f"{DEFAULT_CONTAINER_PORT}/tcp"
    if preferred_key in ports and ports[preferred_key]:
        binding = ports[preferred_key][0]
        host_port_raw = binding.get("HostPort")
        if host_port_raw:
            try:
                return int(host_port_raw), DEFAULT_CONTAINER_PORT
            except (TypeError, ValueError):
                pass

    for key, bindings in ports.items():
        if not bindings:
            continue
        binding = bindings[0] if isinstance(bindings, list) and bindings else None
        if not binding:
            continue
        host_port_raw = binding.get("HostPort")
        if not host_port_raw:
            continue
        container_port_raw = key.split("/")[0]
        try:
            return int(host_port_raw), int(container_port_raw)
        except (TypeError, ValueError):
            continue
    return None, DEFAULT_CONTAINER_PORT


def _read_env_port(env_file: str) -> int | None:
    path = Path(env_file)
    if not path.is_file():
        return None
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() == "HERMES_WEBUI_PORT":
                try:
                    return int(value.strip().strip('"').strip("'"))
                except ValueError:
                    return None
    except OSError:
        return None
    return None


def _compose_path_from_labels(labels: dict) -> str | None:
    config_files = labels.get("com.docker.compose.project.config_files")
    if config_files:
        first = config_files.split(",")[0].strip()
        if first:
            return first

    working_dir = labels.get("com.docker.compose.project.working_dir")
    if working_dir:
        candidate = Path(working_dir) / "docker-compose.yml"
        if candidate.exists():
            return str(candidate)
    return None


def _build_paths(host_data_dir: str) -> dict[str, str]:
    root = Path(host_data_dir)
    return {
        "instance_root": _instance_root_from_host_data_dir(host_data_dir),
        "host_data_dir": host_data_dir,
        "container_data_dir": DEFAULT_CONTAINER_DATA_DIR,
        "workspace_dir": str(root / "workspace"),
        "attachments_dir": str(root / "attachments"),
        "skills_dir": str(root / "skills"),
        "skill_inbox_dir": str(root / "skill-inbox"),
        "tools_dir": str(root / "tools"),
        "plugins_dir": str(root / "plugins"),
        "logs_dir": str(root / "logs"),
        "sessions_dir": str(root / "sessions"),
        "webui_dir": str(root / "webui"),
    }


def _resolve_lifecycle_mode(
    compose_path: str | None,
    env_file: str,
    requested: str | None = None,
) -> tuple[str, list[str]]:
    warnings: list[str] = []
    env_exists = Path(env_file).is_file()
    compose_exists = bool(compose_path and Path(compose_path).is_file())

    if requested == "linked_only":
        return "linked_only", warnings

    if compose_exists and env_exists:
        return requested or "managed_compose", warnings

    if not compose_exists:
        warnings.append("compose_path missing")
    if not env_exists:
        warnings.append("env_file missing")

    if requested == "managed_compose":
        warnings.append("未找到实例 .env 文件或 compose 文件，生命周期管理将降级为 managed_container")
        return "managed_container", warnings

    return requested or "managed_container", warnings


def resolve_from_inspect(
    inspect_data: dict,
    *,
    scan_entry: Path | None = None,
    lifecycle_mode: str | None = None,
) -> DockerInstanceLayout:
    container_name = str(
        inspect_data.get("Name", "").lstrip("/")
        or (inspect_data.get("Config") or {}).get("Hostname")
        or ""
    )
    profile = _profile_from_container_name(container_name)
    labels = (inspect_data.get("Config") or {}).get("Labels") or {}

    warnings: list[str] = []
    host_data_dir = _host_data_dir_from_mounts(inspect_data)
    if not host_data_dir and scan_entry is not None:
        candidate = scan_entry / "data" / "hermes"
        if candidate.is_dir():
            host_data_dir = str(candidate)
    if not host_data_dir:
        candidate = DOCKER_DATA_DIR / profile / "data" / "hermes"
        if candidate.is_dir():
            host_data_dir = str(candidate)

    if not host_data_dir:
        warnings.append("无法识别容器 /data/hermes 的宿主机映射目录，请检查 volume 映射")

    instance_root = _instance_root_from_host_data_dir(host_data_dir) if host_data_dir else ""
    env_file = str(Path(instance_root) / ".env") if instance_root else ""
    compose_path = _compose_path_from_labels(labels) or get_docker_compose_file_fallback()
    project_name = labels.get("com.docker.compose.project") or f"hermes-{profile}"
    service_name = labels.get("com.docker.compose.service")

    host_port, container_port = _parse_ports(inspect_data)
    if host_port is None and env_file:
        host_port = _read_env_port(env_file)
    if host_port is None:
        warnings.append("无法识别 WebUI 端口")

    public_host = get_docker_public_host()
    '''
    if public_host == "localhost" and not os.environ.get("DOCKER_PUBLIC_HOST"):
        warnings.append("未配置 DOCKER_PUBLIC_HOST，WebUI 公共访问地址可能不可用")
    '''
    if public_host == "localhost" and not settings.DOCKER_PUBLIC_HOST:
        warnings.append("未配置 DOCKER_PUBLIC_HOST，WebUI 公共访问地址可能不可用")

    public_url = get_docker_public_url(host_port) if host_port else None
    health_url = (
        f"http://{_docker_endpoint_host()}:{host_port}/health"
        if host_port
        else None
    )

    resolved_lifecycle, lifecycle_warnings = _resolve_lifecycle_mode(
        compose_path,
        env_file,
        lifecycle_mode,
    )
    warnings.extend(lifecycle_warnings)

    paths = _build_paths(host_data_dir) if host_data_dir else {}
    if instance_root:
        paths["instance_root"] = instance_root
        paths["env_file"] = env_file
    if compose_path:
        paths["compose_path"] = compose_path

    return DockerInstanceLayout(
        profile=profile,
        container_name=container_name,
        instance_root=instance_root,
        host_data_dir=host_data_dir or "",
        container_data_dir=DEFAULT_CONTAINER_DATA_DIR,
        env_file=env_file,
        compose_path=compose_path,
        project_name=project_name,
        service_name=service_name,
        host_port=host_port,
        container_port=container_port,
        public_url=public_url,
        health_url=health_url,
        lifecycle_mode=resolved_lifecycle,
        paths=paths,
        warnings=warnings,
    )


def layout_to_advanced_config(layout: DockerInstanceLayout) -> dict:
    return {
        "attach_mode": "external",
        "lifecycle_mode": layout.lifecycle_mode,
        "external_lifecycle": False,
        "external_container_name": layout.container_name,
        "profile": layout.profile,
        "paths": {
            "instance_root": layout.instance_root,
            "host_data_dir": layout.host_data_dir,
            "container_data_dir": layout.container_data_dir,
            "env_file": layout.env_file,
            "compose_path": layout.compose_path,
            "workspace_dir": layout.paths.get("workspace_dir"),
            "attachments_dir": layout.paths.get("attachments_dir"),
            "skills_dir": layout.paths.get("skills_dir"),
            "skill_inbox_dir": layout.paths.get("skill_inbox_dir"),
            "tools_dir": layout.paths.get("tools_dir"),
            "plugins_dir": layout.paths.get("plugins_dir"),
            "logs_dir": layout.paths.get("logs_dir"),
            "sessions_dir": layout.paths.get("sessions_dir"),
            "webui_dir": layout.paths.get("webui_dir"),
        },
        "compose": {
            "project_name": layout.project_name,
            "service_name": layout.service_name,
            "container_name": layout.container_name,
            "compose_path": layout.compose_path,
            "env_file": layout.env_file,
        },
        "webui": {
            "public_scheme": get_docker_public_scheme(),
            "public_host": get_docker_public_host(),
            "host_port": layout.host_port,
            "container_port": layout.container_port,
            "public_url": layout.public_url,
            "health_url": layout.health_url,
        },
        "capabilities": {
            "allow_logs": True,
            "allow_start": layout.lifecycle_mode != "linked_only",
            "allow_stop": layout.lifecycle_mode != "linked_only",
            "allow_restart": layout.lifecycle_mode != "linked_only",
            "allow_destroy_container": False,
            "allow_destroy_files": False,
            "allow_compose_recreate": False,
            "allow_skill_management": True,
        },
        "expert": {
            "profile": layout.profile,
            "template": layout.profile,
        },
    }
