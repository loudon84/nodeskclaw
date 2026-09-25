from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.acceptance.check_postman_collection import (
    PUBLIC_JOURNEY_PATTERNS,
    check_collection,
    scan_acceptance_secrets,
)

REPO_COLLECTION = Path("tests/postman/nodeskclaw_acceptance_closure.postman_collection.json")
REPO_ENV_TEMPLATE = Path("tests/postman/nodeskclaw_agent_acceptance.postman_environment.template.json")


def _assert_ok():
    return [
        {
            "listen": "test",
            "script": {
                "exec": [
                    "pm.test('200 ok', function() { pm.expect(pm.response.code).to.equal(200); });"
                ]
            },
        }
    ]


def _jwt_item(name: str, url: str, *, body: str = "") -> dict:
    request = {
        "method": "POST" if body else "GET",
        "header": [{"key": "Authorization", "value": "Bearer {{JWT_TOKEN}}"}],
        "url": {"raw": url},
    }
    if body:
        request["body"] = {"raw": body}
    return {"name": name, "request": request, "event": _assert_ok()}


def _internal_item(name: str, url: str) -> dict:
    return {
        "name": name,
        "request": {
            "method": "GET",
            "header": [{"key": "X-Skill-Agent-Token", "value": "{{INTERNAL_TOKEN}}"}],
            "url": {"raw": url},
        },
        "event": _assert_ok(),
    }


def _valid_collection(*, extra_public: list[dict] | None = None, include_bundle: bool = True) -> dict:
    public = [
        _jwt_item("AC-01 Health", "{{BACKEND_BASE_URL}}/api/v1/health"),
        _jwt_item(
            "AC-02 Catalog",
            "{{BACKEND_BASE_URL}}/api/v1/mcp",
            body='{"jsonrpc":"2.0","id":"list-1","method":"tools/list","params":{}}',
        ),
        _jwt_item(
            "AC-03 tools/call",
            "{{BACKEND_BASE_URL}}/api/v1/mcp",
            body='{"jsonrpc":"2.0","id":"call-1","method":"tools/call","params":{"name":"demo_search","arguments":{"q":"{{RUN_PREFIX}}"}}}',
        ),
        _jwt_item("AC-04 Events", "{{BACKEND_BASE_URL}}/api/v1/runs/{{RUN_ID}}/events"),
        _jwt_item("AC-05 Result", "{{BACKEND_BASE_URL}}/api/v1/runs/{{RUN_ID}}/result"),
        _jwt_item(
            "AC-07 Approve",
            "{{BACKEND_BASE_URL}}/api/v1/runs/{{RUN_ID}}/approvals/{{APPROVAL_ID}}",
            body='{"choice":"once"}',
        ),
        _jwt_item(
            "AC-07b Decision",
            "{{BACKEND_BASE_URL}}/api/v1/runs/{{RUN_ID}}/approvals/{{APPROVAL_ID}}/decision",
            body='{"decision":"allow"}',
        ),
        _jwt_item(
            "AC-10 Attachments",
            "{{BACKEND_BASE_URL}}/api/v1/attachments",
            body='{"filename":"probe.txt"}',
        ),
        _jwt_item("AC-08 Resume", "{{BACKEND_BASE_URL}}/api/v1/runs/{{RUN_ID}}/resume"),
        _jwt_item("AC-06 Cancel", "{{BACKEND_BASE_URL}}/api/v1/runs/{{RUN_ID}}/cancel"),
        _jwt_item("AC-09 Artifacts", "{{BACKEND_BASE_URL}}/api/v1/runs/{{RUN_ID}}/artifacts"),
    ]
    if extra_public:
        public.extend(extra_public)
    internal = [_internal_item("AC-22 Internal Request", "{{AGENT_BASE_URL}}/health/ready")]
    if include_bundle:
        internal.append(
            _internal_item(
                "AC-27 Bundle Desired Installations",
                "{{BACKEND_BASE_URL}}/api/v1/internal/edge/installations/desired",
            )
        )
    return {
        "info": {"name": "Valid Collection"},
        "item": [
            {"name": "Public Contract (Backend JWT)", "item": public},
            {"name": "Internal Harness (Edge/Bundle)", "item": internal},
        ],
    }


