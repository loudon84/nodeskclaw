"""Local Artifact Store — pathlib + ARTIFACT_LOCAL_ROOT; signed URL short TTL not persisted."""

from __future__ import annotations

import hashlib
import hmac
import time
from pathlib import Path
from urllib.parse import quote

from app.core.config import settings


def _root() -> Path:
    root = Path(settings.ARTIFACT_LOCAL_ROOT)
    root.mkdir(parents=True, exist_ok=True)
    return root


def write_bytes(relative_path: str, data: bytes) -> str:
    path = _root() / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return f"local://{relative_path.replace(chr(92), '/')}"


def read_bytes(uri: str) -> bytes:
    relative = uri.removeprefix("local://")
    path = _root() / relative
    return path.read_bytes()


def signed_url(uri: str, *, ttl_seconds: int = 300) -> str:
    """Compute ephemeral signed URL; do not persist tokens."""
    expires = int(time.time()) + ttl_seconds
    secret = (settings.KNOWLEDGE_CONNECTOR_MASTER_KEY or "knowledge-artifact").encode("utf-8")
    payload = f"{uri}:{expires}".encode()
    sig = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return f"/artifacts/signed?uri={quote(uri, safe='')}&expires={expires}&sig={sig}"


def verify_signed_url(*, uri: str, expires: int, sig: str) -> bool:
    if int(time.time()) > expires:
        return False
    secret = (settings.KNOWLEDGE_CONNECTOR_MASTER_KEY or "knowledge-artifact").encode("utf-8")
    payload = f"{uri}:{expires}".encode()
    expected = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)
