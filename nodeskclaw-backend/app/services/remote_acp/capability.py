from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any

from app.contracts.remote_acp.constants import CAPABILITY_TTL_SECONDS

CAPABILITY_CONTEXT = "nodeskclaw.remote-acp.capability.v1"


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def derived_key(internal_token: str) -> bytes:
    return hmac.new(internal_token.encode("utf-8"), CAPABILITY_CONTEXT.encode("utf-8"), hashlib.sha256).digest()


def sign_payload_b64(internal_token: str, payload_b64: str) -> str:
    signature = hmac.new(derived_key(internal_token), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return _b64url(signature)


def mint_execution_capability(
    *,
    internal_token: str,
    org_id: str,
    user_id: str,
    agent_ref: str,
    context_version: int = 1,
    trace_id: str,
    now: int | None = None,
    ttl_seconds: int = CAPABILITY_TTL_SECONDS,
    jti: str | None = None,
) -> str:
    issued_at = int(time.time() if now is None else now)
    ttl = min(int(ttl_seconds), 120)
    payload = {
        "v": 1,
        "jti": jti or str(uuid.uuid4()),
        "org_id": org_id,
        "user_id": user_id,
        "agent_ref": agent_ref,
        "context_version": int(context_version),
        "issued_at": issued_at,
        "expires_at": issued_at + ttl,
        "trace_id": trace_id,
    }
    payload_b64 = _b64url(canonical_json(payload).encode("utf-8"))
    return f"{payload_b64}.{sign_payload_b64(internal_token, payload_b64)}"


def verify_execution_capability(
    token: str | None,
    *,
    current_token: str,
    previous_token: str = "",
    now: int | None = None,
) -> tuple[dict[str, Any] | None, str]:
    if not token or not current_token:
        return None, "ACP_CAPABILITY_INVALID"
    parts = token.split(".")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        return None, "ACP_CAPABILITY_INVALID"
    payload_b64, presented_sig = parts
    keys = [current_token]
    if previous_token:
        keys.append(previous_token)
    matched = False
    for key in keys:
        expected = sign_payload_b64(key, payload_b64)
        if hmac.compare_digest(expected, presented_sig):
            matched = True
            break
    if not matched:
        return None, "ACP_CAPABILITY_INVALID"
    try:
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except (ValueError, json.JSONDecodeError, UnicodeError):
        return None, "ACP_CAPABILITY_INVALID"
    current = int(time.time() if now is None else now)
    if int(payload.get("expires_at") or 0) <= current:
        return None, "ACP_CAPABILITY_EXPIRED"
    return payload, ""