def _valid_env() -> dict:
    return {
        "values": [
            {"key": "AGENT_BASE_URL", "value": "http://127.0.0.1:4580"},
            {"key": "BACKEND_BASE_URL", "value": "http://127.0.0.1:4510"},
            {"key": "JWT_TOKEN", "value": "${JWT_TOKEN}"},
            {"key": "INTERNAL_TOKEN", "value": "${SKILL_AGENT_INTERNAL_TOKEN}"},
            {"key": "ORG_ID", "value": "${ACCEPTANCE_ORG_ID}"},
            {"key": "RUN_PREFIX", "value": "${ACCEPTANCE_RUN_PREFIX}"},
        ]
    }


def test_checker_passes_on_valid_collection(tmp_path):
    coll = _valid_collection()
    env = _valid_env()

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


def test_checker_rejects_public_hermes_task_url(tmp_path):
    coll = _valid_collection(
        extra_public=[
            _jwt_item(
                "AC-05 Task Timeline SSE",
                "{{BACKEND_BASE_URL}}/api/v1/hermes/tasks/{{TASK_ID}}/timeline",
            )
        ]
    )
    c_path = tmp_path / "hermes_task.json"
    e_path = tmp_path / "env.json"
    c_path.write_text(json.dumps(coll))
    e_path.write_text(json.dumps(_valid_env()))

    errors = check_collection(c_path, e_path)

    assert any("hermes/tasks" in error.lower() or "hermestask" in error.lower() for error in errors)


def test_checker_rejects_missing_bundle_journey(tmp_path):
    coll = _valid_collection(include_bundle=False)
    c_path = tmp_path / "no_bundle.json"
    e_path = tmp_path / "env.json"
    c_path.write_text(json.dumps(coll))
    e_path.write_text(json.dumps(_valid_env()))

    errors = check_collection(c_path, e_path)

    assert any("bundle" in error.lower() for error in errors)


def test_checker_rejects_missing_public_result_journey(tmp_path):
    coll = _valid_collection()
    public = coll["item"][0]["item"]
    coll["item"][0]["item"] = [item for item in public if "/result" not in str(item["request"]["url"]["raw"])]
    c_path = tmp_path / "no_result.json"
    e_path = tmp_path / "env.json"
    c_path.write_text(json.dumps(coll))
    e_path.write_text(json.dumps(_valid_env()))

    errors = check_collection(c_path, e_path)

    assert any("result" in error.lower() for error in errors)


def test_checker_rejects_missing_public_decision_journey(tmp_path):
    coll = _valid_collection()
    public = coll["item"][0]["item"]
    coll["item"][0]["item"] = [
        item for item in public if "/decision" not in str(item["request"]["url"]["raw"])
    ]
    c_path = tmp_path / "no_decision.json"
    e_path = tmp_path / "env.json"
    c_path.write_text(json.dumps(coll))
    e_path.write_text(json.dumps(_valid_env()))

    errors = check_collection(c_path, e_path)

    assert any("approval_decision" in error.lower() or "decision" in error.lower() for error in errors)


def test_checker_rejects_missing_public_attachments_journey(tmp_path):
    coll = _valid_collection()
    public = coll["item"][0]["item"]
    coll["item"][0]["item"] = [
        item for item in public if "/api/v1/attachments" not in str(item["request"]["url"]["raw"])
    ]
    c_path = tmp_path / "no_attachments.json"
    e_path = tmp_path / "env.json"
    c_path.write_text(json.dumps(coll))
    e_path.write_text(json.dumps(_valid_env()))

    errors = check_collection(c_path, e_path)

    assert any("attachments" in error.lower() for error in errors)


def test_checker_rejects_public_item_with_internal_token(tmp_path):
    coll = _valid_collection()
    coll["item"][0]["item"][0]["request"]["header"].append(
        {"key": "X-Skill-Agent-Token", "value": "{{INTERNAL_TOKEN}}"}
    )
    c_path = tmp_path / "public_internal.json"
    e_path = tmp_path / "env.json"
    c_path.write_text(json.dumps(coll))
    e_path.write_text(json.dumps(_valid_env()))

    errors = check_collection(c_path, e_path)

    assert any("x-skill-agent-token" in error.lower() for error in errors)


def test_formal_collection_covers_public_skill_run_journeys():
    errors = check_collection(REPO_COLLECTION, REPO_ENV_TEMPLATE)
    assert errors == []


def test_public_journeys_do_not_include_internal_southbound():
    blob = " ".join(pattern.pattern for pattern in PUBLIC_JOURNEY_PATTERNS.values())
    assert "/internal/" not in blob
    assert "AGENT_BASE_URL" not in blob
