"""Workspace-bounded artifact candidate collection."""

from __future__ import annotations

import os
from collections.abc import Iterable
from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

from .config import ArtifactSettings


@dataclass(frozen=True)
class ArtifactCandidate:
    path: Path
    name: str
    size_bytes: int
    required: bool


@dataclass(frozen=True)
class RejectedPath:
    path: Path
    reason: str


@dataclass(frozen=True)
class CollectionResult:
    candidates: tuple[ArtifactCandidate, ...]
    rejected: tuple[RejectedPath, ...]


class ArtifactCollector:
    def __init__(self, settings: ArtifactSettings) -> None:
        self._settings = settings

    def collect(self, workspace_root: Path, paths: Iterable[Path]) -> CollectionResult:
        root = Path(workspace_root).resolve(strict=True)
        candidates: list[ArtifactCandidate] = []
        rejected: list[RejectedPath] = []
        seen: set[Path] = set()
        for raw_path in paths:
            path = Path(raw_path)
            if not path.is_absolute():
                path = root / path
            if self._traverses_symlink(root, path):
                rejected.append(RejectedPath(path, "symbolic links are not allowed"))
                continue
            if path.is_symlink():
                rejected.append(RejectedPath(path, "symbolic links are not allowed"))
                continue
            try:
                resolved = path.resolve(strict=True)
            except OSError:
                rejected.append(RejectedPath(path, "path does not exist"))
                continue
            try:
                relative_path = resolved.relative_to(root)
            except ValueError:
                rejected.append(RejectedPath(path, "path is outside workspace"))
                continue
            if not resolved.is_file():
                rejected.append(RejectedPath(path, "path is not a regular file"))
                continue
            relative_name = relative_path.as_posix()
            if any(
                fnmatchcase(relative_name, pattern)
                for pattern in self._settings.exclude_patterns
            ):
                continue
            if (
                self._settings.ext_allow
                and resolved.suffix.lower() not in self._settings.ext_allow
            ):
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            candidates.append(
                ArtifactCandidate(
                    path=resolved,
                    name=resolved.name,
                    size_bytes=resolved.stat().st_size,
                    required=self._settings.required_default,
                )
            )
        return CollectionResult(tuple(candidates), tuple(rejected))

    @staticmethod
    def _traverses_symlink(root: Path, path: Path) -> bool:
        cursor = path
        while True:
            if cursor.is_symlink():
                return True
            try:
                if os.path.samefile(cursor, root):
                    return False
            except OSError:
                return False
            parent = cursor.parent
            if parent == cursor:
                return False
            cursor = parent
