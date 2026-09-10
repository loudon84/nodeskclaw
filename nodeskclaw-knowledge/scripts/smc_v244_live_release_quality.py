#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

CLAIMS = ("CLM-09", "CLM-16")
LIVE_ONLY_KEYS = {
    "errors.knowledge.release_quality_snapshot_live_only",
    "errors.knowledge.snapshot_release_mismatch",
}


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


def optional_env(name: str) -> str:
    return os.environ.get(name, "").strip()


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


def release_items(payload: Any) -> list[dict[str, Any]]:
    data = unwrap(payload)
    items = data.get("items")
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    return []


def message_key_of(payload: Any) -> str | None:
    if not isinstance(payload, dict):
        return None
    key = payload.get("message_key")
    if isinstance(key, str) and key:
        return key
    error = payload.get("error")
    if isinstance(error, dict):
        nested = error.get("message_key")
        if isinstance(nested, str) and nested:
            return nested
    return None


def manifest_topology(release: dict[str, Any]) -> list[Any]:
    manifest = release.get("release_manifest")
    if not isinstance(manifest, dict):
        return []
    sets = manifest.get("knowledge_sets")
    return list(sets) if isinstance(sets, list) else []


def pick_validated_release(items: list[dict[str, Any]], preferred_id: str) -> dict[str, Any] | None:
    if preferred_id:
        for item in items:
            if str(item.get("id") or "") == preferred_id:
                return item
    for item in items:
        if item.get("status") == "validated" and item.get("quality_snapshot_id"):
            return item
    for item in items:
        if item.get("status") == "validated":
            return item
    return None


def evaluate(*, topology_unchanged: bool, live_only_rejected: bool) -> dict[str, str]:
    results = fail_all()
    if topology_unchanged and live_only_rejected:
        results["CLM-09"] = "PASS"
        results["CLM-16"] = "PASS"
    return results


def main() -> int:
    rebound = False
    rebound_set_id = ""
    headers: dict[str, str] = {}
    know = ""
    application_id = ""
    try:
        require_env("SMC_VERIFICATION_CANDIDATE_ID")
        application_id = require_env("KNOWLEDGE_LIVE_APPLICATION_ID")
        preferred_release = optional_env("KNOWLEDGE_LIVE_RELEASE_ID")
        token = login_token()
        headers = {"Authorization": f"Bearer {token}"}
        know = knowledge_base_url()
        list_status, list_payload = http_json(
            "GET",
            f"{know}/api/v2/applications/{application_id}/releases",
            headers=headers,
        )
        release = pick_validated_release(release_items(list_payload), preferred_release)
        if list_status != 200 or release is None:
            emit_result(fail_all())
            return 1
        release_id = str(release.get("id") or "")
        before_status, before_payload = http_json(
            "GET",
            f"{know}/api/v2/applications/{application_id}/releases/{release_id}",
            headers=headers,
        )
        before = unwrap(before_payload)
        topology_before = manifest_topology(before)
        app_status, app_payload = http_json(
            "GET",
            f"{know}/api/v2/applications/{application_id}",
            headers=headers,
        )
        app_data = unwrap(app_payload)
        live_sets = app_data.get("knowledge_set_ids") if isinstance(app_data.get("knowledge_set_ids"), list) else []
        if app_status == 200 and live_sets:
            rebound_set_id = str(live_sets[-1] or "")
            if rebound_set_id:
                unbind_status, _unbind = http_json(
                    "DELETE",
                    f"{know}/api/v2/applications/{application_id}/knowledge-sets/{rebound_set_id}",
                    headers=headers,
                )
                rebound = unbind_status < 400
        after_status, after_payload = http_json(
            "GET",
            f"{know}/api/v2/applications/{application_id}/releases/{release_id}",
            headers=headers,
        )
        after = unwrap(after_payload)
        topology_unchanged = (
            before_status == 200
            and after_status == 200
            and topology_before == manifest_topology(after)
        )
        promote_status, promote_payload = http_json(
            "POST",
            f"{know}/api/v2/applications/{application_id}/channels/stable/promote",
            headers=headers,
            body={"release_id": release_id},
        )
        live_only_rejected = promote_status >= 400 and message_key_of(promote_payload) in LIVE_ONLY_KEYS
        results = evaluate(topology_unchanged=topology_unchanged, live_only_rejected=live_only_rejected)
        emit_result(results)
        return 0 if all(results[cid] == "PASS" for cid in CLAIMS) else 1
    except Exception:
        emit_result(fail_all())
        return 1
    finally:
        if rebound and rebound_set_id and headers and know and application_id:
            http_json(
                "POST",
                f"{know}/api/v2/applications/{application_id}/knowledge-sets",
                headers=headers,
                body={"knowledge_set_id": rebound_set_id},
            )


if __name__ == "__main__":
    raise SystemExit(main())
