"""DeskClaw API client -- shared HTTP helper for all tool scripts.

Uses only Python standard library (urllib.request + json).
Authentication via environment variables:
  DESKCLAW_API_URL        Backend API base URL (e.g. http://localhost:4510/api/v1)
  DESKCLAW_TOKEN          Instance proxy_token for Bearer auth
  DESKCLAW_WORKSPACE_ID   Current workspace ID
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
import urllib.error
import urllib.request
import uuid
from typing import Any

def _discover_from_openclaw_config() -> tuple[str, str, str]:
    """Fall back to openclaw.json channel config when env vars are missing."""
    cfg_path = os.path.expanduser("~/.openclaw/openclaw.json")
    api, tok, ws = "", "", ""
    try:
        import re as _re
        with open(cfg_path) as f:
            raw = f.read()
        clean = _re.sub(r"^\s*//.*$", "", raw, flags=_re.MULTILINE)
        cfg = json.loads(clean)
        acct = cfg.get("channels", {}).get("nodeskclaw", {}).get("accounts", {}).get("default", {})
        api = acct.get("apiUrl", "")
        tok = acct.get("apiToken", "")
        ws = acct.get("workspaceId", "")
    except (OSError, json.JSONDecodeError, KeyError):
        pass
    return api, tok, ws


def _discover_from_hermes_context() -> tuple[str, str, str]:
    api = os.environ.get("NODESKCLAW_API_URL", "")
    tok = os.environ.get("NODESKCLAW_TOKEN", "") or os.environ.get("GATEWAY_TOKEN", "")
    ws = os.environ.get("NODESKCLAW_WORKSPACE_ID", "") or os.environ.get("DESKCLAW_WORKSPACE_ID", "")
    if ws:
        return api, tok, ws

    session_dir = os.path.expanduser("~/.hermes/sessions")
    candidates: list[str] = []
    for pattern in ("session_workspace:*.json", "request_dump_workspace:*.json"):
        candidates.extend(glob.glob(os.path.join(session_dir, pattern)))
    candidates.sort(key=lambda path: os.path.getmtime(path), reverse=True)
    for path in candidates:
        match = re.search(r"workspace:([0-9A-Za-z_-]+)", os.path.basename(path))
        if match:
            ws = match.group(1)
            break
    return api, tok, ws


_oc_api, _oc_tok, _oc_ws = _discover_from_openclaw_config()
_hm_api, _hm_tok, _hm_ws = _discover_from_hermes_context()

API_URL = (
    os.environ.get("DESKCLAW_API_URL")
    or os.environ.get("NODESKCLAW_API_URL")
    or _oc_api
    or _hm_api
    or "http://localhost:4510/api/v1"
)
TOKEN = os.environ.get("DESKCLAW_TOKEN") or os.environ.get("NODESKCLAW_TOKEN") or _oc_tok or _hm_tok or ""
WORKSPACE_ID = (
    os.environ.get("DESKCLAW_WORKSPACE_ID")
    or os.environ.get("NODESKCLAW_WORKSPACE_ID")
    or _oc_ws
    or _hm_ws
    or ""
)


def _ws_base() -> str:
    if not WORKSPACE_ID:
        _fatal("DESKCLAW_WORKSPACE_ID is not set")
    return f"{API_URL}/workspaces/{WORKSPACE_ID}"


def _headers() -> dict[str, str]:
    h = {"Content-Type": "application/json"}
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    return h


def api_call(method: str, path: str, body: dict | None = None, *, ws: bool = True) -> Any:
    """Make an HTTP request to the DeskClaw backend API.

    Args:
        method: HTTP method (GET, POST, PUT, PATCH, DELETE).
        path: URL path relative to workspace base (when ws=True) or API base.
        body: Optional JSON body.
        ws: If True, prepend /workspaces/{WORKSPACE_ID} to path.

    Returns:
        Parsed JSON response.
    """
    base = _ws_base() if ws else API_URL
    url = f"{base}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        try:
            err = json.loads(error_body)
        except (json.JSONDecodeError, ValueError):
            err = {"status": e.code, "detail": error_body}
        _output({"error": True, **err})
        sys.exit(1)
    except (urllib.error.URLError, OSError) as e:
        _output({"error": True, "detail": str(e)})
        sys.exit(1)


def upload_file(
    file_path: str,
    endpoint: str,
    filename: str,
    parent_path: str = "/",
    content_type: str = "application/octet-stream",
) -> Any:
    """Upload a local file via multipart/form-data POST."""
    boundary = uuid.uuid4().hex
    with open(file_path, "rb") as f:
        file_data = f.read()

    parts: list[bytes] = []
    parts.append(
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n".encode()
        + file_data
        + b"\r\n"
    )
    for name, value in [
        ("parent_path", parent_path),
        ("filename", filename),
        ("content_type", content_type),
    ]:
        parts.append(
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
            f"{value}\r\n".encode()
        )
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)

    base = _ws_base()
    url = f"{base}{endpoint}"
    headers: dict[str, str] = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else ""
        try:
            err = json.loads(error_body)
        except (json.JSONDecodeError, ValueError):
            err = {"status": e.code, "detail": error_body}
        _output({"error": True, **err})
        sys.exit(1)
    except (urllib.error.URLError, OSError) as e:
        _output({"error": True, "detail": str(e)})
        sys.exit(1)


def _output(data: Any) -> None:
    """Print JSON to stdout for agent consumption."""
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _fatal(msg: str) -> None:
    _output({"error": True, "message": msg})
    sys.exit(1)
