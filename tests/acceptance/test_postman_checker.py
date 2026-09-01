from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.acceptance.check_postman_collection import check_collection, scan_acceptance_secrets


def test_checker_passes_on_valid_collection(tmp_path):
    coll = {
        "info": {"name": "Valid Collection"},
        "item": [
            {
                "name": "Public Contract (Backend JWT)",
                "item": [
                    {
                        "name": "AC-01 Valid Request",
                        "request": {
                            "method": "GET",
                            "header": [{"key": "Authorization", "value": "Bearer {{JWT_TOKEN}}"}],
                            "url": {"raw": "{{BACKEND_BASE_URL}}/api/v1/health"},
                        },
                        "event": [
                            {
                                "listen": "test",
                                "script": {
                                    "exec": [
                                        "pm.test('200 ok', function() { pm.expect(pm.response.code).to.equal(200); });"
                                    ]
                                },
                            }
                        ],
                    }
                ],
            },
            {
                "name": "Internal Harness (Edge/Bundle)",
                "item": [
                    {
                        "name": "AC-22 Internal Request",
                        "request": {
                            "method": "GET",
                            "header": [{"key": "X-Skill-Agent-Token", "value": "{{INTERNAL_TOKEN}}"}],
                            "url": {"raw": "{{AGENT_BASE_URL}}/health/ready"},
                        },
                        "event": [
                            {
                                "listen": "test",
                                "script": {
                                    "exec": [
                                        "pm.test('200 ok', function() { pm.expect(pm.response.code).to.equal(200); });"
                                    ]
                                },
                            }
                        ],
                    }
                ],
            },
        ],
    }
    env = {
        "values": [
            {"key": "AGENT_BASE_URL", "value": "http://127.0.0.1:4520"},
            {"key": "BACKEND_BASE_URL", "value": "http://127.0.0.1:4510"},
            {"key": "JWT_TOKEN", "value": "${JWT_TOKEN}"},
            {"key": "INTERNAL_TOKEN", "value": "${SKILL_AGENT_INTERNAL_TOKEN}"},
        ]
    }

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


def test_checker_requires_jwt_and_internal_items(tmp_path):
    coll = {
        "info": {"name": "Missing JWT"},
        "item": [
            {
                "name": "AC-22 Internal Only",
                "request": {
                    "header": [{"key": "X-Skill-Agent-Token", "value": "{{INTERNAL_TOKEN}}"}],
                    "url": {"raw": "{{AGENT_BASE_URL}}/health/ready"},
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
    c_path = tmp_path / "jwt_missing.json"
    c_path.write_text(json.dumps(coll))
    errors = check_collection(c_path)
    assert any("Backend JWT public-contract" in err for err in errors)


def test_secret_scan_flags_forbidden_literals(tmp_path):
    compose = tmp_path / "docker-compose.acceptance.yml"
    compose.write_text("SKILL_AGENT_INTERNAL_TOKEN: postman-acceptance-agent-token-secure-32b\n")
    errors = scan_acceptance_secrets([compose])
    assert any("Secret-like value" in err for err in errors)


def test_checker_rejects_test_script_without_assertion(tmp_path):
    coll = {
        "info": {"name": "Assertionless Collection"},
        "item": [
            {
                "name": "Public Request",
                "request": {
                    "header": [{"key": "Authorization", "value": "Bearer {{JWT_TOKEN}}"}],
                    "url": {"raw": "{{BACKEND_BASE_URL}}/api/v1/health"},
                },
                "event": [{"listen": "test", "script": {"exec": ["console.log('no assertion')"]}}],
            },
            {
                "name": "Internal Request",
                "request": {
                    "header": [{"key": "X-Skill-Agent-Token", "value": "{{INTERNAL_TOKEN}}"}],
                    "url": {"raw": "{{AGENT_BASE_URL}}/health/ready"},
                },
                "event": [{"listen": "test", "script": {"exec": ["console.log('no assertion')"]}}],
            },
        ],
    }
    path = tmp_path / "assertionless.json"
    path.write_text(json.dumps(coll))

    errors = check_collection(path)

    assert any("no test assertions" in error for error in errors)


def test_checker_rejects_permissive_mixed_success_and_error_statuses(tmp_path):
    collection = {
        "info": {"name": "Permissive Collection"},
        "item": [
            {
                "name": "Public request",
                "request": {
                    "header": [{"key": "Authorization", "value": "Bearer {{JWT_TOKEN}}"}],
                    "url": {"raw": "{{BACKEND_BASE_URL}}/api/v1/health"},
                },
                "event": [{"listen": "test", "script": {"exec": [
                    "pm.test('anything', function() { pm.expect(pm.response.code).to.be.oneOf([200, 404]); });"
                ]}}],
            },
            {
                "name": "Internal request",
                "request": {
                    "header": [{"key": "X-Skill-Agent-Token", "value": "{{INTERNAL_TOKEN}}"}],
                    "url": {"raw": "{{AGENT_BASE_URL}}/health/ready"},
                },
                "event": [{"listen": "test", "script": {"exec": [
                    "pm.test('ready', function() { pm.response.to.have.status(200); });"
                ]}}],
            },
        ],
    }
    path = tmp_path / "permissive.json"
    path.write_text(json.dumps(collection))

    errors = check_collection(path)

    assert any("permissive mixed success/error status" in error for error in errors)


def test_secret_scan_detects_generic_secret_in_rendered_report(tmp_path):
    report = tmp_path / "rendered_acceptance_environment.json"
    report.write_text('{"JWT_TOKEN": "plain-secret-value-123"}')

    errors = scan_acceptance_secrets([report])

    assert any("Secret-like value" in error for error in errors)
