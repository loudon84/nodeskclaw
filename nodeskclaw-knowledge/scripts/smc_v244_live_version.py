#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CLAIMS = ("CLM-01",)
VERSION_PATHS = ("/v2/system/version", "/api/v1/system/version", "/v1/system/version")


def emit_result(results: dict[str, str]) -> None:
    payload = {"claims": {cid: {"result": results[cid]} for cid in CLAIMS}}
    print("SMC_ACCEPTANCE_RESULT " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def fail_all() -> dict[str, str]:
    return {cid: "FAIL" for cid in CLAIMS}


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"missing env {name}")
    return value


def knowledge_base_url() -> str:
    port = os.environ.get("KNOWLEDGE_PORT", "4530").strip() or "4530"
    return f"http://127.0.0.1:{port}".rstrip("/")


def http_json(method: str, url: str, *, headers: dict[str, str] | None = None, body: dict[str, Any] | None = None) -> tuple[int, Any]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = Request(url, data=data, method=method)
    request.add_header("Accept", "application/json")
    if body is not None:
        request.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8", errors="replace")
            status = response.status
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        status = exc.code
    except URLError as exc:
        raise RuntimeError(f"request failed {url}: {exc.reason}") from exc
    if not raw:
        return status, None
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"non-json response {url} http={status}") from exc


def extract_version(payload: Any) -> str | None:
    if isinstance(payload, dict):
        data = payload.get("data") if payload.get("code", 0) == 0 else payload
        if isinstance(data, dict):
            for key in ("version", "ragflow_version", "release"):
                value = data.get(key)
                if value:
                    return str(value)
        elif data:
            return str(data)
    return None


def evaluate(
    attempted: list[str],
    version: str | None,
    ready_status: int,
    ready_payload: Any,
) -> dict[str, str]:
    results = fail_all()
    v2_first = bool(attempted) and attempted[0] == "/v2/system/version"
    ready_ok = ready_status == 200 and isinstance(ready_payload, dict)
    if v2_first and version and ready_ok:
        results["CLM-01"] = "PASS"
    return results


def probe_version(ragflow: str, api_key: str) -> tuple[list[str], str | None]:
    attempted: list[str] = []
    headers = {"Authorization": f"Bearer {api_key}"}
    for path in VERSION_PATHS:
        attempted.append(path)
        status, payload = http_json("GET", f"{ragflow}{path}", headers=headers)
        if status >= 400:
            continue
        version = extract_version(payload)
        if version:
            return attempted, version
    return attempted, None


def main() -> int:
    try:
        require_env("SMC_VERIFICATION_CANDIDATE_ID")
        require_env("KNOWLEDGE_LIVE_KB_ID")
        ragflow = require_env("RAGFLOW_BASE_URL").rstrip("/")
        api_key = require_env("RAGFLOW_API_KEY")
        attempted, version = probe_version(ragflow, api_key)
        ready_status, ready_payload = http_json("GET", f"{knowledge_base_url()}/health/ready")
        results = evaluate(attempted, version, ready_status, ready_payload)
        emit_result(results)
        return 0 if all(results[cid] == "PASS" for cid in CLAIMS) else 1
    except Exception:
        emit_result(fail_all())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
