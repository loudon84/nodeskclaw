"""Unified path resolver for external Docker Hermes instances."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from app.core.exceptions import BadRequestError
from app.services.docker_constants import DOCKER_DATA_DIR

if TYPE_CHECKING:
    from app.models.instance import Instance

logger = logging.getLogger(__name__)

AUTO_CREATE_DIRS = ("workspace", "attachments", "backups", "skill-inbox")
PROFILE_NAME_PATTERN = re.compile(r"^[a-z0-9_-]+$")
DEFAULT_PROFILE_NAME = "default"


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


@dataclass
class HermesProfilePaths:
    profile: str
    profile_type: str
    profile_dir: Path
    env_file: Path
    config_file: Path
    soul_file: Path
    skills_dir: Path
    workspace_dir: Path
    backups_dir: Path
    core_file_backup_dir: Path


def validate_profile_name(name: str) -> str:
    value = (name or "").strip()
    if not value:
        raise BadRequestError(
            message="Profile 名称不能为空",
            message_key="errors.external_docker.profile_name_invalid",
        )
    if value != DEFAULT_PROFILE_NAME and not PROFILE_NAME_PATTERN.match(value):
        raise BadRequestError(
            message="Profile 名称仅允许小写字母、数字、连字符和下划线",
            message_key="errors.external_docker.profile_name_invalid",
        )
    if ".." in value or "/" in value or "\\" in value:
        raise BadRequestError(
            message="Profile 名称包含非法字符",
            message_key="errors.external_docker.profile_name_invalid",
        )
    return value


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

    def resolve_profile(self, instance: Instance, profile_name: str) -> HermesProfilePaths:
        ep = self.resolve(instance)
        return self.resolve_profile_from_host_data_dir(ep.host_data_dir, profile_name)

    def resolve_profile_from_host_data_dir(
        self,
        host_data_dir: Path,
        profile_name: str,
    ) -> HermesProfilePaths:
        profile = validate_profile_name(profile_name)
        host_data_dir = Path(host_data_dir)

        if profile == DEFAULT_PROFILE_NAME:
            profile_dir = host_data_dir
            profile_type = "default"
            core_file_backup_dir = host_data_dir / "backups" / "core-files" / DEFAULT_PROFILE_NAME
        else:
            profile_dir = host_data_dir / "profiles" / profile
            profile_type = "extended"
            core_file_backup_dir = profile_dir / "backups" / "core-files"

        return HermesProfilePaths(
            profile=profile,
            profile_type=profile_type,
            profile_dir=profile_dir,
            env_file=profile_dir / ".env",
            config_file=profile_dir / "config.yaml",
            soul_file=profile_dir / "SOUL.md",
            skills_dir=profile_dir / "skills",
            workspace_dir=profile_dir / "workspace",
            backups_dir=profile_dir / "backups",
            core_file_backup_dir=core_file_backup_dir,
        )
