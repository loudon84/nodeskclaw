"""Docker deployment constants."""

import os
from pathlib import Path
from urllib.parse import urlparse

from app.core.config import settings

DOCKER_BASE_PORT = 13000
HERMES_EXPERT_PORT_START = settings.HERMES_EXPERT_PORT_START
HERMES_EXPERT_PORT_END = settings.HERMES_EXPERT_PORT_END

_DEFAULT_DOCKER_DATA_DIR = str(Path.home() / ".nodeskclaw" / "docker-instances")

'''
DOCKER_DATA_DIR = Path(os.environ.get(
    "DOCKER_DATA_DIR",
    _DEFAULT_DOCKER_DATA_DIR,
))

DOCKER_HOST_DATA_DIR = os.environ.get(
    "DOCKER_HOST_DATA_DIR",
    os.environ.get("DOCKER_DATA_DIR", _DEFAULT_DOCKER_DATA_DIR),
)

DOCKER_ATTACH_SCAN_DIRS_RAW = os.environ.get("DOCKER_ATTACH_SCAN_DIRS", "")
'''

DOCKER_DATA_DIR = Path(settings.DOCKER_DATA_DIR or _DEFAULT_DOCKER_DATA_DIR)

DOCKER_HOST_DATA_DIR = (
    settings.DOCKER_HOST_DATA_DIR
    or settings.DOCKER_DATA_DIR
    or _DEFAULT_DOCKER_DATA_DIR
)

DOCKER_ATTACH_SCAN_DIRS_RAW = settings.DOCKER_ATTACH_SCAN_DIRS or ""

def get_docker_attach_scan_dirs() -> list[Path]:
    raw = DOCKER_ATTACH_SCAN_DIRS_RAW.strip()
    if raw:
        return [Path(p.strip()) for p in raw.split(",") if p.strip()]
    return [DOCKER_DATA_DIR]


def get_hermes_instances_root() -> Path:
    root = (settings.HERMES_INSTANCES_ROOT or "").strip()
    if root:
        return Path(root)
    scan_dirs = get_docker_attach_scan_dirs()
    if scan_dirs:
        return scan_dirs[0]
    return DOCKER_DATA_DIR


def get_hermes_agent_host_ip() -> str:
    host = (settings.HERMES_AGENT_HOST_IP or "").strip()
    if host:
        return host
    return get_docker_public_host()


def _host_from_portal_base_url() -> str | None:
    portal_url = (settings.PORTAL_BASE_URL or "").strip()
    if not portal_url:
        return None
    parsed = urlparse(portal_url if "://" in portal_url else f"http://{portal_url}")
    return parsed.hostname or None


def get_docker_public_scheme() -> str:
    return settings.DOCKER_PUBLIC_SCHEME or "http"


def get_docker_public_host() -> str:
    host_raw = settings.DOCKER_PUBLIC_HOST
    if host_raw:
        return host_raw
    derived = _host_from_portal_base_url()
    if derived:
        return derived
    return "localhost"


def get_docker_public_url(port: int) -> str:
    return f"{get_docker_public_scheme()}://{get_docker_public_host()}:{port}"


def get_docker_compose_file_fallback() -> str | None:
    compose_file = settings.DOCKER_COMPOSE_FILE
    if compose_file and Path(compose_file).exists():
        return compose_file
    parent_compose = DOCKER_DATA_DIR.parent / "docker-compose.yml"
    if parent_compose.exists():
        return str(parent_compose)
    scan_dirs = get_docker_attach_scan_dirs()
    if scan_dirs:
        scan_parent_compose = scan_dirs[0].parent / "docker-compose.yml"
        if scan_parent_compose.exists():
            return str(scan_parent_compose)
    return compose_file or None
