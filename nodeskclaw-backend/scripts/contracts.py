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


def _run_event_v12_union_schema(models: tuple) -> dict:
    """Build oneOf schema with $defs hoisted to root so #/$defs refs resolve."""
    one_of: list[dict] = []
    all_defs: dict = {}
    for model in models:
        schema = _model_schema(model)
        defs = schema.pop("$defs", {}) or {}
        all_defs.update(defs)
        one_of.append({"title": model.__name__, **schema})
    result: dict = {"title": "RunEvent", "oneOf": one_of}
    if all_defs:
        result["$defs"] = all_defs
    return result


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _artifact_files(root: Path) -> list[Path]:
    patterns = [
        "openapi.yaml",
        "RELEASE.md",
        "events/*.schema.json",
        "mcp/*.schema.json",
        "runs/*.schema.json",
        "edge/*.schema.json",
        "installations/*.schema.json",
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
        "fixtures/edge-lease-renew.json": ("edge/lease-renew.schema.json", None),
        "fixtures/edge-artifact-upload.json": ("edge/artifact-upload.schema.json", None),
        "fixtures/desired-installation.json": ("installations/installation.schema.json", None),
    }
    for fixture_rel, schema_info in schema_map.items():
        fixture_path = root / fixture_rel
        if not fixture_path.exists():
            continue
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
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
        manifest = _read_manifest(skill_run_root)
        if release:
            if manifest.get("backendCommit") != _git_head():
                raise SystemExit("skill-run manifest.backendCommit does not match current HEAD in release mode")
            tag_name = manifest.get("tagName")
            if tag_name:
                tag_check = subprocess.run(
                    ["git", "tag", "-l", tag_name],
                    cwd=BACKEND_ROOT.parent,
                    capture_output=True,
                    text=True,
                )
                if not tag_check.stdout.strip():
                    raise SystemExit(f"skill-run contract tag '{tag_name}' not found in release mode")

    skill_run_v11_root = SKILL_RUN_CONTRACTS_HOME / "v1.1.0"
    if skill_run_v11_root.exists():
        _validate_checksums(skill_run_v11_root)
        _validate_skill_run_fixtures(skill_run_v11_root)
        _validate_skill_run_v11_negative_fixtures(skill_run_v11_root)
        manifest_v11 = _read_manifest(skill_run_v11_root)
        if release and manifest_v11.get("backendCommit") != _git_head():
            raise SystemExit("skill-run v1.1.0 manifest.backendCommit does not match current HEAD in release mode")

    skill_run_v12_root = SKILL_RUN_CONTRACTS_HOME / "v1.2.0"
    if skill_run_v12_root.exists():
        _validate_checksums(skill_run_v12_root)
        _validate_skill_run_fixtures(skill_run_v12_root)
        _validate_skill_run_v12_event_fixtures(skill_run_v12_root)
        _validate_skill_run_v12_negative_fixtures(skill_run_v12_root)
        manifest_v12 = _read_manifest(skill_run_v12_root)
        if release and manifest_v12.get("backendCommit") != _git_head():
            raise SystemExit("skill-run v1.2.0 manifest.backendCommit does not match current HEAD in release mode")

    print("SKILL-RUN-CONTRACT check passed")


def _validate_skill_run_v12_event_fixtures(root: Path) -> None:
    import jsonschema

    schema_path = root / "events" / "run-event.schema.json"
    if not schema_path.exists():
        raise SystemExit(f"Missing run-event schema: {schema_path}")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    for fixture_rel in (
        "fixtures/run-event-assistant-message.json",
        "fixtures/run-event-tool-call.json",
        "fixtures/run-event-artifact-persisted.json",
        "fixtures/run-event-reasoning-summary.json",
        "fixtures/run-event-clarify-requested.json",
        "fixtures/run-event-approval-requested.json",
        "fixtures/run-event-control-progress.json",
        "fixtures/run-event-control-created.json",
    ):
        fixture_path = root / fixture_rel
        if not fixture_path.exists():
            raise SystemExit(f"Missing skill-run v1.2 fixture: {fixture_rel}")
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        jsonschema.validate(fixture, schema)


