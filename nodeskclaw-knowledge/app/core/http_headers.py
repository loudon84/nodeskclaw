"""HTTP header helpers that remain latin-1 safe."""

from __future__ import annotations

from urllib.parse import quote


def content_disposition_attachment(file_name: str | None) -> str:
    raw = (file_name or "").strip() or "download"
    ascii_fallback = "".join(ch if 32 <= ord(ch) < 127 and ch not in {"\\", '"'} else "_" for ch in raw)
    if not ascii_fallback.replace("_", ""):
        ascii_fallback = "download"
    if ascii_fallback == raw:
        return f'attachment; filename="{raw}"'
    encoded = quote(raw, safe="")
    return f"attachment; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded}"
