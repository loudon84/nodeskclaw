from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.acceptance.run_newman import (
    allocate_run_prefix,
    assert_private_env_path,
    assert_reports_present,
    construct_newman_command,
    generate_env_file,
    redact_report_files,
    run_skill_run_contract_check,
)


def test_construct_newman_command(tmp_path):
    coll = tmp_path / "coll.json"
    env = tmp_path / "env.json"
    xml = tmp_path / "report.xml"
    json_out = tmp_path / "report.json"

    cmd = construct_newman_command(coll, env, xml, json_out)
    assert "run" in cmd
    assert str(coll) in cmd
    assert str(env) in cmd
    assert str(xml) in cmd
    assert str(json_out) in cmd
    assert "--delay-request" in cmd
    assert "cli,junit,json" in cmd
    assert "--timeout-request" in cmd


def test_generate_env_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AGENT_INTERNAL_TOKEN", "internal-token")
    monkeypatch.setenv("SKILL_AGENT_EDGE_TOKEN", "edge-token")
    monkeypatch.setenv("JWT_TOKEN", "jwt-token")
    monkeypatch.setenv("ACCEPTANCE_ORG_ID", "acceptance-test")
    monkeypatch.setenv("ACCEPTANCE_USER_ID", "user-test-acceptance")
    template = tmp_path / "template.json"
    template.write_text('{"values": [{"key": "TOKEN", "value": "${SKILL_AGENT_INTERNAL_TOKEN}"}]}')
    out = tmp_path / "out.json"

    generate_env_file(template, out)
    assert out.exists()
    assert "${SKILL_AGENT_INTERNAL_TOKEN}" not in out.read_text()


def test_generate_env_file_requires_isolated_org_and_user(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AGENT_INTERNAL_TOKEN", "internal-token")
    monkeypatch.setenv("SKILL_AGENT_EDGE_TOKEN", "edge-token")
    monkeypatch.setenv("JWT_TOKEN", "jwt-token")
    monkeypatch.delenv("ACCEPTANCE_ORG_ID", raising=False)
    monkeypatch.delenv("ACCEPTANCE_USER_ID", raising=False)
    template = tmp_path / "template.json"
    template.write_text('{"values": []}')

    try:
        generate_env_file(template, tmp_path / "out.json")
    except RuntimeError as exc:
        assert "ACCEPTANCE_ORG_ID" in str(exc)
    else:
        raise AssertionError("expected missing acceptance scope to fail")


def test_redact_report_files_removes_runtime_secret(tmp_path):
    report = tmp_path / "newman.json"
    report.write_text('{"authorization": "Bearer jwt-token"}')

    redact_report_files((report,), ("jwt-token",))

    assert "jwt-token" not in report.read_text()
    assert "[REDACTED]" in report.read_text()


def test_allocate_run_prefix_rejects_duplicate():
    used: set[str] = set()
    first = allocate_run_prefix(used, "acceptance-shared")
    assert first == "acceptance-shared"
    try:
        allocate_run_prefix(used, "acceptance-shared")
    except RuntimeError as exc:
        assert "Duplicate acceptance run prefix" in str(exc)
    else:
        raise AssertionError("expected duplicate prefix to fail")


def test_assert_reports_present_rejects_missing_or_empty(tmp_path):
    missing = tmp_path / "newman_run1.json"
    empty = tmp_path / "newman_run1_junit.xml"
    empty.write_text("")
    try:
        assert_reports_present((missing, empty))
    except RuntimeError as exc:
        assert "required JUnit and JSON reports" in str(exc)
    else:
        raise AssertionError("expected missing reports to fail")


def test_generate_env_file_rejects_reports_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AGENT_INTERNAL_TOKEN", "internal-token")
    monkeypatch.setenv("SKILL_AGENT_EDGE_TOKEN", "edge-token")
    monkeypatch.setenv("JWT_TOKEN", "jwt-token")
    monkeypatch.setenv("ACCEPTANCE_ORG_ID", "acceptance-test")
    monkeypatch.setenv("ACCEPTANCE_USER_ID", "user-test-acceptance")
    template = tmp_path / "template.json"
    template.write_text('{"values": [{"key": "RUN_PREFIX", "value": "${ACCEPTANCE_RUN_PREFIX}"}]}')
    reports_out = tmp_path / "reports" / "acceptance_environment.json"
    reports_out.parent.mkdir()
    try:
        generate_env_file(template, reports_out, run_prefix="acceptance-a")
    except RuntimeError as exc:
        assert "reports" in str(exc)
    else:
        raise AssertionError("expected reports directory env path to fail")


def test_generate_env_file_injects_unique_prefix(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_AGENT_INTERNAL_TOKEN", "internal-token")
    monkeypatch.setenv("SKILL_AGENT_EDGE_TOKEN", "edge-token")
    monkeypatch.setenv("JWT_TOKEN", "jwt-token")
    monkeypatch.setenv("ACCEPTANCE_ORG_ID", "acceptance-test")
    monkeypatch.setenv("ACCEPTANCE_USER_ID", "user-test-acceptance")
    template = tmp_path / "template.json"
    template.write_text('{"values": [{"key": "RUN_PREFIX", "value": "${ACCEPTANCE_RUN_PREFIX}"}]}')
    out = tmp_path / "private" / "env.json"
    generate_env_file(template, out, run_prefix="acceptance-unique-1")
    text = out.read_text()
    assert "acceptance-unique-1" in text
    assert "${ACCEPTANCE_RUN_PREFIX}" not in text


def test_assert_private_env_path_allows_temp_dir(tmp_path):
    assert_private_env_path(tmp_path / "acceptance_environment.json")


def test_run_skill_run_contract_check_fails_closed(monkeypatch):
    class _Result:
        returncode = 1

    monkeypatch.setattr(
        "tools.acceptance.run_newman.subprocess.run",
        lambda *args, **kwargs: _Result(),
    )
    try:
        run_skill_run_contract_check()
    except RuntimeError as exc:
        assert "contract check failed" in str(exc).lower()
    else:
        raise AssertionError("expected failed contract check to abort")
