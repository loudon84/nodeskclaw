#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CLAIMS = ("CLM-01", "CLM-02", "CLM-04", "CLM-07", "CLM-08")
CHUNK_UNAVAILABLE = (
    "runtime_chunk_unavailable",
    "runtime_chunk_retrieval_unavailable",
)


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


def login_token() -> str:
    backend = require_env("NODESKCLAW_BACKEND_URL").rstrip("/")
    account = require_env("BACKEND_ACCOUNT")
    password = require_env("BACKEND_PASSWORD")
    status, payload = http_json(
        "POST",
        f"{backend}/api/v1/auth/account-login",
        body={"account": account, "password": password},
    )
    if status != 200 or not isinstance(payload, dict):
        raise RuntimeError(f"account-login http={status}")
    token = ((payload.get("data") or {}) if isinstance(payload.get("data"), dict) else {}).get("access_token")
    if not token:
        raise RuntimeError("account-login missing access_token")
    return str(token)


def chunk_index(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    chunk = data.get("chunk")
    return chunk if isinstance(chunk, dict) else None


def blocking_codes(payload: Any) -> list[str]:
    if not isinstance(payload, dict):
        return []
    data = payload.get("data")
    if not isinstance(data, dict):
        return []
    blocking = data.get("blocking") or []
    codes: list[str] = []
    if isinstance(blocking, list):
        for item in blocking:
            if isinstance(item, dict) and item.get("code"):
                codes.append(str(item["code"]))
    return codes


def evaluate(indexes: dict[str, Any] | None, codes: list[str]) -> dict[str, str]:
    results = fail_all()
    build_status = (indexes or {}).get("build_status")
    retrieval_status = (indexes or {}).get("retrieval_status")
    chunk_ready = build_status == "ready" and retrieval_status == "ready"
    not_unsupported = retrieval_status != "unsupported"
    readiness_ok = all(code not in codes for code in CHUNK_UNAVAILABLE)
    if chunk_ready:
        results["CLM-01"] = "PASS"
        results["CLM-02"] = "PASS"
    if chunk_ready and readiness_ok:
        results["CLM-04"] = "PASS"
    if not_unsupported and retrieval_status is not None:
        results["CLM-08"] = "PASS"
    if all(results[cid] == "PASS" for cid in ("CLM-01", "CLM-02", "CLM-04", "CLM-08")):
        results["CLM-07"] = "PASS"
    return results


def main() -> int:
    try:
        kb_id = require_env("KNOWLEDGE_LIVE_KB_ID")
        application_id = require_env("KNOWLEDGE_LIVE_APPLICATION_ID")
        token = login_token()
        headers = {"Authorization": f"Bearer {token}"}
        know = knowledge_base_url()
        indexes_status, indexes_payload = http_json(
            "GET",
            f"{know}/api/v2/knowledge-bases/{kb_id}/indexes",
            headers=headers,
        )
        ready_status, ready_payload = http_json(
            "GET",
            f"{know}/api/v2/applications/{application_id}/readiness",
            headers=headers,
        )
        if indexes_status != 200 or ready_status != 200:
            results = fail_all()
            emit_result(results)
            return 1
        results = evaluate(chunk_index(indexes_payload), blocking_codes(ready_payload))
        emit_result(results)
        return 0 if all(results[cid] == "PASS" for cid in CLAIMS) else 1
    except Exception:
        emit_result(fail_all())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
