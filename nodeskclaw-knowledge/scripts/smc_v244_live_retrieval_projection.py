#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CLAIMS = ("CLM-11", "CLM-16")
FORBIDDEN_KEYS = {"dataset_id", "document_id", "chunk_id"}
FORBIDDEN_PREFIX = "ragflow_"
METRIC_KEYS = {"ragflow_ms", "ragflow_call_count"}


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


def unwrap(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    data = payload.get("data")
    return data if isinstance(data, dict) else {}


def leaks_provider_ids(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            if key_text in FORBIDDEN_KEYS:
                return True
            if key_text.startswith(FORBIDDEN_PREFIX) and key_text not in METRIC_KEYS:
                return True
            if leaks_provider_ids(item):
                return True
    elif isinstance(value, list):
        return any(leaks_provider_ids(item) for item in value)
    return False


def has_evidence_id(payload: dict[str, Any]) -> bool:
    chunks = payload.get("chunks")
    if isinstance(chunks, list) and chunks:
        first = chunks[0]
        return isinstance(first, dict) and bool(first.get("evidence_id"))
    evidence = payload.get("evidence")
    if isinstance(evidence, list) and evidence:
        first = evidence[0]
        return isinstance(first, dict) and bool(first.get("evidence_id"))
    return payload.get("status") in {"empty", "success", "degraded"}


def evaluate(v2_status: int, v2_payload: Any, agent_status: int, agent_payload: Any) -> dict[str, str]:
    results = fail_all()
    v2_data = unwrap(v2_payload)
    agent_data = unwrap(agent_payload)
    v2_ok = v2_status == 200 and has_evidence_id(v2_data) and not leaks_provider_ids(v2_data)
    agent_ok = agent_status == 200 and has_evidence_id(agent_data) and not leaks_provider_ids(agent_data)
    if v2_ok and agent_ok:
        results["CLM-11"] = "PASS"
        results["CLM-16"] = "PASS"
    return results


def main() -> int:
    try:
        require_env("SMC_VERIFICATION_CANDIDATE_ID")
        application_id = require_env("KNOWLEDGE_LIVE_APPLICATION_ID")
        token = login_token()
        headers = {"Authorization": f"Bearer {token}"}
        know = knowledge_base_url()
        v2_status, v2_payload = http_json(
            "POST",
            f"{know}/api/v2/applications/{application_id}/retrieval",
            headers=headers,
            body={"query": "smc v244 retrieval projection"},
        )
        agent_status, agent_payload = http_json(
            "POST",
            f"{know}/api/v2/agent/tools/knowledge.search",
            headers=headers,
            body={"query": "smc v244 retrieval projection", "application_id": application_id, "channel": "stable"},
        )
        results = evaluate(v2_status, v2_payload, agent_status, agent_payload)
        emit_result(results)
        return 0 if all(results[cid] == "PASS" for cid in CLAIMS) else 1
    except Exception:
        emit_result(fail_all())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
