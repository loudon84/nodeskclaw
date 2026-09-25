"""Run-scoped, idempotent artifact finalization."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from .collector import ArtifactCollector
from .config import ArtifactSettings
from .contracts import (
    NativeOutputRef,
    NativeRunFinalizeRequest,
    NativeRunFinalizeResult,
)
from .upload import MinioUploader, UploadResult


class ArtifactUploader(Protocol):
    def upload(self, run_id: str, path: Path, required: bool) -> UploadResult: ...


@dataclass
class RunArtifactState:
    paths: list[Path] = field(default_factory=list)
    workspace_root: Path | None = None
    finalizing: bool = False
    completed: threading.Event = field(default_factory=threading.Event)
    result: NativeRunFinalizeResult | None = None


class ArtifactRegistry:
    def __init__(
        self, settings: ArtifactSettings, uploader: ArtifactUploader | None = None
    ) -> None:
        self._settings = settings
        self._uploader = uploader or MinioUploader(settings)
        self._lock = threading.RLock()
        self._by_run: dict[str, RunArtifactState] = {}

    def track_path(
        self, run_id: str, path: str | Path, workspace_root: str | Path
    ) -> None:
        if not run_id.strip():
            return
        candidate = Path(path)
        root = Path(workspace_root)
        if not candidate.is_absolute():
            candidate = root / candidate
        with self._lock:
            state = self._by_run.setdefault(run_id, RunArtifactState())
            if state.workspace_root is None:
                state.workspace_root = root
            if candidate not in state.paths:
                state.paths.append(candidate)

    def finalize(self, request: NativeRunFinalizeRequest) -> NativeRunFinalizeResult:
        with self._lock:
            state = self._by_run.setdefault(request.run_id, RunArtifactState())
            if state.result is not None:
                return state.result
            if state.finalizing:
                completed = state.completed
                snapshot = None
            else:
                state.finalizing = True
                completed = None
                snapshot = (
                    tuple(state.paths),
                    request.workspace_root or state.workspace_root,
                )
        if completed is not None:
            completed.wait()
            with self._lock:
                return self._by_run[
                    request.run_id
                ].result or NativeRunFinalizeResult.failed(
                    "artifact_finalize_interrupted",
                    "artifact finalization did not produce a result",
                )
        assert snapshot is not None
        result = NativeRunFinalizeResult.failed(
            "artifact_finalize_interrupted",
            "artifact finalization did not produce a result",
        )
        try:
            result = self._finalize_snapshot(request, *snapshot)
        except (OSError, RuntimeError, TypeError, ValueError) as exc:
            result = NativeRunFinalizeResult.failed(
                "artifact_finalize_failed", str(exc)
            )
        finally:
            with self._lock:
                state = self._by_run[request.run_id]
                state.result = result
                state.finalizing = False
                state.completed.set()
        return result

    def _finalize_snapshot(
        self,
        request: NativeRunFinalizeRequest,
        paths: tuple[Path, ...],
        workspace_root: Path | None,
    ) -> NativeRunFinalizeResult:
        if not paths:
            return NativeRunFinalizeResult.ready()
        if workspace_root is None:
            return NativeRunFinalizeResult.failed(
                "artifact_workspace_missing", "workspace_root is required"
            )
        try:
            collection = ArtifactCollector(self._settings).collect(
                workspace_root, paths
            )
        except OSError as exc:
            return NativeRunFinalizeResult.failed(
                "artifact_workspace_invalid", str(exc)
            )
        if collection.rejected:
            return NativeRunFinalizeResult.failed(
                "artifact_collection_rejected", collection.rejected[0].reason
            )
        if len(collection.candidates) > self._settings.max_files:
            return NativeRunFinalizeResult.failed(
                "artifact_file_limit_exceeded", "artifact count exceeds max_files"
            )
        total_bytes = sum(candidate.size_bytes for candidate in collection.candidates)
        if total_bytes > self._settings.max_total_bytes:
            return NativeRunFinalizeResult.failed(
                "artifact_total_limit_exceeded",
                "artifact total exceeds max_total_bytes",
            )

        output_refs: list[NativeOutputRef] = []
        for candidate in collection.candidates:
            try:
                result = self._uploader.upload(
                    request.run_id, candidate.path, candidate.required
                )
            except (OSError, RuntimeError, ValueError) as exc:
                return NativeRunFinalizeResult.failed(
                    "artifact_upload_failed", str(exc), tuple(output_refs)
                )
            if not result.ok:
                if result.required:
                    return NativeRunFinalizeResult.failed(
                        "artifact_upload_failed",
                        result.error or "required MinIO upload failed",
                        tuple(output_refs),
                    )
                continue
            output_refs.append(
                NativeOutputRef(
                    name=result.name,
                    content_type=result.content_type,
                    url=result.url,
                    required=result.required,
                    size_bytes=result.size_bytes,
                    checksum_sha256=result.checksum_sha256,
                    expires_at=result.expires_at,
                )
            )
        return NativeRunFinalizeResult.ready(tuple(output_refs))
