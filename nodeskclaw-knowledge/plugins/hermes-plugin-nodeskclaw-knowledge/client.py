"""HTTP client for nodeskclaw-knowledge knowledge.retrieve."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from config import PluginSettings

RETRIEVE_PATH = "/api/v2/agent/tools/knowledge.retrieve"
OPS_HINT = "Check SMC_KB_API_TOKEN in ~/.hermes/.env, then restart Hermes gateway."
_AUTH_ERROR_CODES = {40100}


def _maybe_attach_ops_hint(payload: dict[str, Any], *, http_status: int | None) -> dict[str, Any]:
    error_code = payload.get("error_code")
    needs_hint = http_status == 401 or error_code in _AUTH_ERROR_CODES
    if needs_hint and "plugin_ops_hint" not in payload:
        payload = dict(payload)
        payload["plugin_ops_hint"] = OPS_HINT
    return payload


def retrieve(
    settings: PluginSettings,
    *,
    knowledge_set_id: str,
    query: str,
    top_k: int | None = 10,
) -> dict[str, Any]:
    url = f"{settings.url.rstrip('/')}{RETRIEVE_PATH}"
    body: dict[str, Any] = {
        "knowledge_set_id": knowledge_set_id,
        "query": query,
    }
    if top_k is not None:
        body["top_k"] = top_k
    data = json.dumps(body).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
            if not isinstance(payload, dict):
                return {"code": 0, "data": payload}
            return _maybe_attach_ops_hint(payload, http_status=getattr(response, "status", None))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8") if exc.fp else ""
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {
                "code": exc.code,
                "error_code": exc.code,
                "message_key": "errors.knowledge.upstream_http_error",
                "message": raw or str(exc.reason),
                "data": None,
            }
        if not isinstance(payload, dict):
            payload = {
                "code": exc.code,
                "error_code": exc.code,
                "message": str(payload),
                "data": None,
            }
        return _maybe_attach_ops_hint(payload, http_status=exc.code)
    except urllib.error.URLError as exc:
        return {
            "code": 50300,
            "error_code": 50300,
            "message_key": "errors.knowledge.upstream_unreachable",
            "message": str(exc.reason),
            "data": None,
        }
