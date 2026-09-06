from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.acceptance import harness
from tools.acceptance.hermes_test_server import HermesHandler


def _fill_required_env(monkeypatch) -> None:
    for name in harness.REQUIRED_ENV:
        monkeypatch.setenv(name, f"test-value-{name}")


def _passing_report(**overrides):
    report = {
        "status": "PASSED",
        "started": True,
        "teardown": {"ok": True},
        "chat_completions": {"status": 404, "ok": True},
        "native_observed": {"ok": True},
        "scan_bind": {"ok": True},
        "scenarios": [
            {"name": name, "ok": True, "oracle": {"ok": True}}
            for name in sorted(harness.REQUIRED_SCENARIOS)
        ],
        "faults": [
            {"name": name, "injected": True, "recovered": True, "ok": True, "oracle": {"ok": True}}
            for name in sorted(harness.REQUIRED_FAULTS)
        ],
    }
    report.update(overrides)
    return report


def test_validate_topology_passes_on_current_compose():
    compose = Path("docker-compose.acceptance.yml")
    if not compose.exists():
        return
    result = harness.validate_topology(compose)
    assert result["valid"] is True, result
    assert result["checks"]["no_dead_hermes_gateway_url"] is True
    assert result["checks"]["has_hermes_instances_root"] is True


def test_validate_topology_rejects_dead_gateway_url(tmp_path):
    compose = tmp_path / "docker-compose.acceptance.yml"
    compose.write_text(
        Path("docker-compose.acceptance.yml").read_text(encoding="utf-8")
        + "\n      HERMES_GATEWAY_URL: http://hermes-test:8088\n",
        encoding="utf-8",
    )
    result = harness.validate_topology(compose)
    assert result["valid"] is False
    assert result["checks"]["no_dead_hermes_gateway_url"] is False


def test_check_docker_unavailable_is_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(harness, "check_docker_available", lambda: False)
    proc = subprocess.run(
        [sys.executable, "tools/acceptance/harness.py", "check-docker"],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 1
    payload = json.loads(proc.stdout)
    assert payload["docker_available"] is False


def test_run_exits_nonzero_when_docker_unavailable(monkeypatch, tmp_path):
    monkeypatch.setattr(harness, "check_docker_available", lambda: False)
    with patch.object(sys, "argv", ["harness.py", "run", "--reports-dir", str(tmp_path)]):
        with pytest.raises(SystemExit) as exc:
            harness.main()
    assert exc.value.code == 1
    report = json.loads((tmp_path / "harness_summary.json").read_text())
    assert report["status"] == "FAILED"
    assert report["error"] == "Docker daemon unavailable"


def test_run_compose_returns_failed_when_env_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("SKILL_AGENT_INTERNAL_TOKEN", raising=False)
    report = harness.run_compose_acceptance(Path("docker-compose.acceptance.yml"), tmp_path)
    assert report["status"] == "FAILED"
    assert "Missing required env" in report["error"]
    assert (tmp_path / "harness_summary.json").is_file()


def test_execution_report_rejects_success_without_scenario_oracles():
    report = {
        "status": "PASSED",
        "scenarios": [{"name": "dual_central_minio_ready", "ok": True}],
        "faults": [],
    }

    errors = harness.validate_execution_report(report)

    assert "missing required scenario" in " ".join(errors)
    assert "missing required fault" in " ".join(errors)


def test_execution_report_rejects_missing_oracle_on_named_scenario():
    report = _passing_report()
    report["scenarios"] = [
        {"name": "dual_central_minio_artifact", "ok": True},
        {"name": "edge_delivery_and_spool_replay", "ok": True, "oracle": {"ok": True}},
        {"name": "bundle_lifecycle", "ok": True, "oracle": {"ok": True}},
    ]

    errors = harness.validate_execution_report(report)

    assert any("dual_central_minio_artifact" in item for item in errors)


def test_execution_report_rejects_chat_completions_200():
    report = _passing_report(chat_completions={"status": 200, "ok": False})

    errors = harness.validate_execution_report(report)

    assert any("ChatCompletion" in item for item in errors)


def test_execution_report_rejects_scan_bind_failure():
    report = _passing_report(scan_bind={"ok": False, "bound": 0})

    errors = harness.validate_execution_report(report)

    assert any("scan-existing" in item for item in errors)


def test_execution_report_rejects_passed_without_teardown():
    report = _passing_report(teardown={"ok": False})

    errors = harness.validate_execution_report(report)

    assert any("teardown" in item for item in errors)


def test_interpret_scan_bind_zero_is_fail_closed():
    result = harness.interpret_scan_bind({"code": 0, "data": {"bound": 0, "scanned": 1, "items": []}}, http_status=200)
    assert result["ok"] is False


def test_observe_chat_completions_200_is_fail_closed():
    class Chat200(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            return

        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length:
                self.rfile.read(length)
            body = b'{"id":"chatcmpl-x"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Chat200)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        observed = harness.observe_chat_completions(f"http://127.0.0.1:{port}")
    finally:
        server.shutdown()
        server.server_close()
    assert observed["status"] == 200
    assert observed["ok"] is False


def test_hermes_handler_native_surface_and_chat_completions_404(monkeypatch):
    monkeypatch.setenv("HERMES_TEST_API_KEY", "fixture-key")
    server = ThreadingHTTPServer(("127.0.0.1", 0), HermesHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        base = f"http://127.0.0.1:{port}"
        deadline = time.time() + 2
        health = (0, "")
        while time.time() < deadline:
            health = harness._http_get(f"{base}/health")
            if health[0] == 200:
                break
            time.sleep(0.05)
        assert health[0] == 200
        chat = harness.observe_chat_completions(base)
        native = harness.observe_native_runtime(base, "fixture-key")
    finally:
        server.shutdown()
        server.server_close()
    assert chat["status"] == 404
    assert chat["ok"] is True
    assert native["ok"] is True
    assert native["version"] == "v2026.8.31"
    monkeypatch.setenv("HERMES_TEST_API_KEY", "fixture-key")
    server = ThreadingHTTPServer(("127.0.0.1", 0), HermesHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = server.server_address[1]
        base = f"http://127.0.0.1:{port}"
        chat = harness.observe_chat_completions(base)
        native = harness.observe_native_runtime(base, "fixture-key")
    finally:
        server.shutdown()
        server.server_close()
    assert chat["status"] == 404
    assert chat["ok"] is True
    assert native["ok"] is True
    assert native["version"] == "v2026.8.31"


def test_run_compose_teardown_after_started_failure(monkeypatch, tmp_path):
    _fill_required_env(monkeypatch)
    monkeypatch.setattr(harness, "validate_topology", lambda *_a, **_k: {"valid": True, "checks": {}})
    monkeypatch.setattr(harness, "prepare_hermes_instance_dir", lambda root, _key: root)
    calls: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(harness, "_wait_ready", lambda *_a, **_k: {"ok": False, "status": 503, "body": "not ready"})

    report = harness.run_compose_acceptance(Path("docker-compose.acceptance.yml"), tmp_path)

    assert report["status"] == "FAILED"
    assert report.get("started") is True
    assert report.get("teardown", {}).get("ok") is True
    assert any("down" in cmd for cmd in calls)


def test_harness_report_redacts_runtime_secrets(monkeypatch, tmp_path):
    monkeypatch.setenv("SKILL_AGENT_INTERNAL_TOKEN", "test-secret-token")

    harness._write_report(tmp_path, {"status": "FAILED", "detail": "test-secret-token"})

    content = (tmp_path / "harness_summary.json").read_text()
    assert "test-secret-token" not in content
    assert "[REDACTED]" in content
