from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.acceptance import harness


def test_validate_topology_passes_on_current_compose():
    compose = Path("docker-compose.acceptance.yml")
    if not compose.exists():
        return
    result = harness.validate_topology(compose)
    assert result["valid"] is True, result


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


def test_harness_report_redacts_runtime_secrets(monkeypatch, tmp_path):
    monkeypatch.setenv("SKILL_AGENT_INTERNAL_TOKEN", "test-secret-token")

    harness._write_report(tmp_path, {"status": "FAILED", "detail": "test-secret-token"})

    content = (tmp_path / "harness_summary.json").read_text()
    assert "test-secret-token" not in content
    assert "[REDACTED]" in content
