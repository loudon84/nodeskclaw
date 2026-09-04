#!/usr/bin/env python3
"""Acceptance Harness for Central A/B, Edge and Backend topology validation."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
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


def _write_report(reports_dir: Path, report: dict[str, Any]) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(report, indent=2)
    for name in REQUIRED_ENV:
        secret = os.getenv(name, "")
        if secret:
            rendered = rendered.replace(secret, "[REDACTED]")
    (reports_dir / "harness_summary.json").write_text(rendered, encoding="utf-8")


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
        elif not fault.get("injected") or not fault.get("recovered") or not fault.get("oracle"):
            errors.append(f"fault has no passing oracle: {name}")

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


def _http_get(url: str, timeout: float = 3.0) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body


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


def _run_fault(name: str, compose_file: Path, command: list[str], recover: list[str]) -> dict[str, Any]:
    result: dict[str, Any] = {"name": name, "injected": False, "recovered": False}
    inj = subprocess.run(command, check=False, capture_output=True, text=True)
    result["injected"] = inj.returncode == 0
    result["inject_output"] = (inj.stdout or "") + (inj.stderr or "")
    time.sleep(3)
    rec = subprocess.run(recover, check=False, capture_output=True, text=True)
    result["recovered"] = rec.returncode == 0
    result["recover_output"] = (rec.stdout or "") + (rec.stderr or "")
    return result


def run_compose_acceptance(compose_file: Path, reports_dir: Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "status": "RUNNING",
        "compose_file": str(compose_file),
        "scenarios": [],
        "faults": [],
    }
    started = False
    try:
        missing = [name for name in REQUIRED_ENV if not os.getenv(name, "").strip()]
        if missing:
            report.update(status="FAILED", error=f"Missing required env: {', '.join(missing)}")
            return report

        up = subprocess.run(_compose_cmd(compose_file, "up", "-d", "--build"), check=False)
        if up.returncode != 0:
            report.update(status="FAILED", error="docker compose up failed")
            return report
        started = True

        waits = {
            "backend_live": _wait_ready("http://127.0.0.1:4510/api/v1/health"),
            "agent_a_ready": _wait_ready("http://127.0.0.1:4580/health/ready", timeout_seconds=240),
            "agent_b_ready": _wait_ready("http://127.0.0.1:4521/health/ready", timeout_seconds=240),
        }
        report["waits"] = waits
        if not all(item.get("ok") for item in waits.values()):
            report.update(status="FAILED", error="readiness wait failed")
            return report

        report["scenarios"].append({"name": "dual_central_minio_ready", "ok": True})
        report["faults"] = [
            _run_fault("postgres_unavailable", compose_file, _compose_cmd(compose_file, "pause", "postgres"), _compose_cmd(compose_file, "unpause", "postgres")),
            _run_fault("minio_unavailable", compose_file, _compose_cmd(compose_file, "pause", "minio"), _compose_cmd(compose_file, "unpause", "minio")),
            _run_fault("kill_central_a", compose_file, _compose_cmd(compose_file, "kill", "nodeskclaw-agent"), _compose_cmd(compose_file, "up", "-d", "nodeskclaw-agent")),
            _run_fault("edge_network_partition", compose_file, _compose_cmd(compose_file, "pause", "nodeskclaw-agent-edge"), _compose_cmd(compose_file, "unpause", "nodeskclaw-agent-edge")),
        ]

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
            teardown = subprocess.run(_compose_cmd(compose_file, "down", "--volumes", "--remove-orphans"), check=False, capture_output=True, text=True)
            report["teardown"] = {"ok": teardown.returncode == 0}
            if teardown.returncode != 0 and report.get("status") == "PASSED":
                report.update(status="FAILED", error="compose teardown failed")
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