def _validate_skill_run_v12_negative_fixtures(root: Path) -> None:
    import jsonschema

    schema_path = root / "events" / "run-event.schema.json"
    if not schema_path.exists():
        return
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    unknown_type = {
        "event_id": "evt-x",
        "run_id": "run-1",
        "event_type": "unknown.semantic",
        "event_seq": 1,
        "source": "agent",
        "timestamp": "2026-08-31T00:00:00Z",
        "payload": {},
    }
    try:
        jsonschema.validate(unknown_type, schema)
    except jsonschema.ValidationError:
        pass
    else:
        raise SystemExit("run-event.schema.json unexpectedly accepted unknown event_type")

    missing_category = {
        "event_id": "evt-y",
        "run_id": "run-1",
        "event_type": "tool.call",
        "event_seq": 1,
        "source": "agent",
        "timestamp": "2026-08-31T00:00:00Z",
        "payload": {"tool_name": "search"},
    }
    try:
        jsonschema.validate(missing_category, schema)
    except jsonschema.ValidationError:
        pass
    else:
        raise SystemExit("run-event.schema.json unexpectedly accepted tool.call missing required fields")


def _validate_skill_run_v11_negative_fixtures(root: Path) -> None:
    import jsonschema

    tools_schema_path = root / "mcp" / "tools-list.response.schema.json"
    if not tools_schema_path.exists():
        return
    tools_schema = json.loads(tools_schema_path.read_text(encoding="utf-8"))

    # Test invalid descriptor missing capabilityKind
    invalid_descriptor = {
        "tools": [
            {
                "name": "invalid_tool",
                "interactionMode": "chat",
                "supportsAttachments": False,
                "annotations": {"riskLevel": "low"},
            }
        ]
    }
    try:
        jsonschema.validate(invalid_descriptor, tools_schema)
    except jsonschema.ValidationError:
        pass
    else:
        raise SystemExit("tools-list.response.schema.json unexpectedly accepted descriptor missing capabilityKind")


