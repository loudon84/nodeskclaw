"""Formal Hermes plugin entrypoint for MinIO output artifacts."""

from __future__ import annotations

import inspect
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .config import ArtifactSettings
from .refs import REGISTRY, ArtifactRegistry
from .upload import HttpUploader, MinioUploader

_PATH_KEYS = (
    "path",
    "file",
    "filepath",
    "file_path",
    "output",
    "destination",
    "target",
)
_SUCCESS_STATUSES = frozenset({"completed", "succeeded", "success"})
_IMPORT_PATHS = (
    "gateway.platforms.api_server",
    "hermes_agent.gateway.platforms.api_server",
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
        for key in ("path", "file", "written", "output_path", "file_path"):
            append(result.get(key))
    return tuple(dict.fromkeys(values))


def _run_id_from_payload(**payload: Any) -> str:
    for key in ("native_run_id", "run_id", "task_id", "session_id"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _workspace_from_payload(**payload: Any) -> Path | None:
    for key in ("workspace_root", "workspace", "cwd"):
        value = payload.get(key)
        if value:
            return Path(value)
    return None


def _apply_terminal_gate(run_id: str, status: Any, fields: Mapping[str, Any]):
    status_text = str(status or "")
    payload = dict(fields)
    if status_text.lower() not in _SUCCESS_STATUSES:
        return status, payload
    try:
        refs = REGISTRY.merge_output_refs(
            str(run_id), payload.get("output_refs"), force_flush=True
        )
        ok, error = REGISTRY.can_complete(str(run_id))
        payload["output_refs"] = refs
        if not ok:
            payload["error"] = error or "artifact upload gate failed"
            return "failed", payload
        return status, payload
    except Exception as exc:
        payload["error"] = f"output_artifacts gate error: {exc}"
        return "failed", payload


def _install_terminal_gate() -> bool:
    adapter = None
    for module_name in _IMPORT_PATHS:
        try:
            module = __import__(module_name, fromlist=["APIServerAdapter"])
        except ImportError:
            continue
        adapter = getattr(module, "APIServerAdapter", None)
        if adapter is not None:
            break
    if adapter is None:
        return False
    original = getattr(adapter, "_set_run_status", None)
    if not callable(original) or getattr(original, "_output_artifacts_wrapped", False):
        return callable(original)

    if inspect.iscoroutinefunction(original):

        async def wrapped(self, run_id, status, **fields):
            status, fields = _apply_terminal_gate(run_id, status, fields)
            return await original(self, run_id, status, **fields)

    else:

        def wrapped(self, run_id, status, **fields):
            status, fields = _apply_terminal_gate(run_id, status, fields)
            return original(self, run_id, status, **fields)

    wrapped._output_artifacts_wrapped = True
    adapter._set_run_status = wrapped
    return True


def track_workspace_file(
    run_id: str, path: str, workspace_root: str | Path | None = None
) -> None:
    root = workspace_root if workspace_root is not None else Path(path).parent
    REGISTRY.track_path(run_id, path, root)


def register(
    ctx: Any,
    environment: Mapping[str, str] | None = None,
    uploader: Any | None = None,
) -> None:
    settings = ArtifactSettings.from_context(
        ctx, os.environ if environment is None else environment
    )
    if not settings.enabled:
        return
    register_hook = getattr(ctx, "register_hook", None)
    register_finalizer = getattr(ctx, "register_native_run_finalizer", None)
    if not callable(register_hook):
        raise TypeError("Hermes PluginContext.register_hook() is required")
    has_finalizer = callable(register_finalizer)
    has_gate = _install_terminal_gate()
    if not has_finalizer and not has_gate:
        raise TypeError(
            "Hermes v0.21 requires APIServerAdapter._set_run_status wrapping, "
            "or Core must provide ctx.register_native_run_finalizer()"
        )
    if uploader is None:
        uploader = (
            HttpUploader(settings)
            if settings.upload_mode == "http"
            else MinioUploader(settings)
        )
    registry = ArtifactRegistry(settings, uploader=uploader)
    REGISTRY.bind(registry)

    def post_tool_call(
        tool_name: str = "",
        args: Any = None,
        result: Any = None,
        native_run_id: str | None = None,
        workspace_root: str | Path | None = None,
        **payload: Any,
    ) -> None:
        run_id = _run_id_from_payload(
            native_run_id=native_run_id,
            run_id=payload.get("run_id"),
            task_id=payload.get("task_id"),
            session_id=payload.get("session_id"),
        )
        root = workspace_root or _workspace_from_payload(**payload)
        if not run_id or root is None:
            return
        for path in _extract_paths(tool_name, args, result):
            registry.track_path(run_id, path, root)

    def finalize(request: Any) -> Any:
        return registry.finalize(request)

    register_hook("post_tool_call", post_tool_call)
    if has_finalizer:
        register_finalizer(finalize)
