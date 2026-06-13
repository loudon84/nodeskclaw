"""Unified path resolver for external Docker Hermes instances."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from app.services.docker_constants import DOCKER_DATA_DIR

if TYPE_CHECKING:
    from app.models.instance import Instance

logger = logging.getLogger(__name__)

AUTO_CREATE_DIRS = ("workspace", "attachments", "backups", "skill-inbox")


@dataclass
class HermesExternalPaths:
    profile: str
    container_name: str
    docker_env_file: Path
    host_data_dir: Path
    container_data_dir: str
    config_file: Path
    workspace_dir: Path
    profiles_dir: Path
    skills_dir: Path
    skill_inbox_dir: Path
    tools_dir: Path
    plugins_dir: Path
    attachments_dir: Path
    logs_dir: Path
    sessions_dir: Path
    backups_dir: Path


class HermesExternalPathResolver:
    def resolve(self, instance: Instance) -> HermesExternalPaths:
        raw = instance.advanced_config
        try:
            cfg = json.loads(raw) if isinstance(raw, str) else (raw or {})
        except (json.JSONDecodeError, TypeError):
            cfg = {}

        paths = cfg.get("paths") or {}
        profile = cfg.get("profile") or instance.slug or instance.name
        container_name = cfg.get("external_container_name") or f"hermes-{profile}"
        container_data_dir = paths.get("container_data_dir") or "/data/hermes"

        host_data_dir_str = paths.get("host_data_dir")
        if not host_data_dir_str:
            host_data_dir = DOCKER_DATA_DIR / profile / "data" / "hermes"
        else:
            host_data_dir = Path(host_data_dir_str)

        docker_env_file = Path(
            paths.get("docker_env_file")
            or paths.get("env_file")
            or str(host_data_dir.parent.parent / ".env")
        )

        return HermesExternalPaths(
            profile=profile,
            container_name=container_name,
            docker_env_file=docker_env_file,
            host_data_dir=host_data_dir,
            container_data_dir=container_data_dir,
            config_file=host_data_dir / "config.yaml",
            workspace_dir=host_data_dir / "workspace",
            profiles_dir=host_data_dir / "profiles",
            skills_dir=host_data_dir / "skills",
            skill_inbox_dir=host_data_dir / "skill-inbox",
            tools_dir=host_data_dir / "tools",
            plugins_dir=host_data_dir / "plugins",
            attachments_dir=host_data_dir / "attachments",
            logs_dir=host_data_dir / "logs",
            sessions_dir=host_data_dir / "sessions",
            backups_dir=host_data_dir / "backups",
        )

    def ensure_auto_create_dirs(self, ep: HermesExternalPaths) -> None:
        for name in AUTO_CREATE_DIRS:
            d = ep.host_data_dir / name
            d.mkdir(parents=True, exist_ok=True)

    def validate_host_data_dir(self, ep: HermesExternalPaths) -> None:
        if not ep.host_data_dir.is_dir():
            raise FileNotFoundError(
                f"Hermes 数据目录不存在: {ep.host_data_dir}，请检查 Docker volume 映射"
            )
