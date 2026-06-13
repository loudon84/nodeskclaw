"""External Docker instance file listing service."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.core.exceptions import BadRequestError, ForbiddenError
from app.models.instance import Instance
from app.schemas.external_docker import ExternalDockerFileItem, ExternalDockerFilesResponse
from app.services.hermes_external._common import resolve_paths
from app.services.hermes_external.path_resolver import HermesExternalPathResolver

_path_resolver = HermesExternalPathResolver()


def _resolve_scope_root(host_data_dir: Path, scope: str, sub_path: str) -> tuple[Path, Path]:
    if scope == "workspace":
        allowed_root = host_data_dir / "workspace"
        allowed_root.mkdir(parents=True, exist_ok=True)
    elif scope == "system":
        allowed_root = host_data_dir
    else:
        raise BadRequestError(
            message="不支持的文件 scope",
            message_key="errors.external_docker.invalid_file_scope",
        )

    requested = allowed_root if not sub_path else (allowed_root / sub_path)
    resolved = requested.resolve()
    allowed_resolved = allowed_root.resolve()
    if not str(resolved).startswith(str(allowed_resolved)):
        raise ForbiddenError(
            message="路径不在允许范围内",
            message_key="errors.external_docker.path_not_allowed",
        )
    return allowed_root, resolved


def list_files(
    instance: Instance,
    scope: str = "workspace",
    path: str = "",
) -> ExternalDockerFilesResponse:
    ep = resolve_paths(instance)
    _path_resolver.validate_host_data_dir(ep)

    allowed_root, target = _resolve_scope_root(ep.host_data_dir, scope, path)
    if not target.exists():
        return ExternalDockerFilesResponse(
            root=str(allowed_root),
            scope=scope,
            path=path,
            exists=False,
            items=[],
        )

    if not target.is_dir():
        raise BadRequestError(
            message="目标路径不是目录",
            message_key="errors.external_docker.path_not_directory",
        )

    items: list[ExternalDockerFileItem] = []
    for entry in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        stat = entry.stat()
        rel_path = str(entry.relative_to(allowed_root)).replace("\\", "/")
        items.append(
            ExternalDockerFileItem(
                name=entry.name,
                path=rel_path,
                is_dir=entry.is_dir(),
                size=None if entry.is_dir() else stat.st_size,
                modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            )
        )

    return ExternalDockerFilesResponse(
        root=str(allowed_root),
        scope=scope,
        path=path,
        exists=True,
        items=items,
    )
