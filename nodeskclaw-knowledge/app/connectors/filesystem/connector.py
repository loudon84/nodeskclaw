"""Filesystem connector with root-alias path security."""

from __future__ import annotations

import fnmatch
import hashlib
import mimetypes
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.connectors.base import ConnectorCapabilities
from app.connectors.models import DiscoveryPage, FetchedSource, SourceDescriptor
from app.connectors.registry import register
from app.core.config import parse_connector_fs_roots
from app.core.exceptions import BadRequestError, ValidationError

# @lat: [[knowledge-objects#Connector Domain]]


def resolve_fs_path(*, root_alias: str, sub_path: str = "", roots: dict[str, str] | None = None) -> Path:
    configured = roots if roots is not None else parse_connector_fs_roots()
    if root_alias not in configured:
        raise ValidationError(
            message="未知 filesystem root_alias",
            message_key="errors.knowledge.connector_fs_root_unknown",
            details={"root_alias": root_alias},
        )
    root = Path(configured[root_alias]).resolve()
    relative = (sub_path or "").replace("\\", "/").lstrip("/")
    if ".." in Path(relative).parts:
        raise ValidationError(
            message="非法 filesystem 路径",
            message_key="errors.knowledge.connector_fs_path_escape",
        )
    candidate = (root / relative).resolve() if relative else root
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValidationError(
            message="filesystem 路径越界",
            message_key="errors.knowledge.connector_fs_path_escape",
        ) from exc
    if candidate.is_symlink():
        raise ValidationError(
            message="禁止跟随 symlink",
            message_key="errors.knowledge.connector_fs_path_escape",
        )
    return candidate


def _match_globs(rel_posix: str, patterns: list[str] | None) -> bool:
    if not patterns:
        return True
    name = Path(rel_posix).name
    return any(fnmatch.fnmatch(rel_posix, p) or fnmatch.fnmatch(name, p) for p in patterns)


@register("filesystem")
class FilesystemConnector:
    capabilities = ConnectorCapabilities(
        incremental_cursor=False,
        stable_external_id=False,
        delete_events=False,
        folders=True,
        source_metadata=True,
        authentication=False,
    )

    def __init__(self, config: dict[str, Any], *, roots: dict[str, str] | None = None, **_kwargs: Any) -> None:
        self.config = dict(config or {})
        self.roots = roots if roots is not None else parse_connector_fs_roots()
        self.root_alias = str(self.config.get("root_alias") or "")
        self.sub_path = str(self.config.get("sub_path") or "")
        self.include_globs = list(self.config.get("include_globs") or [])
        self.exclude_globs = list(self.config.get("exclude_globs") or [])
        if not self.root_alias:
            raise BadRequestError(
                message="filesystem connector 需要 root_alias",
                message_key="errors.knowledge.connector_config_invalid",
            )
        self.root = resolve_fs_path(root_alias=self.root_alias, sub_path=self.sub_path, roots=self.roots)

    async def test_connection(self) -> dict[str, Any]:
        if not self.root.exists() or not self.root.is_dir():
            raise BadRequestError(
                message="filesystem root 不可用",
                message_key="errors.knowledge.connector_fs_root_unavailable",
            )
        return {"ok": True, "root": str(self.root)}

    def _relative_id(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def _iter_files(self) -> list[Path]:
        if not self.root.exists():
            return []
        files: list[Path] = []
        for dirpath, _dirnames, filenames in os.walk(self.root, followlinks=False):
            for name in filenames:
                full = Path(dirpath) / name
                if full.is_symlink():
                    continue
                try:
                    resolved = full.resolve(strict=True)
                    resolved.relative_to(self.root)
                except (ValueError, OSError):
                    continue
                rel = self._relative_id(resolved)
                if self.exclude_globs and _match_globs(rel, self.exclude_globs):
                    continue
                if self.include_globs and not _match_globs(rel, self.include_globs):
                    continue
                files.append(resolved)
        files.sort(key=lambda p: p.as_posix())
        return files

    async def discover(self, *, cursor: dict[str, Any] | None = None) -> DiscoveryPage:
        files = self._iter_files()
        offset = int((cursor or {}).get("offset") or 0)
        page_size = int(self.config.get("page_size") or 200)
        page_size = max(1, min(page_size, 1000))
        slice_files = files[offset : offset + page_size]
        objects: list[SourceDescriptor] = []
        for path in slice_files:
            rel = self._relative_id(path)
            st = path.stat()
            mime, _ = mimetypes.guess_type(path.name)
            objects.append(
                SourceDescriptor(
                    external_object_id=rel,
                    name=path.name,
                    path=rel,
                    canonical_uri=path.as_uri(),
                    mime_type=mime,
                    size=st.st_size,
                    external_revision=str(int(st.st_mtime_ns)),
                    modified_at=datetime.fromtimestamp(st.st_mtime, tz=UTC),
                    source_metadata={"root_alias": self.root_alias},
                )
            )
        next_offset = offset + len(slice_files)
        has_more = next_offset < len(files)
        return DiscoveryPage(
            objects=objects,
            next_cursor={"offset": next_offset} if has_more else None,
            has_more=has_more,
        )

    async def fetch(self, descriptor: SourceDescriptor) -> FetchedSource:
        rel = (descriptor.external_object_id or descriptor.path or "").replace("\\", "/").lstrip("/")
        path = (self.root / Path(rel)).resolve()
        try:
            path.relative_to(self.root)
        except ValueError as exc:
            raise ValidationError(
                message="filesystem 路径越界",
                message_key="errors.knowledge.connector_fs_path_escape",
            ) from exc
        if path.is_symlink() or not path.is_file():
            raise ValidationError(
                message="filesystem 对象不可读取",
                message_key="errors.knowledge.connector_fs_path_escape",
            )
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        mime, _ = mimetypes.guess_type(path.name)
        return FetchedSource(
            file_name=path.name,
            mime_type=mime or descriptor.mime_type,
            stream=data,
            size=len(data),
            sha256=digest,
        )

    async def close(self) -> None:
        return None
