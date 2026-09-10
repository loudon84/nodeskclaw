#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CLAIMS = ("CLM-08",)


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


def evaluate(conflict_status: int, conflict_payload: Any, pointer_status: int) -> dict[str, str]:
    results = fail_all()
    message_key = None
    if isinstance(conflict_payload, dict):
        message_key = conflict_payload.get("message_key") or (conflict_payload.get("error") or {}).get("message_key")
    conflict_closed = conflict_status >= 400 and (
        message_key == "errors.knowledge.release_id_conflict" or conflict_status in {400, 409, 422}
    )
    pointer_ok = pointer_status == 200
    if conflict_closed and pointer_ok:
        results["CLM-08"] = "PASS"
    return results


def main() -> int:
    try:
        require_env("SMC_VERIFICATION_CANDIDATE_ID")
        application_id = require_env("KNOWLEDGE_LIVE_APPLICATION_ID")
        token = login_token()
        headers = {"Authorization": f"Bearer {token}"}
        know = knowledge_base_url()
        conflict_status, conflict_payload = http_json(
            "POST",
            f"{know}/api/v2/agent/tools/knowledge.search",
            headers=headers,
            body={
                "query": "smc v244 pointer conflict",
                "application_id": application_id,
                "channel": "stable",
                "release_id": "00000000-0000-0000-0000-000000000000",
            },
        )
        pointer_status, _pointer_payload = http_json(
            "POST",
            f"{know}/api/v2/agent/tools/knowledge.search",
            headers=headers,
            body={
                "query": "smc v244 pointer wins",
                "application_id": application_id,
                "channel": "stable",
            },
        )
        results = evaluate(conflict_status, conflict_payload, pointer_status)
        emit_result(results)
        return 0 if all(results[cid] == "PASS" for cid in CLAIMS) else 1
    except Exception:
        emit_result(fail_all())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
