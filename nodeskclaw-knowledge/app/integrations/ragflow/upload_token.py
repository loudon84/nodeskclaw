"""Deterministic RAGFlow upload naming to support post-timeout recovery."""

from __future__ import annotations

from pathlib import Path


def build_upload_token(*, source_file_id: str, file_version_id: str) -> str:
    return f"nk_{source_file_id}_{file_version_id}"


def deterministic_upload_filename(
    *,
    source_file_id: str,
    file_version_id: str,
    original_name: str,
) -> str:
    token = build_upload_token(source_file_id=source_file_id, file_version_id=file_version_id)
    suffix = Path(original_name or "file").suffix
    if not suffix:
        suffix = ""
    safe_suffix = "".join(ch for ch in suffix if ch.isalnum() or ch == ".")[:32]
    return f"{token}{safe_suffix}"
