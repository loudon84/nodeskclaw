#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

BACKEND_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_HOME = BACKEND_ROOT / "contracts" / "work-expert"
SKILL_RUN_CONTRACTS_HOME = BACKEND_ROOT / "contracts" / "skill-run"

P0_TEST_FILES = [
    "tests/expert_gateway/test_mcp_capability_token.py",
    "tests/expert_gateway/test_invocation_idempotency.py",
    "tests/hermes_skill/test_task_owner_policy.py",
    "tests/hermes_skill/test_cancel_safe_api_server.py",
    "tests/hermes_skill/test_retry_copies_routing_contract.py",
    "tests/hermes_skill/test_duplicate_completion.py",
    "tests/hermes_skill/test_result_content_separation.py",
    "tests/hermes_skill/test_progress_stages_minimum.py",
    "tests/contracts/test_contracts_check.py",
    "tests/contracts/test_openapi_response_schemas.py",
    "tests/contracts/test_mcp_tools_list_annotations.py",
]


def contract_root(version: str | None = None) -> Path:
    if version:
        return CONTRACTS_HOME / f"v{version}"
    try:
        from app.contracts.work_expert.constants import WORK_EXPERT_CONTRACT_VERSION

        return CONTRACTS_HOME / f"v{WORK_EXPERT_CONTRACT_VERSION}"
    except ImportError:
        return CONTRACTS_HOME / "v1.0.2"


CONTRACT_ROOT = CONTRACTS_HOME / "v1.0.2"


def _git_head() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=BACKEND_ROOT.parent,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_empty_json_schema(schema) -> bool:
    if schema is None:
        return True
    if schema == {}:
        return True
    if not isinstance(schema, dict):
        return False
    if schema.get("$ref") or schema.get("type") or schema.get("properties"):
        return False
    if schema.get("oneOf") or schema.get("anyOf") or schema.get("allOf") or schema.get("items"):
        return False
    return True


