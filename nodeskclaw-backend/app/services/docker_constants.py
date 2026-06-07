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
