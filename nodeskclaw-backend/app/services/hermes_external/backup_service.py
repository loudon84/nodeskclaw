"""External Docker Hermes backup service."""

from __future__ import annotations

import tarfile
from datetime import datetime, timezone
from pathlib import Path

from app.core.exceptions import BadRequestError
from app.models.instance import Instance
from app.schemas.external_docker import (
    ExternalDockerBackupItem,
    ExternalDockerBackupsResponse,
    ExternalDockerCreateBackupResponse,
)
from app.services.hermes_external._common import resolve_paths
from app.services.hermes_external.path_resolver import HermesExternalPathResolver

_path_resolver = HermesExternalPathResolver()


def _backup_dir(ep) -> Path:
    backup_dir = ep.backups_dir
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def list_backups(instance: Instance) -> ExternalDockerBackupsResponse:
    ep = resolve_paths(instance)
    _path_resolver.validate_host_data_dir(ep)
    backup_dir = _backup_dir(ep)

    items: list[ExternalDockerBackupItem] = []
    for entry in sorted(backup_dir.glob("backup-*.tar.gz"), reverse=True):
        stat = entry.stat()
        items.append(
            ExternalDockerBackupItem(
                name=entry.name,
                path=str(entry),
                size=stat.st_size,
                created_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            )
        )

    return ExternalDockerBackupsResponse(
        backup_dir=str(backup_dir),
        items=items,
    )


def create_backup(instance: Instance) -> ExternalDockerCreateBackupResponse:
    ep = resolve_paths(instance)
    _path_resolver.validate_host_data_dir(ep)
    backup_dir = _backup_dir(ep)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    backup_file = backup_dir / f"backup-{timestamp}.tar.gz"
    host_data_dir = ep.host_data_dir.resolve()
    env_file = ep.docker_env_file.resolve() if ep.docker_env_file.exists() else None

    try:
        with tarfile.open(backup_file, "w:gz") as tar:
            for child in host_data_dir.iterdir():
                if child.name == "backups":
                    continue
                tar.add(child, arcname=child.name)
    except OSError as exc:
        raise BadRequestError(
            message=f"创建备份失败: {exc}",
            message_key="errors.external_docker.backup_failed",
        ) from exc

    return ExternalDockerCreateBackupResponse(
        success=True,
        backup_file=str(backup_file),
        include_docker_env=False,
    )