def _collect_refs(node, acc: set[str]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            acc.add(ref.rsplit("/", 1)[-1])
        for value in node.values():
            _collect_refs(value, acc)
    elif isinstance(node, list):
        for value in node:
            _collect_refs(value, acc)


def _prune_openapi_components(openapi: dict) -> dict:
    schemas = (openapi.get("components") or {}).get("schemas") or {}
    needed: set[str] = set()
    _collect_refs(openapi.get("paths"), needed)
    changed = True
    while changed:
        changed = False
        for name in list(needed):
            schema = schemas.get(name)
            if not schema:
                continue
            before = len(needed)
            _collect_refs(schema, needed)
            if len(needed) > before:
                changed = True
    openapi["components"] = {
        "schemas": {name: schemas[name] for name in sorted(needed) if name in schemas}
    }
    return openapi


def _strip_empty_200_json_when_other_media(openapi: dict) -> dict:
    for path_item in (openapi.get("paths") or {}).values():
        if not isinstance(path_item, dict):
            continue
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            content = (
                operation.get("responses", {})
                .get("200", {})
                .get("content")
            )
            if not isinstance(content, dict):
                continue
            json_body = content.get("application/json")
            if json_body and is_empty_json_schema(json_body.get("schema")):
                if any(media != "application/json" for media in content):
                    content.pop("application/json", None)
    return openapi


def assert_non_empty_200_schemas(openapi: dict, paths: list[str]) -> None:
    empty: list[str] = []
    for path in paths:
        path_item = openapi.get("paths", {}).get(path) or {}
        for method, operation in path_item.items():
            if method.startswith("x-") or not isinstance(operation, dict):
                continue
            content = operation.get("responses", {}).get("200", {}).get("content") or {}
            if not content:
                empty.append(f"{method.upper()} {path} missing 200 content")
                continue
            for media, body in content.items():
                if is_empty_json_schema((body or {}).get("schema")):
                    empty.append(f"{method.upper()} {path} {media}")
    if empty:
        raise SystemExit("Empty OpenAPI 200 response schema: " + "; ".join(empty))


def _load_openapi_subset() -> dict:
    from app.contracts.work_expert.constants import (
        WORK_EXPERT_CONTRACT_VERSION,
        WORK_EXPERT_OPENAPI_PATHS,
    )
    from app.main import app

    full = app.openapi()
    filtered_paths = {
        path: full["paths"][path]
        for path in WORK_EXPERT_OPENAPI_PATHS
        if path in full.get("paths", {})
    }
    missing = [path for path in WORK_EXPERT_OPENAPI_PATHS if path not in full.get("paths", {})]
    if missing:
        raise SystemExit(f"OpenAPI missing contract paths: {missing}")
    openapi = {
        "openapi": full.get("openapi", "3.1.0"),
        "info": {
            "title": "WORK-EXPERT-CONTRACT",
            "version": WORK_EXPERT_CONTRACT_VERSION,
        },
        "paths": filtered_paths,
        "components": full.get("components", {}),
    }
    openapi = _prune_openapi_components(openapi)
    openapi = _strip_empty_200_json_when_other_media(openapi)
    assert_non_empty_200_schemas(openapi, WORK_EXPERT_OPENAPI_PATHS)
    return openapi


def _model_schema(model) -> dict:
    return model.model_json_schema(mode="serialization")


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _artifact_files(root: Path) -> list[Path]:
    patterns = [
        "openapi.yaml",
        "RELEASE.md",
        "events/*.schema.json",
        "mcp/*.schema.json",
        "fixtures/*",
        "evidence/*",
    ]
    files: list[Path] = []
    for pattern in patterns:
        files.extend(sorted(root.glob(pattern)))
    return [path for path in files if path.is_file()]


def _build_manifest(file_hashes: dict[str, str], backend_commit: str) -> dict:
    from app.contracts.work_expert.constants import (
        WORK_EXPERT_CAPABILITIES,
        WORK_EXPERT_CONTRACT_NAME,
        WORK_EXPERT_CONTRACT_VERSION,
        WORK_EXPERT_TAG_NAME,
    )

    return {
        "contractName": WORK_EXPERT_CONTRACT_NAME,
        "contractVersion": WORK_EXPERT_CONTRACT_VERSION,
        "provider": "nodeskclaw-backend",
        "consumer": "smc-copilot/apps/work",
        "backendCommit": backend_commit,
        "tagName": WORK_EXPERT_TAG_NAME,
        "tagTargetCommit": None,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "openapiVersion": "3.1.0",
        "eventSchemaVersion": "1.0.0",
        "artifacts": file_hashes,
        "capabilities": dict(WORK_EXPERT_CAPABILITIES),
        "queueLimits": {
            "orgMaxQueued": 1000,
            "userMaxRunning": 3,
            "skillMaxRunning": 10,
            "agentMaxRunningDefault": 5,
            "workerBatchSize": 5,
            "workerSequential": True,
            "loadGate": WORK_EXPERT_CAPABILITIES["loadGate"],
        },
    }


def _fixture_payloads() -> dict[str, dict | list | str]:
    return {
        "fixtures/catalog-tools-list.json": {
            "jsonrpc": "2.0",
            "id": "list-root",
            "result": {
                "tools": [
                    {
                        "name": "call-prep",
                        "description": "Customer research expert",
                        "inputSchema": {"type": "object", "properties": {}},
                        "annotations": {
                            "kind": "expert",
                            "slug": "call-prep",
                            "displayName": "客户调研专家",
                            "status": "ready",
                            "publicSkillCount": 3,
                            "callableSkillCount": 2,
                        },
                    }
                ]
            },
        },
        "fixtures/skill-tools-list.json": {
            "jsonrpc": "2.0",
            "id": "list-skill",
            "result": {
                "tools": [
                    {
                        "name": "customer-profiling",
                        "description": "Profile a customer",
                        "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}},
                        "annotations": {
                            "displayName": "客户画像",
                            "status": "ready",
                            "callEnabled": True,
                            "riskLevel": "low",
                            "approvalMode": "none",
                        },
                    }
                ]
            },
        },
        "fixtures/catalog-tools-list-missing-display-name.json": {
            "jsonrpc": "2.0",
            "id": "list-root-no-display",
            "result": {
                "tools": [
                    {
                        "name": "call-prep",
                        "description": "Customer research expert",
                        "inputSchema": {"type": "object", "properties": {}},
                        "annotations": {
                            "kind": "expert",
                            "slug": "call-prep",
                            "status": "offline",
                            "publicSkillCount": 1,
                            "callableSkillCount": 0,
                        },
                    }
                ]
            },
        },
        "fixtures/skill-tools-list-call-disabled.json": {
            "jsonrpc": "2.0",
            "id": "list-skill-disabled",
            "result": {
                "tools": [
                    {
                        "name": "restricted-skill",
                        "description": "Requires approval",
                        "inputSchema": {"type": "object", "properties": {}},
                        "annotations": {
                            "status": "ready",
                            "callEnabled": False,
                            "riskLevel": "high",
                            "approvalMode": "approval_required",
                        },
                    }
                ]
            },
        },
        "fixtures/invalid-tool-annotations.json": {
            "jsonrpc": "2.0",
            "id": "list-invalid",
            "result": {
                "tools": [
                    {
                        "name": "call-prep",
                        "inputSchema": {"type": "object", "properties": {}},
                        "annotations": {
                            "kind": "expert",
                            "slug": "call-prep",
                            "status": "ready",
                            "publicSkillCount": -1,
                            "callableSkillCount": 0,
                        },
                    }
                ]
            },
        },
        "fixtures/tools-call-accepted.json": {
            "jsonrpc": "2.0",
            "id": "call-1",
            "result": {
                "content": [{"type": "text", "text": "任务已启动，正在由专家执行。"}],
                "structuredContent": {
                    "committed": True,
                    "task_id": "task-00000000-0000-4000-8000-000000000001",
                    "task_no": "TASK-org1-abcd1234",
                    "status": "running",
                    "event_stream": "/api/v1/hermes/tasks/task-00000000-0000-4000-8000-000000000001/events?token=sse_test",
                    "event_url": "/api/v1/hermes/tasks/task-00000000-0000-4000-8000-000000000001/events",
                    "event_token_url": "/api/v1/hermes/tasks/task-00000000-0000-4000-8000-000000000001/events-token",
                    "result_url": "/api/v1/hermes/tasks/task-00000000-0000-4000-8000-000000000001/result",
                    "artifact_url": "/api/v1/hermes/tasks/task-00000000-0000-4000-8000-000000000001/artifacts",
                    "wait_strategy": {
                        "type": "sse",
                        "fallback": "poll",
                        "poll_url": "/api/v1/hermes/tasks/task-00000000-0000-4000-8000-000000000001",
                        "poll_tool": "nodeskclaw_task_wait",
                        "result_url": "/api/v1/hermes/tasks/task-00000000-0000-4000-8000-000000000001/result",
                    },
                    "catalog_slug": "call-prep",
                    "skill_name": "customer-profiling",
                    "invocation_id": "invocation-1",
                },
                "isError": False,
            },
        },
        "fixtures/task-snapshot-running.json": {
            "code": 0,
            "message": "success",
            "data": {
                "task": {"id": "task-1", "status": "running"},
                "status": "running",
                "timeline": [],
                "result": {"ready": False, "summary": None, "result_content": None, "content": None},
                "artifacts": {"ready": False, "items": [], "server_artifacts": []},
                "links": {
                    "event_stream": "/api/v1/hermes/tasks/task-1/events",
                    "result_url": "/api/v1/hermes/tasks/task-1/result",
                    "artifact_url": "/api/v1/hermes/tasks/task-1/artifacts",
                },
                "last_events": [],
            },
        },
        "fixtures/task-result-completed.json": {
            "code": 0,
            "message": "success",
            "data": {
                "ready": True,
                "status": "completed",
                "task_id": "task-1",
                "task_no": "TASK-org1-abcd1234",
                "result_summary": "short summary",
                "result_content": "full result body that is longer than summary",
                "content": "full result body that is longer than summary",
            },
        },
        "fixtures/task-artifacts.json": {
            "code": 0,
            "message": "success",
            "data": [
                {
                    "id": "artifact-1",
                    "org_id": "org-1",
                    "task_id": "task-1",
                    "created_by": "user-1",
                    "file_name": "article.md",
                    "file_path": "article.md",
                    "content_type": "text/markdown",
                    "size_bytes": 128,
                    "sha256": "abc123",
                    "preview_url": "/api/v1/hermes/artifacts/artifact-1/preview",
                    "download_url": "/api/v1/hermes/artifacts/artifact-1/download",
                }
            ],
            "server_artifacts": [],
            "artifact_mode": "pull_only",
        },
        "fixtures/http-task-get.json": {
            "code": 0,
            "message": "success",
            "data": {
                "id": "task-1",
                "org_id": "org-1",
                "task_no": "TASK-org1-abcd1234",
                "status": "running",
            },
        },
        "fixtures/http-events-token.json": {
            "code": 0,
            "message": "success",
            "data": {
                "event_url": "/api/v1/hermes/tasks/task-1/events?token=sse_test",
                "expires_in": 300,
                "expires_at": "2026-08-23T03:00:00+00:00",
            },
        },
        "fixtures/http-artifact-preview.json": {
            "code": 0,
            "message": "success",
            "data": {
                "artifact_id": "artifact-1",
                "org_id": "org-1",
                "task_id": "task-1",
                "created_by": "user-1",
                "file_name": "article.md",
                "content_type": "text/markdown",
                "preview_type": "text",
                "content": "# draft",
                "truncated": False,
                "size_bytes": 8,
                "sha256": "abc123",
                "preview_url": "/api/v1/hermes/artifacts/artifact-1/preview",
                "download_url": "/api/v1/hermes/artifacts/artifact-1/download",
            },
        },
        "fixtures/http-error-owner-forbidden.json": {
            "code": 40300,
            "error_code": 40300,
            "message_key": "errors.task.owner_forbidden",
            "message": "无权访问该任务",
            "data": None,
        },
        "fixtures/http-error-not-found.json": {
            "code": 40400,
            "error_code": 40400,
            "message_key": "errors.task.not_found",
            "message": "任务不存在",
            "data": None,
        },
        "fixtures/http-error-cannot-cancel.json": {
            "code": 40000,
            "error_code": 40000,
            "message_key": "errors.task.cannot_cancel",
            "message": "当前任务状态不可取消",
            "data": None,
        },
        "fixtures/json-rpc-error.json": {
            "jsonrpc": "2.0",
            "id": "err-1",
            "error": {
                "code": -32022,
                "message": "Permission denied",
                "data": {"errorCode": "EXPERT_PERMISSION_DENIED"},
            },
        },
    }


def generate_contracts() -> None:
    from app.schemas.hermes_skill.sse_events import (
        TaskArtifactReadyEvent,
        TaskCompletedEvent,
        TaskEventEnvelope,
        TaskFailedEvent,
        TaskProgressEvent,
        TaskStartedEvent,
        TaskTimelineEvent,
    )
    from app.schemas.work_expert.mcp_jsonrpc import (
        CatalogToolAnnotations,
        JsonRpcErrorResponse,
        JsonRpcRequest,
        SkillToolAnnotations,
        ToolsCallAcceptedResult,
        ToolsListResult,
    )

    root = contract_root()
    root.mkdir(parents=True, exist_ok=True)
    (root / "events").mkdir(exist_ok=True)
    (root / "mcp").mkdir(exist_ok=True)
    (root / "fixtures").mkdir(exist_ok=True)
    (root / "evidence").mkdir(exist_ok=True)

    openapi = _load_openapi_subset()
    (root / "openapi.yaml").write_text(
        yaml.safe_dump(openapi, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    event_models = {
        "task-event.schema.json": TaskEventEnvelope,
        "task-started.schema.json": TaskStartedEvent,
        "task-progress.schema.json": TaskProgressEvent,
        "task-timeline.schema.json": TaskTimelineEvent,
        "task-artifact-ready.schema.json": TaskArtifactReadyEvent,
        "task-completed.schema.json": TaskCompletedEvent,
        "task-failed.schema.json": TaskFailedEvent,
    }
    for filename, model in event_models.items():
        _write_json(root / "events" / filename, _model_schema(model))

    mcp_models = {
        "tools-list.request.schema.json": JsonRpcRequest,
        "tools-list.response.schema.json": ToolsListResult,
        "catalog-tool-annotations.schema.json": CatalogToolAnnotations,
        "skill-tool-annotations.schema.json": SkillToolAnnotations,
        "tools-call.request.schema.json": JsonRpcRequest,
        "tools-call.response.schema.json": ToolsCallAcceptedResult,
        "json-rpc-error.schema.json": JsonRpcErrorResponse,
    }
    for filename, model in mcp_models.items():
        _write_json(root / "mcp" / filename, _model_schema(model))

    for relative_path, payload in _fixture_payloads().items():
        target = root / relative_path
        _write_json(target, payload)

    evidence_src = CONTRACTS_HOME / "v1.0.1" / "evidence" / "load-test-20-runs.json"
    evidence_dst = root / "evidence" / "load-test-20-runs.json"
    if evidence_src.is_file():
        evidence_dst.write_bytes(evidence_src.read_bytes())

    sse_replay = "\n".join(
        [
            json.dumps(
                {
                    "event": "task.started",
                    "task_id": "task-1",
                    "timestamp": "2026-08-23T02:00:00+00:00",
                    "event_type": "task.started",
                    "event_seq": 2,
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "event": "task.progress",
                    "task_id": "task-1",
                    "timestamp": "2026-08-23T02:00:01+00:00",
                    "event_type": "hermes.run.delta",
                    "event_seq": 3,
                    "stage": "preparing",
                },
                ensure_ascii=False,
            ),
            json.dumps(
                {
                    "event": "task.completed",
                    "task_id": "task-1",
                    "timestamp": "2026-08-23T02:00:10+00:00",
                    "event_type": "task.completed",
                    "event_seq": 10,
                    "result": {"summary": "done", "content": "full body"},
                },
                ensure_ascii=False,
            ),
        ]
    ) + "\n"
    (root / "fixtures" / "sse-replay.ndjson").write_text(sse_replay, encoding="utf-8")

    backend_commit = _git_head()
    file_hashes = {
        str(path.relative_to(root)).replace("\\", "/"): _sha256_file(path)
        for path in _artifact_files(root)
        if path.name != "manifest.json"
    }
    manifest = _build_manifest(file_hashes, backend_commit)
    _write_json(root / "manifest.json", manifest)

    checksum_lines = [f"{digest}  {relative}" for relative, digest in sorted(file_hashes.items())]
    (root / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    print(f"Generated WORK-EXPERT-CONTRACT at {root} (backendCommit={backend_commit})")


def _read_manifest(root: Path) -> dict:
    return json.loads((root / "manifest.json").read_text(encoding="utf-8"))


def _validate_checksums(root: Path) -> None:
    checksum_path = root / "SHA256SUMS"
    if not checksum_path.exists():
        raise SystemExit(f"SHA256SUMS missing: {root}")
    listed: dict[str, str] = {}
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, relative = line.split("  ", 1)
        listed[relative] = digest
        path = root / relative
        if not path.is_file():
            raise SystemExit(f"SHA256SUMS lists missing file: {relative}")
        actual = _sha256_file(path)
        if actual != digest:
            raise SystemExit(f"SHA256 mismatch for {relative}")
    manifest = _read_manifest(root)
    artifacts = manifest.get("artifacts") or {}
    for relative, digest in artifacts.items():
        if relative == "manifest.json":
            continue
        path = root / relative
        if not path.is_file():
            raise SystemExit(f"manifest.artifacts lists missing file: {relative}")
        if _sha256_file(path) != digest:
            raise SystemExit(f"manifest hash mismatch for {relative}")
        if listed.get(relative) != digest:
            raise SystemExit(f"SHA256SUMS/manifest disagree on {relative}")


def _validate_fixtures(root: Path) -> None:
    import jsonschema

    from app.schemas.hermes_skill.task_result_contract import TaskResultResponse, TaskSnapshotResponse
    from app.schemas.work_expert.http_responses import (
        ApiErrorBody,
        ArtifactPreviewHttpResponse,
        EventsTokenResponse,
        TaskArtifactsHttpData,
        TaskGetResponse,
    )

    schema_map = {
        "fixtures/catalog-tools-list.json": ("mcp/tools-list.response.schema.json", "result"),
        "fixtures/skill-tools-list.json": ("mcp/tools-list.response.schema.json", "result"),
        "fixtures/catalog-tools-list-missing-display-name.json": (
            "mcp/tools-list.response.schema.json",
            "result",
        ),
        "fixtures/skill-tools-list-call-disabled.json": (
            "mcp/tools-list.response.schema.json",
            "result",
        ),
        "fixtures/tools-call-accepted.json": ("mcp/tools-call.response.schema.json", "result"),
        "fixtures/json-rpc-error.json": ("mcp/json-rpc-error.schema.json", None),
    }
    for fixture_rel, schema_info in schema_map.items():
        fixture = json.loads((root / fixture_rel).read_text(encoding="utf-8"))
        schema_rel, key = schema_info
        schema = json.loads((root / schema_rel).read_text(encoding="utf-8"))
        payload = fixture if key is None else fixture[key]
        jsonschema.validate(payload, schema)

    invalid = json.loads((root / "fixtures/invalid-tool-annotations.json").read_text(encoding="utf-8"))
    tools_schema = json.loads((root / "mcp/tools-list.response.schema.json").read_text(encoding="utf-8"))
    try:
        jsonschema.validate(invalid["result"], tools_schema)
    except jsonschema.ValidationError:
        pass
    else:
        raise SystemExit("fixtures/invalid-tool-annotations.json unexpectedly passed schema")

    pydantic_map = {
        "fixtures/task-snapshot-running.json": (TaskSnapshotResponse, "data"),
        "fixtures/task-result-completed.json": (TaskResultResponse, "data"),
        "fixtures/task-artifacts.json": (TaskArtifactsHttpData, None),
        "fixtures/http-task-get.json": (TaskGetResponse, None),
        "fixtures/http-events-token.json": (EventsTokenResponse, None),
        "fixtures/http-artifact-preview.json": (ArtifactPreviewHttpResponse, None),
        "fixtures/http-error-owner-forbidden.json": (ApiErrorBody, None),
        "fixtures/http-error-not-found.json": (ApiErrorBody, None),
        "fixtures/http-error-cannot-cancel.json": (ApiErrorBody, None),
    }
    for fixture_rel, (model, key) in pydantic_map.items():
        fixture = json.loads((root / fixture_rel).read_text(encoding="utf-8"))
        payload = fixture if key is None else fixture[key]
        model.model_validate(payload)


def _validate_frozen_versions() -> None:
    from app.contracts.work_expert.constants import WORK_EXPERT_FROZEN_VERSIONS

    for version in WORK_EXPERT_FROZEN_VERSIONS:
        root = CONTRACTS_HOME / f"v{version}"
        if not root.exists():
            raise SystemExit(f"Frozen contract missing: {root}")
        _validate_checksums(root)


def _validate_skill_run_fixtures(root: Path) -> None:
    import jsonschema

    schema_map = {
        "fixtures/skill-tools-list.json": (
            "mcp/tools-list.response.schema.json",
            "result",
        ),
        "fixtures/tools-call-accepted.json": ("mcp/tools-call.response.schema.json", "result"),
    }
    for fixture_rel, schema_info in schema_map.items():
        fixture = json.loads((root / fixture_rel).read_text(encoding="utf-8"))
        schema_rel, key = schema_info
        schema = json.loads((root / schema_rel).read_text(encoding="utf-8"))
        payload = fixture if key is None else fixture[key]
        jsonschema.validate(payload, schema)


def check_contracts(release: bool = False) -> None:
    sys.path.insert(0, str(BACKEND_ROOT))
    root = contract_root()
    if not root.exists():
        raise SystemExit(f"Contract directory missing: {root}")

    for rel_path in P0_TEST_FILES:
        if not (BACKEND_ROOT / rel_path).exists():
            raise SystemExit(f"Missing required P0 test file: {rel_path}")

    _validate_frozen_versions()
    _validate_checksums(root)

    manifest = _read_manifest(root)
    if manifest.get("backendCommit") != _git_head():
        if release:
            raise SystemExit("manifest.backendCommit does not match current HEAD in release mode")
        print("warning: manifest.backendCommit differs from current HEAD; run generate after implementation commit")

    _validate_fixtures(root)

    current_openapi = yaml.safe_dump(_load_openapi_subset(), sort_keys=False, allow_unicode=True)
    committed_openapi = (root / "openapi.yaml").read_text(encoding="utf-8")
    if current_openapi != committed_openapi:
        raise SystemExit("OpenAPI drift detected; run contracts generate")

    from app.schemas.hermes_skill.sse_events import TaskProgressEvent

    current_progress_schema = json.dumps(_model_schema(TaskProgressEvent), sort_keys=True)
    committed_progress_schema = json.dumps(
        json.loads((root / "events" / "task-progress.schema.json").read_text(encoding="utf-8")),
        sort_keys=True,
    )
    if current_progress_schema != committed_progress_schema:
        raise SystemExit("SSE schema drift detected; run contracts generate")

    print("WORK-EXPERT-CONTRACT check passed")

    skill_run_root = SKILL_RUN_CONTRACTS_HOME / "v1.0.0"
    if skill_run_root.exists():
        _validate_checksums(skill_run_root)
        _validate_skill_run_fixtures(skill_run_root)
        print("SKILL-RUN-CONTRACT check passed")


def generate_skill_run_contracts() -> None:
    from app.schemas.skill_run.constants import (
        SKILL_RUN_CAPABILITIES,
        SKILL_RUN_CONTRACT_NAME,
        SKILL_RUN_CONTRACT_VERSION,
        SKILL_RUN_TAG_NAME,
    )
    from app.schemas.skill_run.mcp_jsonrpc import (
        ArtifactDescriptor,
        ExecutionSnapshot,
        RunEvent,
        RunRecord,
        SkillToolAnnotations,
        ToolsCallAcceptedResult,
        ToolsListResult,
    )
    from app.schemas.work_expert.mcp_jsonrpc import JsonRpcErrorResponse, JsonRpcRequest

    root = SKILL_RUN_CONTRACTS_HOME / f"v{SKILL_RUN_CONTRACT_VERSION}"
    root.mkdir(parents=True, exist_ok=True)
    (root / "mcp").mkdir(exist_ok=True)
    (root / "events").mkdir(exist_ok=True)
    (root / "runs").mkdir(exist_ok=True)
    (root / "fixtures").mkdir(exist_ok=True)

    mcp_models = {
        "tools-list.request.schema.json": JsonRpcRequest,
        "tools-list.response.schema.json": ToolsListResult,
        "skill-tool-annotations.schema.json": SkillToolAnnotations,
        "tools-call.request.schema.json": JsonRpcRequest,
        "tools-call.response.schema.json": ToolsCallAcceptedResult,
        "json-rpc-error.schema.json": JsonRpcErrorResponse,
    }
    for filename, model in mcp_models.items():
        _write_json(root / "mcp" / filename, _model_schema(model))

    _write_json(root / "events" / "run-event.schema.json", _model_schema(RunEvent))
    _write_json(root / "runs" / "run.schema.json", _model_schema(RunRecord))
    _write_json(root / "runs" / "execution-snapshot.schema.json", _model_schema(ExecutionSnapshot))
    _write_json(root / "runs" / "artifact-descriptor.schema.json", _model_schema(ArtifactDescriptor))

    _write_json(
        root / "fixtures" / "tools-call-accepted.json",
        {
            "jsonrpc": "2.0",
            "id": "call-1",
            "result": {
                "content": [{"type": "text", "text": "accepted"}],
                "structuredContent": {
                    "committed": True,
                    "run_id": "run-1",
                    "status": "QUEUED",
                    "tool_name": "writer_article_generate",
                    "event_stream": "/api/v1/runs/run-1/events?token=example",
                    "result_url": "/api/v1/runs/run-1/result",
                    "artifact_url": "/api/v1/runs/run-1/artifacts",
                    "execution_mode": "async_event",
                },
                "isError": False,
            },
        },
    )
    _write_json(
        root / "fixtures" / "skill-tools-list.json",
        {
            "jsonrpc": "2.0",
            "id": "list-1",
            "result": {
                "tools": [
                    {
                        "name": "writer_article_generate",
                        "title": "Writer",
                        "description": "Generate article",
                        "inputSchema": {"type": "object"},
                        "version": "1.0.0",
                        "category": "writer",
                        "annotations": {
                            "category": "writer",
                            "riskLevel": "low",
                            "requiresApproval": False,
                            "streaming": True,
                            "artifacts": True,
                            "version": "1.0.0",
                        },
                    }
                ]
            },
        },
    )

    release = (
        f"# {SKILL_RUN_CONTRACT_NAME} v{SKILL_RUN_CONTRACT_VERSION}\n\n"
        "Skill-first employee MCP and Run identity contract.\n"
        "Does not modify work-expert v1.0.2.\n"
    )
    (root / "RELEASE.md").write_text(release, encoding="utf-8")

    backend_commit = _git_head()
    file_hashes = {
        str(path.relative_to(root)).replace("\\", "/"): _sha256_file(path)
        for path in _artifact_files(root)
        if path.name != "manifest.json"
    }
    manifest = {
        "contractName": SKILL_RUN_CONTRACT_NAME,
        "contractVersion": SKILL_RUN_CONTRACT_VERSION,
        "provider": "nodeskclaw-backend",
        "consumer": "smc-copilot/apps/work",
        "backendCommit": backend_commit,
        "tagName": SKILL_RUN_TAG_NAME,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "artifacts": file_hashes,
        "capabilities": SKILL_RUN_CAPABILITIES,
    }
    _write_json(root / "manifest.json", manifest)
    checksum_lines = [f"{digest}  {relative}" for relative, digest in sorted(file_hashes.items())]
    (root / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    print(f"Generated {SKILL_RUN_CONTRACT_NAME} at {root} (backendCommit={backend_commit})")


def main() -> None:
    import os
    os.environ.setdefault("JWT_SECRET", "test-secret-key-for-jwt-generation-minimum-32-chars-long")
    os.environ.setdefault("ENCRYPTION_KEY", "test-encryption-key-for-aes-encryption-32-bytes-long")
    os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/nodeskclaw_test")

    parser = argparse.ArgumentParser(description="Contract generator/checker")
    sub = parser.add_subparsers(dest="command", required=True)
    generate_parser = sub.add_parser("generate", help="Generate contract artifacts")
    generate_parser.add_argument(
        "--family",
        choices=("work-expert", "skill-run", "all"),
        default="work-expert",
        help="Contract family to generate",
    )
    check_parser = sub.add_parser("check", help="Validate committed contract artifacts")
    check_parser.add_argument("--release", action="store_true")
    args = parser.parse_args()

    sys.path.insert(0, str(BACKEND_ROOT))
    if args.command == "generate":
        if args.family in ("work-expert", "all"):
            generate_contracts()
        if args.family in ("skill-run", "all"):
            generate_skill_run_contracts()
    else:
        check_contracts(release=args.release)


if __name__ == "__main__":
    main()
