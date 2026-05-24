import base64
import hashlib
import hmac
import json
import time

from app.core.config import settings


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def create_llm_attribution_token(
    *,
    org_id: str,
    workspace_id: str,
    instance_id: str,
    source: str,
    ttl_seconds: int = 300,
) -> str | None:
    if not settings.LLM_ATTRIBUTION_SECRET:
        return None
    payload = {
        "org_id": org_id,
        "workspace_id": workspace_id,
        "instance_id": instance_id,
        "source": source,
        "exp": int(time.time()) + ttl_seconds,
    }
    body = _b64url_encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    sig = hmac.new(
        settings.LLM_ATTRIBUTION_SECRET.encode("utf-8"),
        body.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{body}.{_b64url_encode(sig)}"
