from __future__ import annotations

import hashlib
import json
from typing import Any


def scope_digest(spec: dict[str, Any]) -> str:
    pins = sorted(
        list(spec.get("account_pins") or []),
        key=lambda item: str((item or {}).get("integration_account_id") or ""),
    )
    body = {
        "provider": spec.get("provider") or "",
        "provider_user_id": spec.get("provider_user_id") or "",
        "run_id": spec.get("run_id") or "",
        "account_pins": pins,
        "toolkit_allowlist": sorted(str(item) for item in spec.get("toolkit_allowlist") or []),
        "tool_allowlist": sorted(str(item) for item in spec.get("tool_allowlist") or []),
        "sandbox_enabled": False,
    }
    raw = json.dumps(body, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
