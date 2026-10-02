from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any


def _encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def mint_capability(
    *,
    org_id: str,
    run_id: str,
    attempt_id: str,
    generation: int,
    signing_key: str,
    ttl_seconds: int,
    now: int | None = None,
) -> str | None:
    if not signing_key:
        return None
    issued = int(time.time() if now is None else now)
    payload = {
        "v": 1,
        "org_id": org_id,
        "run_id": run_id,
        "attempt_id": attempt_id,
        "generation": int(generation),
        "iat": issued,
        "exp": issued + int(ttl_seconds),
        "nonce": secrets.token_urlsafe(16),
    }
    body = _encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = hmac.new(signing_key.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_encode(signature)}"


def verify_capability(token: str | None, *, signing_key: str, now: int | None = None) -> tuple[dict[str, Any] | None, str]:
    if not token or not signing_key:
        return None, "AGENT_TOOL_CAPABILITY_MISSING"
    parts = token.split(".")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None, "AGENT_TOOL_CAPABILITY_INVALID"
    expected = hmac.new(signing_key.encode("utf-8"), parts[0].encode("ascii"), hashlib.sha256).digest()
    try:
        presented = _decode(parts[1])
        payload = json.loads(_decode(parts[0]).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeError):
        return None, "AGENT_TOOL_CAPABILITY_INVALID"
    if not hmac.compare_digest(expected, presented):
        return None, "AGENT_TOOL_CAPABILITY_INVALID"
    if not isinstance(payload, dict):
        return None, "AGENT_TOOL_CAPABILITY_INVALID"
    current = int(time.time() if now is None else now)
    if int(payload.get("exp") or 0) <= current:
        return None, "AGENT_TOOL_CAPABILITY_EXPIRED"
    return payload, ""


def stable_tool_call_id(*, attempt_id: str, generation: int, rpc_id: str) -> str:
    return f"{attempt_id}:{int(generation)}:{rpc_id}"
