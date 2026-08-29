from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.acceptance.run_newman import construct_newman_command, generate_env_file


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


def test_generate_env_file(tmp_path):
    template = tmp_path / "template.json"
    template.write_text('{"values": [{"key": "TOKEN", "value": "${SKILL_AGENT_INTERNAL_TOKEN}"}]}')
    out = tmp_path / "out.json"

    generate_env_file(template, out)
    assert out.exists()
    assert "${SKILL_AGENT_INTERNAL_TOKEN}" not in out.read_text()
