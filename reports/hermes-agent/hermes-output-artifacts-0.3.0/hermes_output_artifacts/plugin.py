"""Formal Hermes plugin entrypoint for MinIO output artifacts."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .config import ArtifactSettings
from .contracts import NativeRunFinalizeRequest, NativeRunFinalizeResult
from .refs import ArtifactRegistry

_PATH_KEYS = (
    "path",
    "file",
    "filepath",
    "file_path",
    "output",
    "destination",
    "target",
)


def _extract_paths(tool_name: str, args: Any, result: Any) -> tuple[str, ...]:
    values: list[str] = []

    def append(value: Any) -> None:
        if isinstance(value, str) and value.strip():
            values.append(value.strip())
        elif isinstance(value, (list, tuple)):
            for item in value:
                append(item)

    if isinstance(args, Mapping):
        for key in _PATH_KEYS:
            append(args.get(key))
    if isinstance(result, Mapping):
        for key in ("path", "file", "written", "output_path"):
            append(result.get(key))
    return tuple(dict.fromkeys(values))


def register(ctx: Any, environment: Mapping[str, str] | None = None) -> None:
    settings = ArtifactSettings.from_context(
        ctx, os.environ if environment is None else environment
    )
    if not settings.enabled:
        return
    register_hook = getattr(ctx, "register_hook", None)
    register_finalizer = getattr(ctx, "register_native_run_finalizer", None)
    if not callable(register_hook):
        raise TypeError("Hermes PluginContext.register_hook() is required")
    if not callable(register_finalizer):
        raise TypeError(
            "Hermes Native Run finalizer support is required: ctx.register_native_run_finalizer()"
        )
    registry = ArtifactRegistry(settings)

    def post_tool_call(
        tool_name: str = "",
        args: Any = None,
        result: Any = None,
        native_run_id: str | None = None,
        workspace_root: str | Path | None = None,
        **_: Any,
    ) -> None:
        if (
            not isinstance(native_run_id, str)
            or not native_run_id.strip()
            or workspace_root is None
        ):
            return
        for path in _extract_paths(tool_name, args, result):
            registry.track_path(native_run_id, path, workspace_root)

    def finalize(request: NativeRunFinalizeRequest) -> NativeRunFinalizeResult:
        return registry.finalize(request)

    register_hook("post_tool_call", post_tool_call)
    register_finalizer(finalize)