def generate_skill_run_contracts() -> None:
    from app.api.internal_edge import (
        EdgeActualReportBody,
        EdgeArtifactUploadBody,
        EdgeLeaseRenewBody,
    )
    from app.schemas.hermes_skill.skill_installation import InstallationRead
    from app.schemas.skill_run.constants import (
        SKILL_RUN_CAPABILITIES,
        SKILL_RUN_CONTRACT_NAME,
        SKILL_RUN_CONTRACT_VERSION,
        SKILL_RUN_CONTRACT_VERSION_V11,
        SKILL_RUN_CONTRACT_VERSION_V12,
        SKILL_RUN_TAG_NAME,
    )
    from app.schemas.skill_run.mcp_jsonrpc import (
        ArtifactDescriptor,
        ExecutionSnapshot,
        RUN_EVENT_V12_MODELS,
        RunEvent,
        RunRecord,
        SkillToolAnnotations,
        SkillToolAnnotationsV11,
        SkillToolDescriptorV11,
        ToolsCallAcceptedResult,
        ToolsCallAcceptedResultV11,
        ToolsListResult,
        ToolsListResultV11,
    )
    from app.schemas.work_expert.mcp_jsonrpc import JsonRpcErrorResponse, JsonRpcRequest

    root_v10 = SKILL_RUN_CONTRACTS_HOME / f"v{SKILL_RUN_CONTRACT_VERSION}"
    if not root_v10.exists():
        root_v10.mkdir(parents=True, exist_ok=True)
        (root_v10 / "mcp").mkdir(exist_ok=True)
        (root_v10 / "events").mkdir(exist_ok=True)
        (root_v10 / "runs").mkdir(exist_ok=True)
        (root_v10 / "edge").mkdir(exist_ok=True)
        (root_v10 / "installations").mkdir(exist_ok=True)
        (root_v10 / "fixtures").mkdir(exist_ok=True)

        mcp_models = {
            "tools-list.request.schema.json": JsonRpcRequest,
            "tools-list.response.schema.json": ToolsListResult,
            "skill-tool-annotations.schema.json": SkillToolAnnotations,
            "tools-call.request.schema.json": JsonRpcRequest,
            "tools-call.response.schema.json": ToolsCallAcceptedResult,
            "json-rpc-error.schema.json": JsonRpcErrorResponse,
        }
        for filename, model in mcp_models.items():
            _write_json(root_v10 / "mcp" / filename, _model_schema(model))

        _write_json(root_v10 / "events" / "run-event.schema.json", _model_schema(RunEvent))
        _write_json(root_v10 / "runs" / "run.schema.json", _model_schema(RunRecord))
        _write_json(root_v10 / "runs" / "execution-snapshot.schema.json", _model_schema(ExecutionSnapshot))
        _write_json(root_v10 / "runs" / "artifact-descriptor.schema.json", _model_schema(ArtifactDescriptor))

        _write_json(root_v10 / "edge" / "lease-renew.schema.json", _model_schema(EdgeLeaseRenewBody))
        _write_json(root_v10 / "edge" / "artifact-upload.schema.json", _model_schema(EdgeArtifactUploadBody))
        _write_json(root_v10 / "installations" / "actual-report.schema.json", _model_schema(EdgeActualReportBody))
        _write_json(root_v10 / "installations" / "installation.schema.json", _model_schema(InstallationRead))

        _write_json(
            root_v10 / "fixtures" / "edge-lease-renew.json",
            {
                "extend_seconds": 60,
                "delivery_generation": 1,
            },
        )
        _write_json(
            root_v10 / "fixtures" / "edge-artifact-upload.json",
            {
                "artifact_id": "art-1",
                "name": "result.json",
                "content_base64": "eyJyZXN1bHQiOiA0Mn0=",
                "checksum_sha256": "35a9e381b1a27567549b5f8a6f783c167ebf809630c3991446f41f72a3e01c5c",
                "size_bytes": 16,
                "content_type": "application/json",
                "run_generation": 1,
            },
        )
        _write_json(
            root_v10 / "fixtures" / "desired-installation.json",
            {
                "id": "inst-1",
                "org_id": "org-1",
                "agent_id": "agent-1",
                "skill_id": "skill-1",
                "target_kind": "edge",
                "edge_node_id": "edge-node-1",
                "installed_version": "1.0.0",
                "status": "installed",
                "actual_status": "synced",
                "desired_generation": 1,
                "actual_generation": 1,
                "reconciled_status": "synced",
                "created_at": "2026-08-28T00:00:00Z",
                "updated_at": "2026-08-28T00:00:00Z",
            },
        )
        _write_json(
            root_v10 / "fixtures" / "tools-call-accepted.json",
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
            root_v10 / "fixtures" / "skill-tools-list.json",
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
        (root_v10 / "RELEASE.md").write_text(release, encoding="utf-8")

        backend_commit = _git_head()
        file_hashes = {
            str(path.relative_to(root_v10)).replace("\\", "/"): _sha256_file(path)
            for path in _artifact_files(root_v10)
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
        _write_json(root_v10 / "manifest.json", manifest)
        checksum_lines = [f"{digest}  {relative}" for relative, digest in sorted(file_hashes.items())]
        (root_v10 / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
        print(f"Generated {SKILL_RUN_CONTRACT_NAME} at {root_v10} (backendCommit={backend_commit})")

    # Generate v1.1.0 contract only when missing (freeze committed package).
    root_v11 = SKILL_RUN_CONTRACTS_HOME / f"v{SKILL_RUN_CONTRACT_VERSION_V11}"
    if root_v11.exists() and (root_v11 / "SHA256SUMS").exists():
        print(f"Kept frozen {SKILL_RUN_CONTRACT_NAME} at {root_v11}")
    else:
        root_v11.mkdir(parents=True, exist_ok=True)
        (root_v11 / "mcp").mkdir(exist_ok=True)
        (root_v11 / "events").mkdir(exist_ok=True)
        (root_v11 / "runs").mkdir(exist_ok=True)
        (root_v11 / "edge").mkdir(exist_ok=True)
        (root_v11 / "installations").mkdir(exist_ok=True)
        (root_v11 / "fixtures").mkdir(exist_ok=True)

        mcp_models_v11 = {
            "tools-list.request.schema.json": JsonRpcRequest,
            "tools-list.response.schema.json": ToolsListResultV11,
            "skill-tool-annotations.schema.json": SkillToolAnnotationsV11,
            "tools-call.request.schema.json": JsonRpcRequest,
            "tools-call.response.schema.json": ToolsCallAcceptedResultV11,
            "json-rpc-error.schema.json": JsonRpcErrorResponse,
        }
        for filename, model in mcp_models_v11.items():
            _write_json(root_v11 / "mcp" / filename, _model_schema(model))

        _write_json(root_v11 / "events" / "run-event.schema.json", _model_schema(RunEvent))
        _write_json(root_v11 / "runs" / "run.schema.json", _model_schema(RunRecord))
        _write_json(root_v11 / "runs" / "execution-snapshot.schema.json", _model_schema(ExecutionSnapshot))
        _write_json(root_v11 / "runs" / "artifact-descriptor.schema.json", _model_schema(ArtifactDescriptor))

        _write_json(root_v11 / "edge" / "lease-renew.schema.json", _model_schema(EdgeLeaseRenewBody))
        _write_json(root_v11 / "edge" / "artifact-upload.schema.json", _model_schema(EdgeArtifactUploadBody))
        _write_json(root_v11 / "installations" / "actual-report.schema.json", _model_schema(EdgeActualReportBody))
        _write_json(root_v11 / "installations" / "installation.schema.json", _model_schema(InstallationRead))

        _write_json(
            root_v11 / "fixtures" / "edge-lease-renew.json",
            {
                "extend_seconds": 60,
                "delivery_generation": 1,
            },
        )
        _write_json(
            root_v11 / "fixtures" / "edge-artifact-upload.json",
            {
                "artifact_id": "art-1",
                "name": "result.json",
                "content_base64": "eyJyZXN1bHQiOiA0Mn0=",
                "checksum_sha256": "35a9e381b1a27567549b5f8a6f783c167ebf809630c3991446f41f72a3e01c5c",
                "size_bytes": 16,
                "content_type": "application/json",
                "run_generation": 1,
            },
        )
        _write_json(
            root_v11 / "fixtures" / "desired-installation.json",
            {
                "id": "inst-1",
                "org_id": "org-1",
                "agent_id": "agent-1",
                "skill_id": "skill-1",
                "target_kind": "edge",
                "edge_node_id": "edge-node-1",
                "installed_version": "1.0.0",
                "status": "installed",
                "actual_status": "synced",
                "desired_generation": 1,
                "actual_generation": 1,
                "reconciled_status": "synced",
                "created_at": "2026-08-28T00:00:00Z",
                "updated_at": "2026-08-28T00:00:00Z",
            },
        )
        _write_json(
            root_v11 / "fixtures" / "tools-call-accepted.json",
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
                        "contract_version": "1.1.0",
                    },
                    "isError": False,
                },
            },
        )
        _write_json(
            root_v11 / "fixtures" / "skill-tools-list.json",
            {
                "jsonrpc": "2.0",
                "id": "list-1",
                "result": {
                    "tools": [
                        {
                            "name": "writer_article_generate",
                            "title": "Writer",
                            "description": "Generate article",
                            "inputSchema": {"type": "object", "properties": {"prompt": {"type": "string"}}},
                            "version": "1.1.0",
                            "category": "writer",
                            "capabilityKind": "skill",
                            "interactionMode": "chat",
                            "promptField": "prompt",
                            "supportsAttachments": False,
                            "skillReleaseId": "rel-12345",
                            "skillReleaseDigest": "digest-abcdef",
                            "annotations": {
                                "category": "writer",
                                "riskLevel": "low",
                                "requiresApproval": False,
                                "approvalMode": "none",
                                "streaming": True,
                                "artifacts": True,
                                "version": "1.1.0",
                            },
                        }
                    ]
                },
            },
        )

        release_v11 = (
            f"# {SKILL_RUN_CONTRACT_NAME} v{SKILL_RUN_CONTRACT_VERSION_V11}\n\n"
            "Skill-first employee MCP and Run identity contract v1.1.0.\n"
            "Adds Catalog v1.1 descriptors and optional contract_version.\n"
        )
        (root_v11 / "RELEASE.md").write_text(release_v11, encoding="utf-8")

        backend_commit = _git_head()
        file_hashes_v11 = {
            str(path.relative_to(root_v11)).replace("\\", "/"): _sha256_file(path)
            for path in _artifact_files(root_v11)
            if path.name != "manifest.json"
        }
        manifest_v11 = {
            "contractName": SKILL_RUN_CONTRACT_NAME,
            "contractVersion": SKILL_RUN_CONTRACT_VERSION_V11,
            "provider": "nodeskclaw-backend",
            "consumer": "smc-copilot/apps/work",
            "backendCommit": backend_commit,
            "tagName": f"skill-run-contract-v{SKILL_RUN_CONTRACT_VERSION_V11}",
            "generatedAt": datetime.now(timezone.utc).isoformat(),
            "artifacts": file_hashes_v11,
            "capabilities": {
                **SKILL_RUN_CAPABILITIES,
                "catalogV11": True,
            },
        }
        _write_json(root_v11 / "manifest.json", manifest_v11)
        checksum_lines_v11 = [f"{digest}  {relative}" for relative, digest in sorted(file_hashes_v11.items())]
        (root_v11 / "SHA256SUMS").write_text("\n".join(checksum_lines_v11) + "\n", encoding="utf-8")
        print(f"Generated {SKILL_RUN_CONTRACT_NAME} at {root_v11} (backendCommit={backend_commit})")

    # Generate v1.2.0 semantic event contract
    root_v12 = SKILL_RUN_CONTRACTS_HOME / f"v{SKILL_RUN_CONTRACT_VERSION_V12}"
    root_v12.mkdir(parents=True, exist_ok=True)
    (root_v12 / "mcp").mkdir(exist_ok=True)
    (root_v12 / "events").mkdir(exist_ok=True)
    (root_v12 / "runs").mkdir(exist_ok=True)
    (root_v12 / "edge").mkdir(exist_ok=True)
    (root_v12 / "installations").mkdir(exist_ok=True)
    (root_v12 / "fixtures").mkdir(exist_ok=True)

    for rel in (
        "mcp/tools-list.request.schema.json",
        "mcp/tools-list.response.schema.json",
        "mcp/skill-tool-annotations.schema.json",
        "mcp/tools-call.request.schema.json",
        "mcp/tools-call.response.schema.json",
        "mcp/json-rpc-error.schema.json",
        "runs/run.schema.json",
        "runs/execution-snapshot.schema.json",
        "runs/artifact-descriptor.schema.json",
        "edge/lease-renew.schema.json",
        "edge/artifact-upload.schema.json",
        "installations/actual-report.schema.json",
        "installations/installation.schema.json",
        "fixtures/edge-lease-renew.json",
        "fixtures/edge-artifact-upload.json",
        "fixtures/desired-installation.json",
        "fixtures/tools-call-accepted.json",
        "fixtures/skill-tools-list.json",
    ):
        src = root_v11 / rel
        if src.exists():
            dest = root_v12 / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(src.read_bytes())

    _write_json(
        root_v12 / "events" / "run-event.schema.json",
        _run_event_v12_union_schema(RUN_EVENT_V12_MODELS),
    )

    _write_json(
        root_v12 / "fixtures" / "run-event-assistant-message.json",
        {
            "event_id": "evt-1",
            "run_id": "run-1",
            "event_type": "assistant.message",
            "event_seq": 2,
            "source": "agent",
            "source_event_id": "hermes:run-1:att-1:assistant:1",
            "timestamp": "2026-08-31T00:00:00Z",
            "payload": {"text": "hello"},
        },
    )
    _write_json(
        root_v12 / "fixtures" / "run-event-tool-call.json",
        {
            "event_id": "evt-2",
            "run_id": "run-1",
            "event_type": "tool.call",
            "event_seq": 3,
            "source": "agent",
            "source_event_id": "hermes:run-1:att-1:tool:call-1:1",
            "timestamp": "2026-08-31T00:00:01Z",
            "payload": {"tool_name": "search", "call_id": "call-1", "status": "started"},
        },
    )
    _write_json(
        root_v12 / "fixtures" / "run-event-artifact-persisted.json",
        {
            "event_id": "evt-3",
            "run_id": "run-1",
            "event_type": "artifact.persisted",
            "event_seq": 4,
            "source": "agent",
            "source_event_id": "artifact:art-1:persisted",
            "timestamp": "2026-08-31T00:00:02Z",
            "payload": {
                "artifact_id": "art-1",
                "name": "out.txt",
                "content_type": "text/plain",
                "size": 12,
                "checksum_sha256": "abc123",
            },
        },
    )
    _write_json(
        root_v12 / "fixtures" / "run-event-reasoning-summary.json",
        {
            "event_id": "evt-4",
            "run_id": "run-1",
            "event_type": "reasoning.summary",
            "event_seq": 5,
            "source": "agent",
            "source_event_id": "hermes:run-1:att-1:reasoning:1",
            "timestamp": "2026-08-31T00:00:03Z",
            "payload": {"summary": "checked docs"},
        },
    )
    _write_json(
        root_v12 / "fixtures" / "run-event-clarify-requested.json",
        {
            "event_id": "evt-5",
            "run_id": "run-1",
            "event_type": "clarify.requested",
            "event_seq": 6,
            "source": "agent",
            "source_event_id": "hermes:run-1:att-1:clarify:1",
            "timestamp": "2026-08-31T00:00:04Z",
            "payload": {"question": "which file?", "options": ["a", "b"]},
        },
    )
    _write_json(
        root_v12 / "fixtures" / "run-event-approval-requested.json",
        {
            "event_id": "evt-6",
            "run_id": "run-1",
            "event_type": "approval.requested",
            "event_seq": 7,
            "source": "agent",
            "source_event_id": "hermes:run-1:att-1:approval:1",
            "timestamp": "2026-08-31T00:00:05Z",
            "payload": {"approval_id": "appr-1", "summary": "delete file"},
        },
    )
    _write_json(
        root_v12 / "fixtures" / "run-event-control-progress.json",
        {
            "event_id": "evt-0",
            "run_id": "run-1",
            "event_type": "run.progress",
            "event_seq": 1,
            "source": "agent",
            "source_event_id": None,
            "timestamp": "2026-08-31T00:00:00Z",
            "payload": {"stage": "preparing", "message": "preparing hermes"},
        },
    )
    _write_json(
        root_v12 / "fixtures" / "run-event-control-created.json",
        {
            "event_id": "evt-created",
            "run_id": "run-1",
            "event_type": "run.created",
            "event_seq": 0,
            "source": "agent",
            "source_event_id": None,
            "timestamp": "2026-08-31T00:00:00Z",
            "payload": {},
        },
    )

    (root_v12 / "RELEASE.md").write_text(
        f"# {SKILL_RUN_CONTRACT_NAME} v{SKILL_RUN_CONTRACT_VERSION_V12}\n\n"
        "Skill Run event contract v1.2.0.\n"
        "Adds enumerated semantic run events while keeping control event replay.\n",
        encoding="utf-8",
    )

    backend_commit = _git_head()
    file_hashes_v12 = {
        str(path.relative_to(root_v12)).replace("\\", "/"): _sha256_file(path)
        for path in _artifact_files(root_v12)
        if path.name != "manifest.json"
    }
    manifest_v12 = {
        "contractName": SKILL_RUN_CONTRACT_NAME,
        "contractVersion": SKILL_RUN_CONTRACT_VERSION_V12,
        "provider": "nodeskclaw-backend",
        "consumer": "smc-copilot/apps/work",
        "backendCommit": backend_commit,
        "tagName": f"skill-run-contract-v{SKILL_RUN_CONTRACT_VERSION_V12}",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "artifacts": file_hashes_v12,
        "capabilities": {
            **SKILL_RUN_CAPABILITIES,
            "catalogV11": True,
            "semanticRunEvents": True,
        },
    }
    _write_json(root_v12 / "manifest.json", manifest_v12)
    checksum_lines_v12 = [f"{digest}  {relative}" for relative, digest in sorted(file_hashes_v12.items())]
    (root_v12 / "SHA256SUMS").write_text("\n".join(checksum_lines_v12) + "\n", encoding="utf-8")
    print(f"Generated {SKILL_RUN_CONTRACT_NAME} at {root_v12} (backendCommit={backend_commit})")


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
