from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.acceptance.check_postman_collection import check_collection


def test_checker_passes_on_valid_collection(tmp_path):
    coll = {
        "info": {"name": "Valid Collection"},
        "item": [
            {
                "name": "AC-01 Valid Request",
                "request": {
                    "method": "GET",
                    "url": {"raw": "{{AGENT_BASE_URL}}/health/ready"},
                },
                "event": [
                    {
                        "listen": "test",
                        "script": {
                            "exec": ["pm.test('200 ok', function() { pm.expect(pm.response.code).to.equal(200); });"]
                        },
                    }
                ],
            }
        ],
    }
    env = {"values": [{"key": "AGENT_BASE_URL", "value": "http://127.0.0.1:4520"}]}

    c_path = tmp_path / "coll.json"
    e_path = tmp_path / "env.json"
    c_path.write_text(json.dumps(coll))
    e_path.write_text(json.dumps(env))

    errors = check_collection(c_path, e_path)
    assert len(errors) == 0


def test_checker_catches_vacuous_assertion(tmp_path):
    coll = {
        "info": {"name": "Bad Assert Collection"},
        "item": [
            {
                "name": "AC-01 Fake Test",
                "request": {"url": {"raw": "http://example.com"}},
                "event": [
                    {
                        "listen": "test",
                        "script": {
                            "exec": ["pm.test('fake', function() { pm.expect(true).to.be.true; });"]
                        },
                    }
                ],
            }
        ],
    }
    c_path = tmp_path / "bad_coll.json"
    c_path.write_text(json.dumps(coll))

    errors = check_collection(c_path)
    assert any("vacuous assertion" in err for err in errors)


def test_checker_catches_hardcoded_secret(tmp_path):
    coll = {
        "info": {"name": "Secret Leak Collection"},
        "item": [
            {
                "name": "AC-02 Leak",
                "request": {
                    "body": {"raw": "token = 'sk-12345678901234567890123456789012'"},
                },
                "event": [
                    {
                        "listen": "test",
                        "script": {"exec": ["pm.test('ok', function() { pm.expect(200).to.equal(200); });"]},
                    }
                ],
            }
        ],
    }
    c_path = tmp_path / "leak_coll.json"
    c_path.write_text(json.dumps(coll))

    errors = check_collection(c_path)
    assert any("hardcoded plaintext secret" in err for err in errors)
