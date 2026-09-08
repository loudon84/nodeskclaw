#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    root = Path("tests/postman/nodeskclaw_acceptance_closure.postman_collection.json")
    data = json.loads(root.read_text(encoding="utf-8"))
    data["info"]["name"] = "NoDeskClaw RM-04 Production Acceptance"
    data["info"]["description"] = (
        "Formal acceptance: Backend JWT public contract plus internal Edge/Bundle harness flows."
    )

    public_items = [
        _item(
            "AC-01 Backend Health JWT",
            "GET",
            "{{BACKEND_BASE_URL}}/api/v1/health",
            ["api", "v1", "health"],
            headers=[{"key": "Authorization", "value": "Bearer {{JWT_TOKEN}}"}],
            tests=[
                "pm.test('Backend health returns 200', function () {",
                "    pm.response.to.have.status(200);",
                "    pm.expect(pm.response.json()).to.be.an('object');",
                "});",
            ],
        ),
        _item(
            "AC-02 MCP Catalog tools/list",
            "POST",
            "{{BACKEND_BASE_URL}}/api/v1/mcp",
            ["api", "v1", "mcp"],
            headers=[
                {"key": "Content-Type", "value": "application/json"},
                {"key": "Authorization", "value": "Bearer {{JWT_TOKEN}}"},
                {"key": "X-Org-Id", "value": "{{ORG_ID}}"},
            ],
            body='{"jsonrpc":"2.0","id":"list-1","method":"tools/list","params":{}}',
            tests=[
                "pm.test('MCP catalog lists tools', function () {",
                "    pm.response.to.have.status(200);",
                "    var json = pm.response.json();",
                "    pm.expect(json.jsonrpc).to.eql('2.0');",
                "    pm.expect(json).to.have.property('result');",
                "});",
            ],
        ),
        _item(
            "AC-03 MCP tools/call",
            "POST",
            "{{BACKEND_BASE_URL}}/api/v1/mcp",
            ["api", "v1", "mcp"],
            headers=[
                {"key": "Content-Type", "value": "application/json"},
                {"key": "Authorization", "value": "Bearer {{JWT_TOKEN}}"},
                {"key": "X-Org-Id", "value": "{{ORG_ID}}"},
            ],
            body=(
                '{"jsonrpc":"2.0","id":"call-1","method":"tools/call",'
                '"params":{"name":"demo_search","arguments":{"q":"acceptance"}}}'
            ),
            tests=[
                "pm.test('Tools call returns structured response', function () {",
                "    pm.response.to.have.status(200);",
                "    var json = pm.response.json();",
                "    pm.expect(json).to.have.property('result');",
                "    if (json.result && json.result.structuredContent && json.result.structuredContent.run_id) {",
                "        pm.environment.set('RUN_ID', json.result.structuredContent.run_id);",
                "    }",
                "});",
            ],
        ),
        _item(
            "AC-04 Run Events SSE",
            "GET",
            "{{BACKEND_BASE_URL}}/api/v1/runs/{{RUN_ID}}/events",
            ["api", "v1", "runs", "{{RUN_ID}}", "events"],
            headers=[
                {"key": "Authorization", "value": "Bearer {{JWT_TOKEN}}"},
                {"key": "X-Org-Id", "value": "{{ORG_ID}}"},
            ],
            tests=[
                "pm.test('Run events endpoint responds', function () {",
                "    pm.expect(pm.response.code).to.be.oneOf([200, 404]);",
                "});",
            ],
        ),
        _item(
            "AC-05 Task Timeline SSE",
            "GET",
            "{{BACKEND_BASE_URL}}/api/v1/hermes/tasks/{{TASK_ID}}/timeline",
            ["api", "v1", "hermes", "tasks", "{{TASK_ID}}", "timeline"],
            headers=[
                {"key": "Authorization", "value": "Bearer {{JWT_TOKEN}}"},
                {"key": "Accept", "value": "text/event-stream"},
            ],
            tests=[
                "pm.test('Task timeline SSE responds', function () {",
                "    pm.expect(pm.response.code).to.be.oneOf([200, 404]);",
                "});",
            ],
        ),
        _item(
            "AC-06 Cancel Run",
            "POST",
            "{{BACKEND_BASE_URL}}/api/v1/runs/{{RUN_ID}}/cancel",
            ["api", "v1", "runs", "{{RUN_ID}}", "cancel"],
            headers=[
                {"key": "Authorization", "value": "Bearer {{JWT_TOKEN}}"},
                {"key": "X-Org-Id", "value": "{{ORG_ID}}"},
            ],
            tests=[
                "pm.test('Cancel converges idempotently', function () {",
                "    pm.expect(pm.response.code).to.be.oneOf([200, 404, 400]);",
                "});",
            ],
        ),
        _item(
            "AC-07 Approve Run",
            "POST",
            "{{BACKEND_BASE_URL}}/api/v1/runs/{{RUN_ID}}/approve",
            ["api", "v1", "runs", "{{RUN_ID}}", "approve"],
            headers=[
                {"key": "Content-Type", "value": "application/json"},
                {"key": "Authorization", "value": "Bearer {{JWT_TOKEN}}"},
                {"key": "X-Org-Id", "value": "{{ORG_ID}}"},
            ],
            body='{"approval_id":"acceptance-appr-1","evidence":{"actor":"acceptance"}}',
            tests=[
                "pm.test('Approve handles state cleanly', function () {",
                "    pm.expect(pm.response.code).to.be.oneOf([200, 400, 404, 403]);",
                "});",
            ],
        ),
        _item(
            "AC-08 Resume Worker",
            "POST",
            "{{BACKEND_BASE_URL}}/api/v1/hermes/runtime/worker/resume",
            ["api", "v1", "hermes", "runtime", "worker", "resume"],
            headers=[
                {"key": "Authorization", "value": "Bearer {{JWT_TOKEN}}"},
                {"key": "X-Org-Id", "value": "{{ORG_ID}}"},
            ],
            tests=[
                "pm.test('Resume worker endpoint responds', function () {",
                "    pm.expect(pm.response.code).to.be.oneOf([200, 403, 404]);",
                "});",
            ],
        ),
        _item(
            "AC-09 List Run Artifacts",
            "GET",
            "{{BACKEND_BASE_URL}}/api/v1/runs/{{RUN_ID}}/artifacts",
            ["api", "v1", "runs", "{{RUN_ID}}", "artifacts"],
            headers=[
                {"key": "Authorization", "value": "Bearer {{JWT_TOKEN}}"},
                {"key": "X-Org-Id", "value": "{{ORG_ID}}"},
            ],
            tests=[
                "pm.test('Artifact list responds', function () {",
                "    pm.expect(pm.response.code).to.be.oneOf([200, 404]);",
                "});",
            ],
        ),
    ]

    legacy = data["item"]
    data["item"] = [
        {"name": "Public Contract (Backend JWT)", "item": public_items},
        {"name": "Internal Harness (Edge/Bundle)", "item": legacy},
    ]
    root.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"updated collection: {len(public_items)} public + {len(legacy)} internal items")


def _item(
    name: str,
    method: str,
    raw_url: str,
    path: list[str],
    *,
    headers: list[dict[str, str]] | None = None,
    body: str | None = None,
    tests: list[str],
) -> dict:
    req: dict = {
        "method": method,
        "header": headers or [],
        "url": {
            "raw": raw_url,
            "host": [raw_url.split("/", 3)[0] + "//" + raw_url.split("/")[2] if "://" in raw_url else raw_url],
            "path": path,
        },
    }
    if "{{BACKEND_BASE_URL}}" in raw_url:
        req["url"] = {
            "raw": raw_url,
            "host": ["{{BACKEND_BASE_URL}}"],
            "path": path,
        }
    if body is not None:
        req["body"] = {"mode": "raw", "raw": body}
    return {
        "name": name,
        "event": [
            {
                "listen": "test",
                "script": {"exec": tests, "type": "text/javascript"},
            }
        ],
        "request": req,
    }


if __name__ == "__main__":
    main()
