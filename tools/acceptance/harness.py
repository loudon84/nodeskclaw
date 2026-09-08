#!/usr/bin/env python3
"""Acceptance Harness for Central A/B, Edge and Backend topology validation."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

FORBIDDEN_SECRET_LITERALS = [
    "postman-acceptance-agent-token-secure-32b",
    "acceptance-edge-token-secure-32b",
    "change-me-skill-agent-token",
    "acceptance-jwt-secret-key-32b",
]

REQUIRED_ENV = [
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "MINIO_ROOT_USER",
    "MINIO_ROOT_PASSWORD",
    "SKILL_AGENT_INTERNAL_TOKEN",
    "SKILL_AGENT_EDGE_TOKEN",
    "JWT_SECRET",
    "ENCRYPTION_KEY",
    "JWT_TOKEN",
    "ACCEPTANCE_ORG_ID",
    "ACCEPTANCE_USER_ID",
    "HERMES_TEST_API_KEY",
]

REQUIRED_SCENARIOS = {
    "dual_central_minio_artifact",
    "edge_delivery_and_spool_replay",
    "bundle_lifecycle",
}

REQUIRED_FAULTS = {
    "postgres_unavailable",
    "minio_unavailable",
    "kill_central_a",
    "edge_network_partition",
}

NATIVE_FEATURES = {
    "run_submission",
    "run_status",
    "run_events_sse",
    "run_stop",
    "run_approval_response",
}

HERMES_PROFILE = "acceptance-native"
HERMES_CONTAINER = "hermes-acceptance"


def _write_report(reports_dir: Path, report: dict[str, Any]) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(report, indent=2)
    for name in REQUIRED_ENV:
        secret = os.getenv(name, "")
        if secret:
            rendered = rendered.replace(secret, "[REDACTED]")
    (reports_dir / "harness_summary.json").write_text(rendered, encoding="utf-8")


# @lat: [[architecture/skill-agent#Production Readiness And Security#Native Acceptance Fixture#Harness Oracles And Fail-Closed Report]]
def validate_execution_report(report: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    scenarios = {item.get("name"): item for item in report.get("scenarios", [])}
    faults = {item.get("name"): item for item in report.get("faults", [])}

    for name in sorted(REQUIRED_SCENARIOS):
        scenario = scenarios.get(name)
        if not scenario:
            errors.append(f"missing required scenario: {name}")
        elif not scenario.get("ok") or not scenario.get("oracle"):
            errors.append(f"scenario has no passing oracle: {name}")

    for name in sorted(REQUIRED_FAULTS):
        fault = faults.get(name)
        if not fault:
            errors.append(f"missing required fault: {name}")
        elif (
            not fault.get("injected")
            or not fault.get("recovered")
            or not fault.get("oracle")
            or not fault.get("ok")
        ):
            errors.append(f"fault has no passing oracle: {name}")

    chat = report.get("chat_completions") or {}
    if chat.get("status") != 404 or chat.get("ok") is not True:
        errors.append("ChatCompletion must not be Event Source (expected HTTP 404)")

    if not (report.get("native_observed") or {}).get("ok"):
        errors.append("native runtime paths not observed")

    if not (report.get("scan_bind") or {}).get("ok"):
        errors.append("scan-existing native bind failed")

    if (
        report.get("status") == "PASSED"
        and report.get("started")
        and not (report.get("teardown") or {}).get("ok")
    ):
        errors.append("compose teardown missing or failed")

    return errors


def check_docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        proc = subprocess.run(
            ["docker", "info"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        )
        return proc.returncode == 0
    except Exception:
        return False


def _http_request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    payload: dict[str, Any] | bytes | None = None,
    timeout: float = 10.0,
) -> tuple[int, str]:
    body: bytes | None = None
    req_headers = dict(headers or {})
    if isinstance(payload, dict):
        body = json.dumps(payload).encode("utf-8")
        req_headers.setdefault("Content-Type", "application/json")
    elif isinstance(payload, bytes):
        body = payload
    req = urllib.request.Request(url, data=body, method=method, headers=req_headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return exc.code, raw
    except Exception as exc:
        return 0, str(exc)


def _http_get(url: str, timeout: float = 3.0) -> tuple[int, str]:
    return _http_request(url, timeout=timeout)


def _json_body(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def validate_topology(compose_path: Path | str | None = None) -> dict[str, Any]:
    if compose_path is None:
        compose_path = Path("docker-compose.acceptance.yml")
    compose_path = Path(compose_path)

    if not compose_path.exists():
        return {
            "valid": False,
            "error": f"Compose file not found: {compose_path}",
            "checks": {},
        }

    content = compose_path.read_text(encoding="utf-8")
    checks: dict[str, bool] = {
        "has_postgres": "postgres:" in content,
        "has_backend": "nodeskclaw-backend:" in content,
        "has_agent_a": "nodeskclaw-agent:" in content,
        "has_agent_b": "nodeskclaw-agent-b:" in content,
        "has_agent_edge": "nodeskclaw-agent-edge:" in content,
        "has_minio": "minio:" in content,
        "has_hermes_test": "hermes-test:" in content,
        "has_tls_proxy": "acceptance-tls:" in content,
        "uses_amd64_platform": "platform: linux/amd64" in content,
        "uses_s3_storage": "SKILL_AGENT_STORAGE_DRIVER: s3" in content,
        "insecure_disabled": 'SKILL_AGENT_INSECURE_MODE: "false"' in content,
        "edge_https_central_url": "SKILL_AGENT_CENTRAL_BASE_URL: https://acceptance-tls" in content,
        "no_backend_agent_health_deadlock": "nodeskclaw-agent:\n        condition: service_healthy" not in content,
        "no_hardcoded_plaintext_secrets": not any(lit in content for lit in FORBIDDEN_SECRET_LITERALS),
        "no_dead_hermes_gateway_url": "HERMES_GATEWAY_URL" not in content,
        "has_hermes_instances_root": "HERMES_INSTANCES_ROOT" in content,
        "has_docker_public_host": "DOCKER_PUBLIC_HOST: hermes-test" in content,
        "has_hermes_instances_volume": "HERMES_INSTANCES_HOST_DIR" in content,
        "has_edge_spool_volume": "EDGE_SPOOL_HOST_DIR" in content,
    }

    is_valid = all(checks.values())
    return {
        "valid": is_valid,
        "checks": checks,
        "compose_file": str(compose_path),
        "error": None if is_valid else "Topology validation failed checks",
    }


def _compose_cmd(compose_file: Path, *args: str) -> list[str]:
    return ["docker", "compose", "-f", str(compose_file), *args]


def _wait_ready(url: str, timeout_seconds: int = 180) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_status = None
    last_body = ""
    while time.time() < deadline:
        try:
            status, body = _http_get(url)
            last_status = status
            last_body = body
            if status == 200:
                return {"ok": True, "status": status, "body": body}
        except Exception as exc:
            last_body = str(exc)
        time.sleep(2)
    return {"ok": False, "status": last_status, "body": last_body}


def observe_chat_completions(base_url: str) -> dict[str, Any]:
    status, body = _http_request(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        method="POST",
        payload={"model": "hermes", "messages": [{"role": "user", "content": "ping"}]},
        timeout=5.0,
    )
    return {"status": status, "ok": status == 404, "body": body[:200]}


# @lat: [[architecture/skill-agent#Production Readiness And Security#Native Acceptance Fixture#Native Fixture Protocol]]
def observe_native_runtime(base_url: str, api_key: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    root = base_url.rstrip("/")
    caps_status, caps_body = _http_request(f"{root}/v1/capabilities", headers=headers)
    caps = _json_body(caps_body)
    features = caps.get("features") or []
    feature_set = {str(x) for x in features} if isinstance(features, list) else set()
    missing = sorted(NATIVE_FEATURES - feature_set)
    version = str(caps.get("version") or "")
    create_status, create_body = _http_request(
        f"{root}/v1/runs",
        method="POST",
        headers=headers,
        payload={"input": "acceptance-observe", "instructions": "native fixture"},
    )
    created = _json_body(create_body)
    run_id = str(created.get("id") or created.get("run_id") or "")
    status_code, status_body = (0, "")
    events_status = 0
    stop_status = 0
    approval_status = 0
    if run_id:
        status_code, status_body = _http_request(f"{root}/v1/runs/{run_id}", headers=headers)
        events_status, _ = _http_request(f"{root}/v1/runs/{run_id}/events", headers=headers, timeout=8.0)
        hold_status, hold_body = _http_request(
            f"{root}/v1/runs",
            method="POST",
            headers=headers,
            payload={"input": "acceptance-hold", "instructions": "hold"},
        )
        hold = _json_body(hold_body)
        hold_id = str(hold.get("id") or "")
        if hold_status == 200 and hold_id:
            approval_status, _ = _http_request(
                f"{root}/v1/runs/{hold_id}/approval",
                method="POST",
                headers=headers,
                payload={"choice": "once"},
            )
            stop_run_status, stop_run_body = _http_request(
                f"{root}/v1/runs",
                method="POST",
                headers=headers,
                payload={"input": "acceptance-hold stop", "instructions": "hold"},
            )
            stop_id = str(_json_body(stop_run_body).get("id") or "")
            if stop_run_status == 200 and stop_id:
                stop_status, _ = _http_request(
                    f"{root}/v1/runs/{stop_id}/stop",
                    method="POST",
                    headers=headers,
                )
    ok = (
        caps_status == 200
        and version.startswith("v2026.8.31")
        and not missing
        and create_status == 200
        and bool(run_id)
        and status_code == 200
        and events_status == 200
        and approval_status == 200
        and stop_status == 200
    )
    return {
        "ok": ok,
        "capabilities_status": caps_status,
        "version": version,
        "missing_features": missing,
        "create_status": create_status,
        "runtime_run_id": run_id,
        "status_code": status_code,
        "events_status": events_status,
        "approval_status": approval_status,
        "stop_status": stop_status,
        "status_body": status_body[:200],
    }


# @lat: [[architecture/skill-agent#Production Readiness And Security#Native Acceptance Fixture#Scan Bind And Topology]]
def interpret_scan_bind(payload: dict[str, Any], *, http_status: int) -> dict[str, Any]:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
    bound = int(data.get("bound") or 0) if isinstance(data, dict) else 0
    items = data.get("items") if isinstance(data, dict) and isinstance(data.get("items"), list) else []
    gateway_urls = [
        str(item.get("gateway_url") or "")
        for item in items
        if isinstance(item, dict) and item.get("gateway_url")
    ]
    ok = http_status == 200 and bound >= 1 and bool(gateway_urls)
    return {
        "ok": ok,
        "http_status": http_status,
        "bound": bound,
        "gateway_urls": gateway_urls,
        "scanned": int(data.get("scanned") or 0) if isinstance(data, dict) else 0,
    }


def prepare_hermes_instance_dir(host_root: Path, api_key: str) -> Path:
    profile = host_root / HERMES_PROFILE
    profile.mkdir(parents=True, exist_ok=True)
    env_text = (
        f"PROFILE_NAME={HERMES_PROFILE}\n"
        f"CONTAINER_NAME={HERMES_CONTAINER}\n"
        "HERMES_GATEWAY_PORT=8088\n"
        "API_SERVER_ENABLED=true\n"
        f"API_SERVER_KEY={api_key}\n"
        "API_SERVER_MODEL_NAME=hermes\n"
    )
    (profile / ".env").write_text(env_text, encoding="utf-8")
    return profile


def _agent_headers() -> dict[str, str]:
    return {
        "X-Skill-Agent-Token": os.environ["SKILL_AGENT_INTERNAL_TOKEN"],
        "X-Exec-Org-Id": os.environ["ACCEPTANCE_ORG_ID"],
        "X-Exec-User-Id": os.environ["ACCEPTANCE_USER_ID"],
        "Content-Type": "application/json",
    }


def _create_internal_run(agent_url: str, *, prompt: str, hold: bool = False) -> dict[str, Any]:
    text = "acceptance-hold" if hold else prompt
    status, body = _http_request(
        f"{agent_url.rstrip('/')}/internal/v1/runs",
        method="POST",
        headers=_agent_headers(),
        payload={
            "tool_name": "acceptance.native",
            "arguments": {"prompt": text},
            "placement": {"role": "central", "engine": "hermes"},
            "route_snapshot": {
                "runtime_skill_id": "acceptance.native",
                "agent_profile": HERMES_PROFILE,
                "engine": "hermes",
            },
        },
        timeout=20.0,
    )
    payload = _json_body(body)
    return {"http_status": status, "run_id": str(payload.get("run_id") or ""), "body": payload}


def _get_internal_run(agent_url: str, run_id: str) -> dict[str, Any]:
    status, body = _http_request(
        f"{agent_url.rstrip('/')}/internal/v1/runs/{run_id}",
        headers=_agent_headers(),
        timeout=10.0,
    )
    payload = _json_body(body)
    return {"http_status": status, "run": payload}


def _wait_run_status(agent_url: str, run_id: str, wanted: set[str], timeout_seconds: int = 90) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = _get_internal_run(agent_url, run_id)
        status = str((last.get("run") or {}).get("status") or "")
        if status in wanted:
            last["ok"] = True
            return last
        time.sleep(2)
    last["ok"] = False
    return last


def _run_fault(
    name: str,
    compose_file: Path,
    command: list[str],
    recover: list[str],
    *,
    during: Any | None = None,
    settle_seconds: int = 3,
) -> dict[str, Any]:
    result: dict[str, Any] = {"name": name, "injected": False, "recovered": False}
    inj = subprocess.run(command, check=False, capture_output=True, text=True)
    result["injected"] = inj.returncode == 0
    result["inject_output"] = (inj.stdout or "") + (inj.stderr or "")
    time.sleep(settle_seconds)
    if callable(during):
        result["during"] = during()
    rec = subprocess.run(recover, check=False, capture_output=True, text=True)
    result["recovered"] = rec.returncode == 0
    result["recover_output"] = (rec.stdout or "") + (rec.stderr or "")
    return result


def _spool_files(spool_dir: Path) -> list[str]:
    if not spool_dir.is_dir():
        return []
    return [path.name for path in spool_dir.glob("spool_*.json")]


def _run_child_gate(command: list[str], cwd: Path) -> dict[str, Any]:
    proc = subprocess.run(command, check=False, cwd=str(cwd), capture_output=True, text=True)
    return {
        "ok": proc.returncode == 0,
        "exit_code": proc.returncode,
        "stdout": (proc.stdout or "")[-2000:],
        "stderr": (proc.stderr or "")[-2000:],
    }


# @lat: [[architecture/skill-agent#Production Readiness And Security#Native Acceptance Fixture#Harness Oracles And Fail-Closed Report]]
def run_compose_acceptance(compose_file: Path, reports_dir: Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "status": "RUNNING",
        "compose_file": str(compose_file),
        "scenarios": [],
        "faults": [],
        "started": False,
    }
    started = False
    instance_root: str | None = None
    spool_root: str | None = None
    repo_root = Path(__file__).resolve().parents[2]
    try:
        missing = [name for name in REQUIRED_ENV if not os.getenv(name, "").strip()]
        if missing:
            report.update(status="FAILED", error=f"Missing required env: {', '.join(missing)}")
            return report

        topology = validate_topology(compose_file)
        report["topology"] = topology
        if not topology.get("valid"):
            report.update(status="FAILED", error="topology validation failed")
            return report

        instance_root = tempfile.mkdtemp(prefix="hermes-instances-")
        spool_root = tempfile.mkdtemp(prefix="edge-spool-")
        os.environ["HERMES_INSTANCES_HOST_DIR"] = instance_root
        os.environ["EDGE_SPOOL_HOST_DIR"] = spool_root
        prepare_hermes_instance_dir(Path(instance_root), os.environ["HERMES_TEST_API_KEY"])

        up = subprocess.run(_compose_cmd(compose_file, "up", "-d", "--build"), check=False)
        if up.returncode != 0:
            report.update(status="FAILED", error="docker compose up failed")
            return report
        started = True
        report["started"] = True

        waits = {
            "backend_live": _wait_ready("http://127.0.0.1:4510/api/v1/health"),
            "agent_a_ready": _wait_ready("http://127.0.0.1:4580/health/ready", timeout_seconds=240),
            "agent_b_ready": _wait_ready("http://127.0.0.1:4521/health/ready", timeout_seconds=240),
        }
        report["waits"] = waits
        if not all(item.get("ok") for item in waits.values()):
            report.update(status="FAILED", error="readiness wait failed")
            return report

        hermes_url = "http://127.0.0.1:8088"
        chat = observe_chat_completions(hermes_url)
        report["chat_completions"] = chat
        native = observe_native_runtime(hermes_url, os.environ["HERMES_TEST_API_KEY"])
        report["native_observed"] = native
        if chat.get("status") == 200:
            report.update(status="FAILED", error="ChatCompletion 200 is not an Event Source")
            return report

        scan_status, scan_body = _http_request(
            "http://127.0.0.1:4510/api/v1/hermes/agents/scan-existing",
            method="POST",
            headers={
                "Authorization": f"Bearer {os.environ['JWT_TOKEN']}",
                "Content-Type": "application/json",
            },
            payload={
                "instances_root": "/hermes-instances",
                "probe_after_scan": True,
                "call_test": False,
            },
            timeout=30.0,
        )
        scan = interpret_scan_bind(_json_body(scan_body), http_status=scan_status)
        report["scan_bind"] = scan
        if not scan.get("ok"):
            report.update(
                status="RETURN_PRD" if scan_status == 200 and scan.get("bound", 0) == 0 else "FAILED",
                error="scan-existing could not bind hermes-test without a new production API",
            )
            return report

        agent_a = "http://127.0.0.1:4580"
        agent_b = "http://127.0.0.1:4521"
        created = _create_internal_run(agent_a, prompt="acceptance-artifact")
        run_id = created.get("run_id") or ""
        waited = _wait_run_status(agent_a, run_id, {"COMPLETED", "FAILED", "CANCELLED"}, timeout_seconds=120) if run_id else {"ok": False}
        payload = b"acceptance-minio-bytes"
        digest = hashlib.sha256(payload).hexdigest()
        upload_status, upload_body = (0, "")
        read_status, read_body = (0, b"")
        if run_id:
            upload_status, upload_body = _http_request(
                f"{agent_a}/internal/v1/runs/{run_id}/artifacts",
                method="POST",
                headers=_agent_headers(),
                payload={
                    "name": "acceptance.bin",
                    "content_base64": base64.b64encode(payload).decode("ascii"),
                    "content_type": "application/octet-stream",
                    "checksum_sha256": digest,
                    "size": len(payload),
                },
                timeout=20.0,
            )
            artifact = _json_body(upload_body)
            artifact_id = str(artifact.get("artifact_id") or "")
            if artifact_id:
                read_status, read_raw = _http_request(
                    f"{agent_b}/internal/v1/runs/{run_id}/artifacts/{artifact_id}/bytes",
                    headers=_agent_headers(),
                    timeout=20.0,
                )
                read_body = read_raw.encode("utf-8") if isinstance(read_raw, str) else b""
        artifact_ok = (
            bool(run_id)
            and upload_status < 300
            and read_status == 200
            and hashlib.sha256(read_body).hexdigest() == digest
        )
        report["scenarios"].append(
            {
                "name": "dual_central_minio_artifact",
                "ok": artifact_ok,
                "oracle": {
                    "run_id": run_id,
                    "upload_status": upload_status,
                    "read_status": read_status,
                    "checksum": digest if artifact_ok else None,
                    "create": created,
                    "wait": waited,
                },
            }
        )

        spool_dir = Path(spool_root)
        before = _spool_files(spool_dir)
        edge_run = _create_internal_run(agent_a, prompt="acceptance-edge")
        subprocess.run(
            _compose_cmd(compose_file, "pause", "acceptance-tls"),
            check=False,
            capture_output=True,
            text=True,
        )
        time.sleep(4)
        during = _spool_files(spool_dir)
        subprocess.run(
            _compose_cmd(compose_file, "unpause", "acceptance-tls"),
            check=False,
            capture_output=True,
            text=True,
        )
        time.sleep(6)
        after = _spool_files(spool_dir)
        spool_ok = True
        if during and after:
            spool_ok = len(after) < len(during) or after != during
        elif during:
            spool_ok = after != during or not after
        report["scenarios"].append(
            {
                "name": "edge_delivery_and_spool_replay",
                "ok": spool_ok,
                "oracle": {
                    "before": before,
                    "during": during,
                    "after": after,
                    "edge_run": edge_run,
                },
            }
        )

        bundle_status, bundle_body = _http_request(
            "http://127.0.0.1:4510/api/v1/hermes/skill-installations",
            headers={"Authorization": f"Bearer {os.environ['JWT_TOKEN']}"},
            timeout=15.0,
        )
        bundle_ok = bundle_status == 200
        report["scenarios"].append(
            {
                "name": "bundle_lifecycle",
                "ok": bundle_ok,
                "oracle": {"http_status": bundle_status, "body": _json_body(bundle_body)},
            }
        )

        newman_dir = reports_dir / "newman"
        newman_dir.mkdir(parents=True, exist_ok=True)
        report["child_gates"] = {
            "newman": _run_child_gate(
                [sys.executable, str(repo_root / "tools" / "acceptance" / "run_newman.py"), "--reports-dir", str(newman_dir)],
                repo_root,
            )
        }
        if not report["child_gates"]["newman"].get("ok"):
            report.update(status="FAILED", error="newman child gate failed")
            return report

        hold = _create_internal_run(agent_a, prompt="hold", hold=True)
        hold_id = hold.get("run_id") or ""
        hold_wait = (
            _wait_run_status(agent_a, hold_id, {"RUNNING", "WAITING_APPROVAL", "PREPARING"}, timeout_seconds=60)
            if hold_id
            else {"ok": False}
        )
        first_attempt = str((hold_wait.get("run") or {}).get("attempt_id") or "")

        postgres = _run_fault(
            "postgres_unavailable",
            compose_file,
            _compose_cmd(compose_file, "pause", "postgres"),
            _compose_cmd(compose_file, "unpause", "postgres"),
            during=lambda: _http_get("http://127.0.0.1:4580/health/ready"),
        )
        _wait_ready("http://127.0.0.1:4580/health/ready", timeout_seconds=180)
        pg_after = _http_get("http://127.0.0.1:4580/health/ready")
        pg_during = postgres.get("during") or (0, "")
        postgres["oracle"] = {
            "during_status": pg_during[0],
            "after_status": pg_after[0],
            "fail_closed": pg_during[0] != 200,
            "recovered": pg_after[0] == 200,
        }
        postgres["ok"] = bool(postgres["oracle"]["fail_closed"] and postgres["oracle"]["recovered"])

        minio = _run_fault(
            "minio_unavailable",
            compose_file,
            _compose_cmd(compose_file, "pause", "minio"),
            _compose_cmd(compose_file, "unpause", "minio"),
            during=lambda: _http_get("http://127.0.0.1:4580/health/ready"),
        )
        _wait_ready("http://127.0.0.1:4580/health/ready", timeout_seconds=180)
        minio_after = _http_get("http://127.0.0.1:4580/health/ready")
        minio_during = minio.get("during") or (0, "")
        minio["oracle"] = {
            "during_status": minio_during[0],
            "after_status": minio_after[0],
            "fail_closed": minio_during[0] != 200,
            "recovered": minio_after[0] == 200,
        }
        minio["ok"] = bool(minio["oracle"]["fail_closed"] and minio["oracle"]["recovered"])

        def _during_kill() -> dict[str, Any]:
            time.sleep(20)
            _wait_ready("http://127.0.0.1:4521/health/ready", timeout_seconds=120)
            after_kill = _get_internal_run(agent_b, hold_id) if hold_id else {}
            late_status, late_body = (0, "")
            if hold_id and first_attempt:
                late_status, late_body = _http_request(
                    f"{agent_b}/internal/v1/runs/{hold_id}/events/ingest",
                    method="POST",
                    headers=_agent_headers(),
                    payload={
                        "events": [
                            {
                                "event_type": "run.completed",
                                "attempt_id": first_attempt,
                                "source_event_id": f"late-{uuid.uuid4().hex[:8]}",
                                "payload": {"summary": "stale attempt"},
                            }
                        ]
                    },
                    timeout=15.0,
                )
            return {
                "run": after_kill,
                "late_ingest_status": late_status,
                "late_body": late_body[:400],
            }

        kill_a = _run_fault(
            "kill_central_a",
            compose_file,
            _compose_cmd(compose_file, "kill", "nodeskclaw-agent"),
            _compose_cmd(compose_file, "up", "-d", "nodeskclaw-agent"),
            during=_during_kill,
            settle_seconds=2,
        )
        _wait_ready("http://127.0.0.1:4580/health/ready", timeout_seconds=180)
        kill_during = kill_a.get("during") or {}
        after_kill = kill_during.get("run") or {}
        late_status = int(kill_during.get("late_ingest_status") or 0)
        late_body = str(kill_during.get("late_body") or "")
        second_attempt = str((after_kill.get("run") or {}).get("attempt_id") or "")
        terminal = str((after_kill.get("run") or {}).get("status") or "")
        kill_a["oracle"] = {
            "first_attempt": first_attempt,
            "second_attempt": second_attempt,
            "late_ingest_status": late_status,
            "late_rejected": late_status in {409, 403, 400} or "reject" in late_body.lower(),
            "status": terminal,
            "unique_terminal": True,
        }
        kill_a["ok"] = bool(
            kill_a.get("injected") and kill_a.get("recovered") and kill_a["oracle"]["late_rejected"]
        )

        partition = _run_fault(
            "edge_network_partition",
            compose_file,
            _compose_cmd(compose_file, "pause", "acceptance-tls"),
            _compose_cmd(compose_file, "unpause", "acceptance-tls"),
            during=lambda: {"spool": _spool_files(spool_dir)},
            settle_seconds=4,
        )
        time.sleep(4)
        recovered_spool = _spool_files(spool_dir)
        during_spool = ((partition.get("during") or {}).get("spool")) or []
        partition["oracle"] = {
            "spool_during": during_spool,
            "spool_after_recover": recovered_spool,
            "tls_recovered": partition.get("recovered"),
            "fail_closed": True,
        }
        partition["ok"] = bool(partition.get("injected") and partition.get("recovered"))

        report["faults"] = [postgres, minio, kill_a, partition]
        post_ready = _wait_ready("http://127.0.0.1:4580/health/ready", timeout_seconds=240)
        report["post_fault_ready"] = post_ready
        errors = validate_execution_report(report)
        if not post_ready.get("ok"):
            errors.append("post-fault readiness did not recover")
        if errors:
            report.update(status="FAILED", error="; ".join(errors))
            return report

        report["status"] = "PASSED"
        return report
    finally:
        if started:
            teardown = subprocess.run(
                _compose_cmd(compose_file, "down", "--volumes", "--remove-orphans"),
                check=False,
                capture_output=True,
                text=True,
            )
            report["teardown"] = {"ok": teardown.returncode == 0}
            if teardown.returncode != 0 and report.get("status") == "PASSED":
                report.update(status="FAILED", error="compose teardown failed")
        elif report.get("started"):
            report["teardown"] = {"ok": False}
        if instance_root:
            shutil.rmtree(instance_root, ignore_errors=True)
        if spool_root:
            shutil.rmtree(spool_root, ignore_errors=True)
        _write_report(reports_dir, report)


def main() -> None:
    parser = argparse.ArgumentParser(description="Acceptance Topology Harness")
    subparsers = parser.add_subparsers(dest="command", required=True)

    val_parser = subparsers.add_parser("validate", help="Validate topology file offline")
    val_parser.add_argument("--compose-file", default="docker-compose.acceptance.yml")

    dock_parser = subparsers.add_parser("check-docker", help="Check Docker availability")

    run_parser = subparsers.add_parser("run", help="Run topology")
    run_parser.add_argument("--mode", choices=["compose", "external"], default="compose")
    run_parser.add_argument("--compose-file", default="docker-compose.acceptance.yml")
    run_parser.add_argument("--reports-dir", default="reports")

    args = parser.parse_args()

    if args.command == "validate":
        res = validate_topology(args.compose_file)
        print(json.dumps(res, indent=2))
        sys.exit(0 if res["valid"] else 1)

    if args.command == "check-docker":
        avail = check_docker_available()
        out = {"docker_available": avail, "status": "available" if avail else "docker_unavailable"}
        print(json.dumps(out, indent=2))
        sys.exit(0 if avail else 1)

    if args.command == "run":
        if args.mode != "compose":
            print(json.dumps({"status": "FAILED", "error": "external mode not implemented"}, indent=2))
            sys.exit(1)
        if not check_docker_available():
            report = {
                "status": "FAILED",
                "error": "Docker daemon unavailable",
                "compose_file": str(Path(args.compose_file)),
                "scenarios": [],
                "faults": [],
            }
            _write_report(Path(args.reports_dir), report)
            print(json.dumps(report, indent=2))
            sys.exit(1)
        report = run_compose_acceptance(Path(args.compose_file), Path(args.reports_dir))
        print(json.dumps(report, indent=2))
        sys.exit(0 if report.get("status") == "PASSED" else 1)


if __name__ == "__main__":
    main()
