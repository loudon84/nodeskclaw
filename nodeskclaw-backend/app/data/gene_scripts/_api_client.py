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


def _api_call_raw(
    method: str,
    path: str,
    *,
    data: Any,
    headers: dict[str, str],
    ws: bool = True,
) -> Any:
    base = _ws_base() if ws else API_URL
    url = f"{base}{path}"
    merged_headers = dict(headers)
    if TOKEN:
        merged_headers["Authorization"] = f"Bearer {TOKEN}"
    req = urllib.request.Request(url, data=data, headers=merged_headers, method=method)
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
    body = _MultipartUploadBody(
        file_path=file_path,
        boundary=boundary,
        filename=filename,
        parent_path=parent_path,
        content_type=content_type,
    )

    base = _ws_base()
    url = f"{base}{endpoint}"
    headers: dict[str, str] = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
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
    finally:
        body.close()


def upload_shared_file(
    file_path: str,
    filename: str,
    parent_path: str = "/",
    content_type: str = "application/octet-stream",
) -> Any:
    policy = api_call("GET", "/upload/policy", ws=False).get("data") or {}
    shared_policy = (policy.get("surfaces") or {}).get("shared_file") or {}
    threshold = int(shared_policy.get("chunked_upload_threshold_bytes") or 50 * 1024 * 1024)
    if os.path.getsize(file_path) >= threshold:
        return upload_shared_file_session(file_path, filename, parent_path, content_type)
    return upload_file(file_path, "/blackboard/files/upload-multipart", filename, parent_path, content_type)


def upload_shared_file_session(
    file_path: str,
    filename: str,
    parent_path: str = "/",
    content_type: str = "application/octet-stream",
) -> Any:
    size = os.path.getsize(file_path)
    mtime_ns = os.stat(file_path).st_mtime_ns
    create = api_call("POST", "/uploads/sessions", {
        "surface": "shared_file",
        "filename": filename,
        "content_type": content_type,
        "expected_size": size,
        "parent_path": parent_path,
        "purpose": "workspace_shared_file",
        "conflict_strategy": "keep_both",
        "client_request_id": f"agent:{filename}:{size}:{mtime_ns}",
    })
    session = create.get("data") or {}
    session_id = session["session_id"]
    part_size = int(session["part_size_bytes"])
    part_count = int(session["part_count"])
    parts: list[dict[str, Any]] = []

    for part_number in range(1, part_count + 1):
        offset = (part_number - 1) * part_size
        length = min(part_size, size - offset)
        body = _FileSliceBody(file_path, offset, length)
        try:
            result = _api_call_raw(
                "PUT",
                f"/uploads/sessions/{session_id}/parts/{part_number}",
                data=body,
                headers={
                    "Content-Type": "application/octet-stream",
                    "Content-Length": str(len(body)),
                },
            )
        finally:
            body.close()
        part = (result.get("data") or {}).get("part") or {}
        parts.append({
            "part_number": part["part_number"],
            "size": part["size"],
            "checksum": part["checksum"],
            "etag": part["etag"],
        })

    return api_call("POST", f"/uploads/sessions/{session_id}/complete", {"parts": parts})


class _FileSliceBody:
    def __init__(self, file_path: str, offset: int, length: int) -> None:
        self._file = open(file_path, "rb")
        self._file.seek(offset)
        self._remaining = length
        self._length = length

    def __len__(self) -> int:
        return self._length

    def read(self, size: int = -1) -> bytes:
        if self._remaining <= 0:
            return b""
        if size is None or size < 0 or size > self._remaining:
            size = self._remaining
        chunk = self._file.read(size)
        self._remaining -= len(chunk)
        return chunk

    def close(self) -> None:
        self._file.close()


class _MultipartUploadBody:
    def __init__(
        self,
        *,
        file_path: str,
        boundary: str,
        filename: str,
        parent_path: str,
        content_type: str,
    ) -> None:
        safe_filename = filename.replace('"', '\\"')
        self._file_path = file_path
        self._segments: list[bytes | str] = [
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{safe_filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode(),
            file_path,
            b"\r\n",
        ]
        for name, value in [
            ("parent_path", parent_path),
            ("filename", filename),
            ("content_type", content_type),
        ]:
            self._segments.append(
                (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
                    f"{value}\r\n"
                ).encode()
            )
        self._segments.append(f"--{boundary}--\r\n".encode())
        self._length = sum(
            os.path.getsize(segment) if isinstance(segment, str) else len(segment)
            for segment in self._segments
        )
        self._index = 0
        self._offset = 0
        self._file = None

    def __len__(self) -> int:
        return self._length

    def read(self, size: int = -1) -> bytes:
        if size is None or size < 0:
            size = 64 * 1024
        out = bytearray()
        while len(out) < size and self._index < len(self._segments):
            segment = self._segments[self._index]
            if isinstance(segment, bytes):
                chunk = segment[self._offset:self._offset + (size - len(out))]
                out.extend(chunk)
                self._offset += len(chunk)
                if self._offset >= len(segment):
                    self._index += 1
                    self._offset = 0
                continue

            if self._file is None:
                self._file = open(self._file_path, "rb")
            chunk = self._file.read(size - len(out))
            if chunk:
                out.extend(chunk)
                continue
            self._file.close()
            self._file = None
            self._index += 1
            self._offset = 0
        return bytes(out)

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None


def _output(data: Any) -> None:
    """Print JSON to stdout for agent consumption."""
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _fatal(msg: str) -> None:
    _output({"error": True, "message": msg})
    sys.exit(1)
