"""Docker deployment constants."""

import os
from pathlib import Path

from app.core.config import settings

DOCKER_BASE_PORT = 13000
HERMES_EXPERT_PORT_START = settings.HERMES_EXPERT_PORT_START
HERMES_EXPERT_PORT_END = settings.HERMES_EXPERT_PORT_END

_DEFAULT_DOCKER_DATA_DIR = str(Path.home() / ".nodeskclaw" / "docker-instances")

DOCKER_DATA_DIR = Path(os.environ.get(
    "DOCKER_DATA_DIR",
    _DEFAULT_DOCKER_DATA_DIR,
))

DOCKER_HOST_DATA_DIR = os.environ.get(
    "DOCKER_HOST_DATA_DIR",
    os.environ.get("DOCKER_DATA_DIR", _DEFAULT_DOCKER_DATA_DIR),
)

DOCKER_ATTACH_SCAN_DIRS_RAW = os.environ.get("DOCKER_ATTACH_SCAN_DIRS", "")


def get_docker_attach_scan_dirs() -> list[Path]:
    raw = DOCKER_ATTACH_SCAN_DIRS_RAW.strip()
    if raw:
        return [Path(p.strip()) for p in raw.split(",") if p.strip()]
    return [DOCKER_DATA_DIR]