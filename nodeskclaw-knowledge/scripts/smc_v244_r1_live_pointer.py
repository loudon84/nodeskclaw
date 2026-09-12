#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PLAN_ID = "knowledge-v2.4.4-r1-retrieval-runtime-closure"
FAKE_RELEASE_ID = "00000000-0000-0000-0000-000000000000"


def emit_result(results: dict[str, str]) -> None:
    payload = {"claims": {cid: {"result": results[cid]} for cid in results}}
    print("SMC_ACCEPTANCE_RESULT " + json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


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
    account = os.environ.get("KNOWLEDGE_LIVE_USERNAME", "").strip() or require_env("BACKEND_ACCOUNT")
    password = os.environ.get("KNOWLEDGE_LIVE_PASSWORD", "").strip() or require_env("BACKEND_PASSWORD")
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


def require_v07_pass() -> None:
    path = Path(__file__).resolve().parents[2] / ".smc" / "runs" / PLAN_ID / "v07-pass.json"
    if not path.is_file():
        raise RuntimeError("V07 gate missing: run smc_v244_r1_live_indexes.py first")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("result") != "PASS":
        raise RuntimeError("V07 gate is not PASS")


def message_key_of(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    return payload.get("message_key") or (payload.get("error") or {}).get("message_key")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", choices=("conflict", "stable"), required=True)
    args = parser.parse_args()
    primary = "CLM-02" if args.case == "conflict" else "CLM-03"
    claim_ids = (primary, "CLM-12", "CLM-14")

    def fail_all() -> dict[str, str]:
        return {cid: "FAIL" for cid in claim_ids}

    try:
        require_env("SMC_VERIFICATION_CANDIDATE_ID")
        require_v07_pass()
        application_id = require_env("KNOWLEDGE_LIVE_APPLICATION_ID")
        token = login_token()
        headers = {"Authorization": f"Bearer {token}"}
        know = knowledge_base_url()
        if args.case == "conflict":
            status, payload = http_json(
                "POST",
                f"{know}/api/v2/agent/tools/knowledge.search",
                headers=headers,
                body={
                    "query": "smc v244 r1 pointer conflict",
                    "application_id": application_id,
                    "channel": "stable",
                    "release_id": FAKE_RELEASE_ID,
                },
            )
            ok = status == 400 and message_key_of(payload) == "errors.knowledge.release_id_conflict"
        else:
            status, _payload = http_json(
                "POST",
                f"{know}/api/v2/agent/tools/knowledge.search",
                headers=headers,
                body={
                    "query": "smc v244 r1 pointer stable",
                    "application_id": application_id,
                    "channel": "stable",
                },
            )
            ok = status == 200
        results = fail_all()
        if ok:
            for cid in claim_ids:
                results[cid] = "PASS"
        emit_result(results)
        return 0 if ok else 1
    except Exception:
        emit_result(fail_all())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
