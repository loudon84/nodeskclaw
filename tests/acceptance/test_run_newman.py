from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.acceptance.run_newman import construct_newman_command, generate_env_file, redact_report_files


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
